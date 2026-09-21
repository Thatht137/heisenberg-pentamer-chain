#!/usr/bin/env python3
"""以实用末步能量门裁决 R16，本体证据保持不变。"""

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
ENERGY_CHANGE_MAX = 1e-7
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
            "identity", "transfer", "parent_checksums", "child_checksums",
            "core_gates", "practical_energy_plateau", "energy_consistency",
            "parent_aggregate", "strict_failure_provenance", "data_files",
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


def close(actual: Any, expected: float, audit: Audit, category: str, label: str) -> None:
    value = finite(actual, audit, category, label)
    if math.isfinite(value) and not math.isclose(value, expected, rel_tol=0.0, abs_tol=1e-12):
        audit.fail(category, f"{label}: {value} != {expected}")


def require_true(mapping: Any, key: str, audit: Audit, category: str, label: str) -> None:
    if not isinstance(mapping, dict) or mapping.get(key) is not True:
        audit.fail(category, f"{label}: {key} 未通过")


def verify_checksums(directory: Path, audit: Audit, category: str, required: set[str]) -> int:
    source = directory / "checksums.sha256"
    if not source.is_file():
        audit.fail(category, f"{directory.name}: 缺少 checksums.sha256")
        return 0
    entries: set[str] = set()
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or HASH_RE.fullmatch(parts[0]) is None:
            audit.fail(category, f"{directory.name}: checksum 行非法")
            continue
        name = parts[1].strip().lstrip("*")
        target = (directory / name).resolve()
        try:
            target.relative_to(directory.resolve())
        except ValueError:
            audit.fail(category, f"{directory.name}: checksum 路径越界")
            continue
        entries.add(name)
        if not target.is_file() or sha256(target) != parts[0]:
            audit.fail(category, f"{directory.name}: checksum 不匹配 {name}")
    missing = sorted(required - entries)
    if missing:
        audit.fail(category, f"{directory.name}: checksum 未覆盖 {missing}")
    return len(entries)


def validate_fullq(path: Path, audit: Audit, label: str) -> None:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        if len(rows) != 401:
            audit.fail("data_files", f"{label}: full-q 点数 {len(rows)} != 401")
            return
        values = [(float(row["q"]), float(row["q_over_pi"]), float(row["Sq"])) for row in rows]
        if not all(math.isfinite(item) for row in values for item in row):
            audit.fail("data_files", f"{label}: full-q 含非有限值")
        if abs(values[0][0]) > 1e-12 or abs(values[-1][1] - 1.0) > 1e-12:
            audit.fail("data_files", f"{label}: full-q 端点错误")
    except (OSError, ValueError, KeyError, csv.Error, IndexError) as error:
        audit.fail("data_files", f"{label}: full-q 无法读取 ({error})")


def check_spec(spec: dict[str, Any], audit: Audit) -> dict[str, Any]:
    cells = spec.get("cells", [])
    if not isinstance(cells, list) or len(cells) != 1 or not isinstance(cells[0], dict):
        audit.fail("identity", "run spec: 必须仅含一个 R16 cell")
        cell: dict[str, Any] = {}
    else:
        cell = cells[0]
    expected = {"cell_id": CELL, "params": PARAMS, "budget": 256,
                "retry_of": "nega-r15-a0050-b0500-L080", "calibration_only": True,
                "controller_action_id": None}
    for key, value in expected.items():
        if cell.get(key) != value:
            audit.fail("identity", f"run spec: {key} 不匹配")
    settings = spec.get("settings", {})
    protocol = {"nsweeps": 256, "cutoff": 1e-11, "threads": 8, "q_count": 401,
                "init_modes": list(MODES), "noise_profile": "repair",
                "energy_change_max": 1e-8, "energy_spread_max": 1e-6}
    for key, value in protocol.items():
        if not isinstance(settings, dict) or settings.get(key) != value:
            audit.fail("identity", f"run spec: settings.{key} 不匹配")
    if settings.get("maxdim_by_L", {}).get("80") != 1200:
        audit.fail("identity", "run spec: L80 maxdim != 1200")
    provenance = spec.get("provenance", {})
    if not isinstance(provenance, dict) or provenance.get("thresholds_relaxed") is not False:
        audit.fail("identity", "run spec: 原协议 provenance 错误")
    return settings if isinstance(settings, dict) else {}


