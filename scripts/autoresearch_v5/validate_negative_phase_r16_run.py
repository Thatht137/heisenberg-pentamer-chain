#!/usr/bin/env python3
"""严格验收 R16 三初态收敛修复结果。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RESULTS = (ROOT / "results").resolve()
CELL = "nega-r16-a0050-b0500-L080"
MODES = ("center_random", "ferro_j2", "domain")
PARAMS = {"alpha": -0.05, "beta": 0.5, "L": 80, "n_units": 16}
HASH_RE = re.compile(r"[0-9a-f]{64}")
ENERGY_CHANGE_MAX = 1e-8
ENERGY_SPREAD_MAX = 1e-6


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def under_results(path: Path) -> Path:
    resolved = path.resolve()
    resolved.relative_to(RESULTS)
    return resolved


class Audit:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.checks = {name: True for name in (
            "identity", "parent_checksums", "child_checksums", "original_gates",
            "energy_plateau", "energy_consistency", "parent_aggregate",
            "terminal_acceptance", "provenance", "data_files",
        )}

    def fail(self, category: str, message: str) -> None:
        self.checks[category] = False
        self.failures.append(message)


def read_json(path: Path, audit: Audit, category: str, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("不是对象")
        return value
    except (OSError, ValueError, json.JSONDecodeError) as error:
        audit.fail(category, f"{label}: 无法读取 JSON ({error})")
        return {}


def finite(value: Any, audit: Audit, category: str, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        audit.fail(category, f"{label}: 缺少数值")
        return math.nan
    if not math.isfinite(result):
        audit.fail(category, f"{label}: 非有限")
    return result


def close(actual: Any, expected: float, audit: Audit, category: str, label: str, tolerance: float = 1e-12) -> None:
    value = finite(actual, audit, category, label)
    if math.isfinite(value) and not math.isclose(value, expected, rel_tol=0.0, abs_tol=tolerance):
        audit.fail(category, f"{label}: {value} != {expected}")


def require_true(mapping: Any, key: str, audit: Audit, category: str, label: str) -> None:
    if not isinstance(mapping, dict) or mapping.get(key) is not True:
        audit.fail(category, f"{label}: {key} 未通过")


def verify_checksums(directory: Path, audit: Audit, category: str) -> set[str]:
    source = directory / "checksums.sha256"
    if not source.is_file():
        audit.fail(category, f"{directory.name}: 缺少 checksums.sha256")
        return set()
    entries: set[str] = set()
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or HASH_RE.fullmatch(parts[0]) is None:
            audit.fail(category, f"{directory.name}: checksum 行非法")
            continue
        target = (directory / parts[1].strip().lstrip("*")).resolve()
        try:
            target.relative_to(directory.resolve())
        except ValueError:
            audit.fail(category, f"{directory.name}: checksum 路径越界")
            continue
        relative = parts[1].strip().lstrip("*")
        entries.add(relative)
        if not target.is_file():
            audit.fail(category, f"{directory.name}: checksum 文件缺失 {parts[1]}")
        elif sha256(target) != parts[0]:
            audit.fail(category, f"{directory.name}: checksum 不匹配 {parts[1]}")
    if not entries:
        audit.fail(category, f"{directory.name}: checksum 为空")
    return entries


def valid_hashes(value: Any, audit: Audit, label: str) -> None:
    if not isinstance(value, dict) or not value:
        audit.fail("provenance", f"{label}: code_sha256 缺失")
        return
    if not all(isinstance(item, str) and HASH_RE.fullmatch(item) for item in value.values()):
        audit.fail("provenance", f"{label}: code_sha256 非法")


def validate_fullq(path: Path, expected: int, audit: Audit, label: str) -> None:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        if len(rows) != expected or expected != 401:
            audit.fail("data_files", f"{label}: full-q 点数 {len(rows)} != 401")
            return
        values = [(float(row["q"]), float(row["q_over_pi"]), float(row["Sq"])) for row in rows]
        if not all(math.isfinite(item) for row in values for item in row):
            audit.fail("data_files", f"{label}: full-q 含非有限值")
        if values and (abs(values[0][0]) > 1e-12 or abs(values[-1][1] - 1.0) > 1e-12):
            audit.fail("data_files", f"{label}: full-q 端点错误")
    except (OSError, ValueError, KeyError, csv.Error) as error:
        audit.fail("data_files", f"{label}: full-q 无法读取 ({error})")


def validate_spec(spec: dict[str, Any], audit: Audit) -> dict[str, Any]:
    cells = spec.get("cells")
    if not isinstance(cells, list) or len(cells) != 1 or not isinstance(cells[0], dict):
        audit.fail("identity", "run spec: 必须仅含一个 R16 cell")
        cell: dict[str, Any] = {}
    else:
        cell = cells[0]
    settings = spec.get("settings") if isinstance(spec.get("settings"), dict) else {}
    required = {
        "cell_id": CELL, "params": PARAMS, "budget": 256,
        "retry_of": "nega-r15-a0050-b0500-L080", "calibration_only": True,
        "controller_action_id": None,
    }
    for key, expected in required.items():
        if cell.get(key) != expected:
            audit.fail("identity", f"run spec: {key} 不匹配")
    expected_settings = {
        "nsweeps": 256, "cutoff": 1e-11, "threads": 8, "q_count": 401,
        "init_modes": list(MODES), "noise_profile": "repair",
        "energy_change_max": ENERGY_CHANGE_MAX, "energy_spread_max": ENERGY_SPREAD_MAX,
    }
    for key, expected in expected_settings.items():
        if settings.get(key) != expected:
            audit.fail("identity", f"run spec: settings.{key} 不匹配")
    if settings.get("maxdim_by_L", {}).get("80") != 1200:
        audit.fail("identity", "run spec: L80 maxdim != 1200")
    acceptance = settings.get("acceptance", {})
    strict = {
        "variance_per_site_max": 1e-8, "final_truncation_error_max": 1e-9,
        "sector_tolerance": 1e-8, "spin_gap_min": -1e-8,
        "energy_change_max": ENERGY_CHANGE_MAX, "energy_spread_max": ENERGY_SPREAD_MAX,
        "q_count_min": 401,
    }
    for key, expected in strict.items():
        if not isinstance(acceptance, dict) or acceptance.get(key) != expected:
            audit.fail("identity", f"run spec: acceptance.{key} 不匹配")
    provenance = spec.get("provenance", {})
    if not isinstance(provenance, dict) or provenance.get("thresholds_relaxed") is not False:
        audit.fail("identity", "run spec: 门槛放宽标记错误")
    if not isinstance(provenance, dict) or provenance.get("posthoc_branch_selection_forbidden") is not True:
        audit.fail("identity", "run spec: 未禁止事后选支")
    return settings


def validate_child(run: Path, parent: dict[str, Any], mode: str, audit: Audit) -> dict[str, Any]:
    directory = run / f"start_{mode}"
    entries = verify_checksums(directory, audit, "child_checksums")
    required_entries = {"manifest.json", "status.json", "structure_factor_fullq.csv",
                        "string_profile.csv", "bond_correlations.csv", "schmidt_spectrum.csv"}
    missing_entries = sorted(required_entries - entries)
    if missing_entries:
        audit.fail("child_checksums", f"{directory.name}: checksum 未覆盖 {missing_entries}")
    manifest = read_json(directory / "manifest.json", audit, "identity", f"子 manifest {mode}")
    status = read_json(directory / "status.json", audit, "identity", f"子 status {mode}")
    label = f"子 manifest {mode}"
    if manifest.get("cell_id") != f"{CELL}-{mode}" or manifest.get("params", {}).get("alpha") != -0.05:
        audit.fail("identity", f"{label}: 身份不匹配")
    for key, expected in PARAMS.items():
        if manifest.get("params", {}).get(key) != expected:
            audit.fail("identity", f"{label}: 参数 {key} 不匹配")
    settings = manifest.get("settings", {})
    expected_settings = {
        "nsweeps": 256, "maxdim": 1200, "cutoff": 1e-11, "threads": 8,
        "q_count": 401, "init_mode_sz0": mode, "init_mode_sz1": "center",
        "noise_profile": "repair", "energy_change_max": ENERGY_CHANGE_MAX,
    }
    for key, expected in expected_settings.items():
        if not isinstance(settings, dict) or settings.get(key) != expected:
            audit.fail("identity", f"{label}: settings.{key} 不匹配")
    if settings.get("random_seed") != parent.get("settings", {}).get("random_seed"):
        audit.fail("identity", f"{label}: random_seed 与父级不一致")
    if settings.get("sectors") != ["Sz=0", "Sz=1"]:
        audit.fail("identity", f"{label}: 扇区定义错误")

    diagnostics = manifest.get("diagnostics", {})
    observables = manifest.get("observables", {})
    acceptance = manifest.get("acceptance", {})
    for sector in ("sz0", "sz1"):
        variance = finite(diagnostics.get(f"variance_per_site_{sector}"), audit, "original_gates", f"{label}: variance {sector}")
        truncation = finite(diagnostics.get(f"final_truncation_error_{sector}"), audit, "original_gates", f"{label}: truncation {sector}")
        change = finite(diagnostics.get(f"final_energy_change_{sector}"), audit, "energy_plateau", f"{label}: energy change {sector}")
        sweeps = finite(diagnostics.get(f"nsweeps_completed_{sector}", 256), audit, "original_gates", f"{label}: sweeps {sector}")
        if variance > 1e-8:
            audit.fail("original_gates", f"{label}: variance {sector} 超门")
        if truncation > 1e-9:
            audit.fail("original_gates", f"{label}: truncation {sector} 超门")
        if change > ENERGY_CHANGE_MAX:
            audit.fail("energy_plateau", f"{label}: energy change {sector} 超门")
        if sweeps != 256:
            audit.fail("original_gates", f"{label}: sweeps {sector} 未完成")
        require_true(acceptance, f"variance_{sector}_per_site_le_1e-8", audit, "original_gates", label)
        require_true(acceptance, f"truncation_{sector}_le_1e-9", audit, "original_gates", label)
        require_true(acceptance, f"energy_plateau_{sector}", audit, "energy_plateau", label)
    total0 = finite(diagnostics.get("total_sz0"), audit, "original_gates", f"{label}: Sz0")
    total1 = finite(diagnostics.get("total_sz1"), audit, "original_gates", f"{label}: Sz1")
    seed_offsets = {"center_random": 101, "domain": 211, "ferro_j2": 307}
    base_seed = int(parent.get("settings", {}).get("random_seed", -1))
    if diagnostics.get("initial_seed_sz0") != base_seed + 17 * PARAMS["L"] + seed_offsets[mode]:
        audit.fail("identity", f"{label}: Sz0 初态种子不匹配")
    if diagnostics.get("initial_seed_sz1") != -1:
        audit.fail("identity", f"{label}: Sz1 center 初态不应使用随机种子")
    gap = finite(observables.get("spin_gap"), audit, "original_gates", f"{label}: spin gap")
    energy0 = finite(observables.get("energy_sz0"), audit, "original_gates", f"{label}: energy Sz0")
    energy1 = finite(observables.get("energy_sz1"), audit, "original_gates", f"{label}: energy Sz1")
    if abs(total0) > 1e-8 or abs(total1 - 1.0) > 1e-8:
        audit.fail("original_gates", f"{label}: Sz 扇区偏离")
    if gap < -1e-8:
        audit.fail("original_gates", f"{label}: spin gap 低于门槛")
    if all(math.isfinite(value) for value in (gap, energy0, energy1)) and not math.isclose(gap, energy1 - energy0, rel_tol=0.0, abs_tol=1e-12):
        audit.fail("original_gates", f"{label}: spin gap 与两扇区能量不一致")
    for key in (
        "execution_success", "sz0_sector", "sz1_sector", "nonnegative_gap",
        "all_sweeps_completed", "fullq_file", "fullq_count", "measurement_files",
    ):
        require_true(acceptance, key, audit, "original_gates", label)
    if manifest.get("status") != "success" or manifest.get("accepted") is not True:
        audit.fail("terminal_acceptance", f"{label}: 非 accepted success")
    if status.get("status") != "success" or status.get("accepted") is not True:
        audit.fail("terminal_acceptance", f"子 status {mode}: 非 accepted success")
    validate_fullq(directory / "structure_factor_fullq.csv", int(settings.get("q_count", 0)), audit, label)
    for name in ("string_profile.csv", "bond_correlations.csv", "schmidt_spectrum.csv"):
        if not (directory / name).is_file():
            audit.fail("data_files", f"{label}: 缺少 {name}")
    provenance = manifest.get("provenance", {})
    if not isinstance(provenance, dict) or provenance.get("noise_protocol") != "repair":
        audit.fail("provenance", f"{label}: repair noise provenance 缺失")
    valid_hashes(provenance.get("code_sha256") if isinstance(provenance, dict) else None, audit, label)
    return manifest


def validate_aggregate(parent: dict[str, Any], children: dict[str, dict[str, Any]], audit: Audit) -> dict[str, float]:
    child_obs = {mode: child.get("observables", {}) for mode, child in children.items()}
    truncations = [
        max(float(child.get("diagnostics", {}).get("final_truncation_error_sz0", math.inf)),
            float(child.get("diagnostics", {}).get("final_truncation_error_sz1", math.inf)))
        for child in children.values()
    ]
    numerical_floor = max(10 * max(truncations, default=math.inf), 1e-4)
    rules = {
        "structure_factor_ratio": ("structure_factor_ratio", numerical_floor),
        "structure_factor_peak_q_over_pi": ("structure_factor_peak_q_over_pi", 1 / 400),
        "structure_factor_peak": ("structure_factor_peak", numerical_floor),
        "dominant_structure_factor_ratio": ("dominant_structure_factor_ratio", numerical_floor),
        "structure_factor_peak_ratio": ("dominant_structure_factor_ratio", numerical_floor),
    }
    parent_obs = parent.get("observables", {})
    declared_half = parent.get("diagnostics", {}).get("independent_start_half_range")
    if not isinstance(declared_half, dict):
        audit.fail("parent_aggregate", "父 manifest: 缺少 independent_start_half_range")
        declared_half = {}
    half_keys = {
        "structure_factor_ratio": "pi_ratio",
        "structure_factor_peak_q_over_pi": "q_peak_over_pi",
        "structure_factor_peak": "peak",
        "dominant_structure_factor_ratio": "peak_ratio",
    }
    for parent_key, (child_key, floor) in rules.items():
        values = [finite(child_obs[mode].get(child_key), audit, "parent_aggregate", f"{mode}.{child_key}") for mode in MODES]
        if not all(math.isfinite(value) for value in values):
            continue
        mean = sum(values) / 3
        half_range = (max(values) - min(values)) / 2
        item = parent_obs.get(parent_key) if isinstance(parent_obs, dict) else None
        close(item.get("value") if isinstance(item, dict) else None, mean, audit, "parent_aggregate", f"父 {parent_key}.value")
        close(item.get("error") if isinstance(item, dict) else None, max(half_range, floor), audit, "parent_aggregate", f"父 {parent_key}.error")
        if parent_key in half_keys:
            close(declared_half.get(half_keys[parent_key]), half_range, audit, "parent_aggregate", f"父 half range {half_keys[parent_key]}")
    energies: dict[str, float] = {}
    declared = parent.get("diagnostics", {}).get("independent_start_energy_spread")
    if not isinstance(declared, dict):
        audit.fail("energy_consistency", "父 manifest: 缺少 independent_start_energy_spread")
        declared = {}
    for sector in ("sz0", "sz1"):
        values = [finite(child_obs[mode].get(f"energy_{sector}"), audit, "energy_consistency", f"{mode}.energy_{sector}") for mode in MODES]
        spread = max(values) - min(values) if all(math.isfinite(value) for value in values) else math.inf
        energies[sector] = spread
        if spread > ENERGY_SPREAD_MAX:
            audit.fail("energy_consistency", f"三初态 energy {sector} spread {spread} > 1e-6")
        close(declared.get(sector), spread, audit, "energy_consistency", f"父 energy spread {sector}", tolerance=1e-13)
    require_true(parent.get("acceptance", {}), "energy_consistency", audit, "energy_consistency", "父 manifest")
    return energies


def validate(run_path: Path, spec_path: Path) -> dict[str, Any]:
    run, spec_file = under_results(run_path), under_results(spec_path)
    audit = Audit()
    spec = read_json(spec_file, audit, "identity", "run spec")
    spec_settings = validate_spec(spec, audit)
    parent_entries = verify_checksums(run, audit, "parent_checksums")
    missing_parent = sorted({"manifest.json", "status.json"} - parent_entries)
    if missing_parent:
        audit.fail("parent_checksums", f"父目录: checksum 未覆盖 {missing_parent}")
    parent = read_json(run / "manifest.json", audit, "identity", "父 manifest")
    status = read_json(run / "status.json", audit, "identity", "父 status")
    if parent.get("cell_id") != CELL or parent.get("params") != PARAMS:
        audit.fail("identity", "父 manifest: cell 或参数不匹配")
    settings = parent.get("settings", {})
    expected_parent = {
        "nsweeps": 256, "maxdim": 1200, "cutoff": 1e-11, "threads": 8,
        "q_count": 401, "init_modes": list(MODES), "noise_profile": "repair",
        "energy_change_max": ENERGY_CHANGE_MAX, "energy_spread_max": ENERGY_SPREAD_MAX,
    }
    for key, expected in expected_parent.items():
        if not isinstance(settings, dict) or settings.get(key) != expected:
            audit.fail("identity", f"父 manifest: settings.{key} 不匹配")
    if settings.get("random_seed") != spec_settings.get("random_seed"):
        audit.fail("identity", "父 manifest: random_seed 与 run spec 不一致")
    expected_paths = [f"start_{mode}/manifest.json" for mode in MODES]
    if parent.get("diagnostics", {}).get("child_manifests") != expected_paths:
        audit.fail("identity", "父 manifest: 三子 manifest 顺序不匹配")
    children = {mode: validate_child(run, parent, mode, audit) for mode in MODES}
    energy_spread = validate_aggregate(parent, children, audit)
    for key in (
        "children_completed", "children_accepted", "finite_pi_ratio", "finite_q_peak",
        "finite_peak", "finite_peak_ratio",
    ):
        require_true(parent.get("acceptance", {}), key, audit, "terminal_acceptance", "父 manifest")
    if parent.get("status") != "success" or parent.get("accepted") is not True:
        audit.fail("terminal_acceptance", "父 manifest: 非 accepted success")
    if status.get("status") != "success" or status.get("accepted") is not True:
        audit.fail("terminal_acceptance", "父 status: 非 accepted success")
    provenance = parent.get("provenance", {})
    expected_provenance = spec.get("provenance", {})
    for key in ("standard_sha256", "manifest_sha256"):
        value = provenance.get(key) if isinstance(provenance, dict) else None
        if value != expected_provenance.get(key) or not isinstance(value, str) or HASH_RE.fullmatch(value) is None:
            audit.fail("provenance", f"父 manifest: {key} 与 run spec 不一致")
    parent_code = provenance.get("code_sha256") if isinstance(provenance, dict) else None
    valid_hashes(parent_code, audit, "父 manifest")
    expected_code = expected_provenance.get("code_sha256") if isinstance(expected_provenance, dict) else None
    if not isinstance(expected_code, dict):
        audit.fail("provenance", "run spec: code_sha256 缺失")
        expected_code = {}
    if isinstance(parent_code, dict):
        for name, digest in parent_code.items():
            if expected_code.get(name) != digest:
                audit.fail("provenance", f"父 manifest: {name} hash 与 run spec 不一致")
    for mode, child in children.items():
        child_provenance = child.get("provenance", {})
        for key in ("standard_sha256", "manifest_sha256"):
            if not isinstance(child_provenance, dict) or child_provenance.get(key) != provenance.get(key):
                audit.fail("provenance", f"子 manifest {mode}: {key} 与父级不一致")
        child_code = child_provenance.get("code_sha256") if isinstance(child_provenance, dict) else None
        if isinstance(child_code, dict):
            for name, digest in child_code.items():
                if expected_code.get(name) != digest:
                    audit.fail("provenance", f"子 manifest {mode}: {name} hash 与 run spec 不一致")
    return {
        "schema_version": 1,
        "status": "pass" if not audit.failures else "fail",
        "run_dir": str(run),
        "run_spec": str(spec_file),
        "cell_id": parent.get("cell_id"),
        "checks": audit.checks,
        "energy_spread": energy_spread,
        "limits": {"energy_change_max": ENERGY_CHANGE_MAX, "energy_spread_max": ENERGY_SPREAD_MAX},
        "failures": audit.failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--run-spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = under_results(args.output)
    result = validate(args.run_dir, args.run_spec)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