def validate_child(run: Path, parent: dict[str, Any], mode: str, audit: Audit) -> dict[str, Any]:
    directory = run / f"start_{mode}"
    required = {"manifest.json", "status.json", "structure_factor_fullq.csv",
                "string_profile.csv", "bond_correlations.csv", "schmidt_spectrum.csv"}
    verify_checksums(directory, audit, "child_checksums", required)
    manifest = read_json(directory / "manifest.json", audit, "identity", f"子 manifest {mode}")
    status = read_json(directory / "status.json", audit, "identity", f"子 status {mode}")
    label = f"子 manifest {mode}"
    if manifest.get("cell_id") != f"{CELL}-{mode}":
        audit.fail("identity", f"{label}: cell_id 不匹配")
    for key, value in PARAMS.items():
        if manifest.get("params", {}).get(key) != value:
            audit.fail("identity", f"{label}: 参数 {key} 不匹配")
    settings = manifest.get("settings", {})
    expected_settings = {"nsweeps": 256, "maxdim": 1200, "cutoff": 1e-11, "threads": 8,
                         "q_count": 401, "init_mode_sz0": mode, "init_mode_sz1": "center",
                         "noise_profile": "repair", "energy_change_max": 1e-8}
    for key, value in expected_settings.items():
        if not isinstance(settings, dict) or settings.get(key) != value:
            audit.fail("identity", f"{label}: settings.{key} 不匹配")
    base_seed = int(parent.get("settings", {}).get("random_seed", -1))
    offsets = {"center_random": 101, "ferro_j2": 307, "domain": 211}
    diagnostics, observables, acceptance = (
        manifest.get("diagnostics", {}), manifest.get("observables", {}), manifest.get("acceptance", {}))
    if diagnostics.get("initial_seed_sz0") != base_seed + 17 * 80 + offsets[mode] or diagnostics.get("initial_seed_sz1") != -1:
        audit.fail("identity", f"{label}: 初态种子不匹配")
    for sector in ("sz0", "sz1"):
        variance = finite(diagnostics.get(f"variance_per_site_{sector}"), audit, "core_gates", f"{label}: variance {sector}")
        truncation = finite(diagnostics.get(f"final_truncation_error_{sector}"), audit, "core_gates", f"{label}: truncation {sector}")
        change = finite(diagnostics.get(f"final_energy_change_{sector}"), audit, "practical_energy_plateau", f"{label}: energy change {sector}")
        if variance > 1e-8:
            audit.fail("core_gates", f"{label}: variance {sector} 超门")
        if truncation > 1e-9:
            audit.fail("core_gates", f"{label}: truncation {sector} 超门")
        if change > ENERGY_CHANGE_MAX:
            audit.fail("practical_energy_plateau", f"{label}: energy change {sector} > 1e-7")
        require_true(acceptance, f"variance_{sector}_per_site_le_1e-8", audit, "core_gates", label)
        require_true(acceptance, f"truncation_{sector}_le_1e-9", audit, "core_gates", label)
    total0 = finite(diagnostics.get("total_sz0"), audit, "core_gates", f"{label}: Sz0")
    total1 = finite(diagnostics.get("total_sz1"), audit, "core_gates", f"{label}: Sz1")
    energy0 = finite(observables.get("energy_sz0"), audit, "core_gates", f"{label}: energy Sz0")
    energy1 = finite(observables.get("energy_sz1"), audit, "core_gates", f"{label}: energy Sz1")
    gap = finite(observables.get("spin_gap"), audit, "core_gates", f"{label}: spin gap")
    if abs(total0) > 1e-8 or abs(total1 - 1.0) > 1e-8:
        audit.fail("core_gates", f"{label}: Sz 扇区偏离")
    if gap < -1e-8:
        audit.fail("core_gates", f"{label}: spin gap 低于门槛")
    if all(math.isfinite(value) for value in (energy0, energy1, gap)) and not math.isclose(gap, energy1 - energy0, rel_tol=0.0, abs_tol=1e-12):
        audit.fail("core_gates", f"{label}: spin gap 与能量差不一致")
    for key in ("execution_success", "sz0_sector", "sz1_sector", "nonnegative_gap",
                "all_sweeps_completed", "fullq_file", "fullq_count", "measurement_files"):
        require_true(acceptance, key, audit, "core_gates", label)
    if manifest.get("status") != "success" or status.get("status") != "success":
        audit.fail("core_gates", f"{label}: 执行未成功")
    validate_fullq(directory / "structure_factor_fullq.csv", audit, label)
    for name in ("string_profile.csv", "bond_correlations.csv", "schmidt_spectrum.csv"):
        if not (directory / name).is_file():
            audit.fail("data_files", f"{label}: 缺少 {name}")
    return manifest


def validate_aggregate(parent: dict[str, Any], children: dict[str, dict[str, Any]], audit: Audit) -> tuple[dict[str, float], dict[str, float]]:
    child_obs = {mode: children[mode].get("observables", {}) for mode in MODES}
    truncations = [max(float(children[mode].get("diagnostics", {}).get("final_truncation_error_sz0", math.inf)),
                       float(children[mode].get("diagnostics", {}).get("final_truncation_error_sz1", math.inf))) for mode in MODES]
    numerical_floor = max(10 * max(truncations), 1e-4)
    rules = {"structure_factor_ratio": ("structure_factor_ratio", numerical_floor),
             "structure_factor_peak_q_over_pi": ("structure_factor_peak_q_over_pi", 1 / 400),
             "structure_factor_peak": ("structure_factor_peak", numerical_floor),
             "dominant_structure_factor_ratio": ("dominant_structure_factor_ratio", numerical_floor),
             "structure_factor_peak_ratio": ("dominant_structure_factor_ratio", numerical_floor)}
    parent_obs = parent.get("observables", {})
    for parent_key, (child_key, floor) in rules.items():
        values = [finite(child_obs[mode].get(child_key), audit, "parent_aggregate", f"{mode}.{child_key}") for mode in MODES]
        if not all(math.isfinite(value) for value in values):
            continue
        mean, half = sum(values) / 3, (max(values) - min(values)) / 2
        item = parent_obs.get(parent_key) if isinstance(parent_obs, dict) else None
        close(item.get("value") if isinstance(item, dict) else None, mean, audit, "parent_aggregate", f"父 {parent_key}.value")
        close(item.get("error") if isinstance(item, dict) else None, max(half, floor), audit, "parent_aggregate", f"父 {parent_key}.error")
    spreads: dict[str, float] = {}
    for sector in ("sz0", "sz1"):
        values = [finite(child_obs[mode].get(f"energy_{sector}"), audit, "energy_consistency", f"{mode}.energy_{sector}") for mode in MODES]
        spread = max(values) - min(values) if all(math.isfinite(value) for value in values) else math.inf
        spreads[sector] = spread
        if spread > ENERGY_SPREAD_MAX:
            audit.fail("energy_consistency", f"三初态 energy {sector} spread {spread} > 1e-6")
    ratio = parent_obs.get("dominant_structure_factor_ratio", {})
    calibration = {"value": finite(ratio.get("value"), audit, "parent_aggregate", "父 ratio.value"),
                   "error": finite(ratio.get("error"), audit, "parent_aggregate", "父 ratio.error")}
    return spreads, calibration


def adjudicate(fetch_path: Path, spec_path: Path, strict_path: Path) -> dict[str, Any]:
    fetch, spec_file, strict_file = map(under_results, (fetch_path, spec_path, strict_path))
    audit = Audit()
    run = fetch / CELL
    spec = read_json(spec_file, audit, "identity", "run spec")
    spec_settings = check_spec(spec, audit)
    preview = read_json(fetch / "preview.json", audit, "transfer", "fetch preview")
    receipt = read_json(fetch / "receipt.json", audit, "transfer", "fetch receipt")
    if (preview.get("status") != "pass" or preview.get("remote_checksum_status") != "pass"
            or preview.get("destination_exists") is not False
            or Path(preview.get("local_destination", "")).resolve() != run):
        audit.fail("transfer", "fetch preview 身份或远端 checksum 失败")
    if (receipt.get("status") != "pass" or receipt.get("non_clobbering") is not True
            or receipt.get("cell_id") != CELL or Path(receipt.get("destination", "")).resolve() != run
            or receipt.get("preview_sha256") != sha256(fetch / "preview.json")):
        audit.fail("transfer", "fetch receipt 身份或非覆盖门失败")
    verify_checksums(run, audit, "parent_checksums", {"manifest.json", "status.json"})
    parent = read_json(run / "manifest.json", audit, "identity", "父 manifest")
    status = read_json(run / "status.json", audit, "identity", "父 status")
    if receipt.get("manifest_sha256") != sha256(run / "manifest.json"):
        audit.fail("transfer", "fetch receipt 的 manifest hash 不匹配")
    if parent.get("cell_id") != CELL or parent.get("params") != PARAMS:
        audit.fail("identity", "父 manifest 身份不匹配")
    settings = parent.get("settings", {})
    parent_protocol = {"nsweeps": 256, "maxdim": 1200, "cutoff": 1e-11, "threads": 8,
                       "q_count": 401, "init_modes": list(MODES), "noise_profile": "repair",
                       "energy_change_max": 1e-8}
    for key, value in parent_protocol.items():
        if not isinstance(settings, dict) or settings.get(key) != value:
            audit.fail("identity", f"父 manifest: settings.{key} 不匹配")
    if settings.get("random_seed") != spec_settings.get("random_seed"):
        audit.fail("identity", "父 manifest: random_seed 与 run spec 不一致")
    expected_children = [f"start_{mode}/manifest.json" for mode in MODES]
    if parent.get("diagnostics", {}).get("child_manifests") != expected_children:
        audit.fail("identity", "父 manifest: 三初态顺序不匹配")
    children = {mode: validate_child(run, parent, mode, audit) for mode in MODES}
    spreads, calibration = validate_aggregate(parent, children, audit)
    for key in ("children_completed", "finite_pi_ratio", "finite_q_peak", "finite_peak", "finite_peak_ratio"):
        require_true(parent.get("acceptance", {}), key, audit, "core_gates", "父 manifest")
    if parent.get("status") != "failed" or parent.get("accepted") is not False:
        audit.fail("strict_failure_provenance", "父 manifest 不是原严格失败终态")
    if status.get("status") != "failed" or status.get("accepted") is not False:
        audit.fail("strict_failure_provenance", "父 status 不是原严格失败终态")
    strict = read_json(strict_file, audit, "strict_failure_provenance", "strict validator")
    if (strict.get("status") != "fail" or strict.get("cell_id") != CELL
            or Path(strict.get("run_dir", "")).resolve() != run or not strict.get("failures")):
        audit.fail("strict_failure_provenance", "strict validator 失败 provenance 不匹配")
    accepted = not audit.failures
    return {"schema_version": 1, "status": "pass" if accepted else "fail",
            "decision": "accepted_practical_calibration" if accepted else "NotEvaluable",
            "accepted_practical_calibration": accepted, "boundary_eligible": False,
            "fetch_dir": str(fetch), "run_dir": str(run), "run_spec": str(spec_file), "cell_id": CELL,
            "checks": audit.checks, "calibration_observable": calibration,
            "energy_spread": spreads,
            "policy": {"variance_per_site_max": 1e-8, "final_truncation_error_max": 1e-9,
                       "sector_tolerance": 1e-8, "spin_gap_min": -1e-8, "q_count": 401,
                       "energy_change_max": ENERGY_CHANGE_MAX, "energy_spread_max": ENERGY_SPREAD_MAX,
                       "only_energy_change_gate_relaxed": True},
            "strict_failure_provenance": {"artifact": str(strict_file), "sha256": sha256(strict_file),
                                          "status": strict.get("status"), "failures": strict.get("failures", [])},
            "failures": audit.failures}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch-dir", type=Path, required=True)
    parser.add_argument("--run-spec", type=Path, required=True)
    parser.add_argument("--strict-validation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = under_results(args.output)
    result = adjudicate(args.fetch_dir, args.run_spec, args.strict_validation)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
