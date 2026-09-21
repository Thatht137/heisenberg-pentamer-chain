#!/usr/bin/env python3
"""独立验收负 alpha 相图双初态 cell。"""

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
HASH_RE = re.compile(r"[0-9a-f]{64}")


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


def checksum_ok(run: Path) -> list[str]:
    source = run / "checksums.sha256"
    if not source.is_file():
        return [f"{run.name}: 缺少 checksums.sha256"]
    failures: list[str] = []
    lines = [line for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return [f"{run.name}: 空 checksums.sha256"]
    for line in lines:
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or HASH_RE.fullmatch(parts[0]) is None:
            failures.append(f"{run.name}: 非法 checksum 行")
            continue
        target = (run / parts[1].strip().lstrip("*")).resolve()
        try:
            target.relative_to(run)
        except ValueError:
            failures.append(f"{run.name}: checksum 路径越界")
            continue
        if not target.is_file():
            failures.append(f"{run.name}: checksum 文件缺失 {parts[1]}")
        elif sha256(target) != parts[0]:
            failures.append(f"{run.name}: checksum 不匹配 {parts[1]}")
    return failures


def read_json(path: Path, failures: list[str], label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("不是对象")
        return value
    except (OSError, ValueError, json.JSONDecodeError) as error:
        failures.append(f"{label}: 无法读取 JSON ({error})")
        return {}


def number(value: Any, label: str, failures: list[str]) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        failures.append(f"{label}: 缺少数值")
        return math.nan
    if not math.isfinite(result):
        failures.append(f"{label}: 非有限")
    return result


def true(mapping: Any, key: str, failures: list[str], label: str) -> None:
    if not isinstance(mapping, dict) or mapping.get(key) is not True:
        failures.append(f"{label}: {key} 未通过")


def expected_cell(spec: dict[str, Any], identifier: str, failures: list[str]) -> dict[str, Any]:
    cells = spec.get("cells")
    if not isinstance(cells, list):
        failures.append("run spec: 缺少 cells")
        return {}
    matches = [cell for cell in cells if isinstance(cell, dict) and cell.get("cell_id") == identifier]
    if len(matches) != 1:
        failures.append(f"run spec: cell_id={identifier} 匹配数为 {len(matches)}，必须唯一")
        return {}
    return matches[0]


def expected_hash(spec: dict[str, Any], key: str) -> str | None:
    for mapping in (spec, spec.get("provenance"), spec.get("contract"), spec.get("expected_hashes")):
        if isinstance(mapping, dict) and isinstance(mapping.get(key), str):
            return mapping[key]
    return None


def read_fullq(path: Path, expected_count: int, label: str, failures: list[str]) -> None:
    try:
        raw = path.read_text(encoding="utf-8")
        if "\\n" in raw:
            failures.append(f"{label}: full-q 将换行写成字面 \\n，记录不可解析")
            return
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        if not rows or set((rows[0] or {}).keys()) < {"q", "q_over_pi", "Sq"}:
            failures.append(f"{label}: full-q 表头不完整")
            return
        if len(rows) != expected_count or expected_count < 401:
            failures.append(f"{label}: full-q 点数 {len(rows)}，期望 {expected_count} 且不少于 401")
        values = [(float(row["q"]), float(row["q_over_pi"]), float(row["Sq"])) for row in rows]
        if not all(math.isfinite(value) for row in values for value in row):
            failures.append(f"{label}: full-q 含非有限值")
    except (OSError, ValueError, KeyError, csv.Error) as error:
        failures.append(f"{label}: 无法读取 full-q ({error})")


def valid_hashes(value: Any, label: str, failures: list[str]) -> None:
    if not isinstance(value, dict) or not value or not all(isinstance(item, str) and HASH_RE.fullmatch(item) for item in value.values()):
        failures.append(f"{label}: 源码 hash 缺失或非法")


def validate_child(parent: dict[str, Any], child: Path, mode: str, failures: list[str]) -> dict[str, Any]:
    label = f"子 manifest {mode}"
    failures.extend(checksum_ok(child))
    manifest = read_json(child / "manifest.json", failures, label)
    status = read_json(child / "status.json", failures, f"子 status {mode}")
    if manifest.get("status") != "success" or manifest.get("accepted") is not True:
        failures.append(f"{label}: 非 accepted success")
    if status.get("status") != "success" or status.get("accepted") is not True:
        failures.append(f"子 status {mode}: 非 accepted success")
    params, settings = manifest.get("params", {}), manifest.get("settings", {})
    parent_params = parent.get("params", {})
    for key in ("alpha", "beta", "L", "n_units"):
        if params.get(key) != parent_params.get(key):
            failures.append(f"{label}: 参数 {key} 与父 cell 不一致")
    if settings.get("sectors") != ["Sz=0", "Sz=1"]:
        failures.append(f"{label}: Sz 扇区定义错误")
    expected_sweeps = parent.get("settings", {}).get("nsweeps") if isinstance(parent.get("settings"), dict) else None
    if settings.get("nsweeps") != expected_sweeps:
        failures.append(f"{label}: sweeps 与父 cell 不一致")
    diagnostics, acceptance = manifest.get("diagnostics", {}), manifest.get("acceptance", {})
    for sector in ("sz0", "sz1"):
        variance = number(diagnostics.get(f"variance_per_site_{sector}"), f"{label}: variance {sector}", failures)
        truncation = number(diagnostics.get(f"final_truncation_error_{sector}"), f"{label}: final truncation {sector}", failures)
        if variance > 1e-8:
            failures.append(f"{label}: variance/site {sector} 超门")
        if truncation > 1e-9:
            failures.append(f"{label}: final truncation {sector} 超门")
        true(acceptance, f"variance_{sector}_per_site_le_1e-8", failures, label)
        true(acceptance, f"truncation_{sector}_le_1e-9", failures, label)
    total0 = number(diagnostics.get("total_sz0"), f"{label}: total Sz0", failures)
    total1 = number(diagnostics.get("total_sz1"), f"{label}: total Sz1", failures)
    if abs(total0) > 1e-8 or abs(total1 - 1.0) > 1e-8:
        failures.append(f"{label}: Sz 扇区偏离")
    true(acceptance, "sz0_sector", failures, label)
    true(acceptance, "sz1_sector", failures, label)
    for key in ("execution_success", "nonnegative_gap", "all_sweeps_completed", "fullq_file", "fullq_count", "measurement_files"):
        true(acceptance, key, failures, label)
    gap = number((manifest.get("observables") or {}).get("spin_gap"), f"{label}: spin gap", failures)
    if gap < -1e-8:
        failures.append(f"{label}: spin gap 低于非负门")
    energy_change_max = parent.get("settings", {}).get("energy_change_max") if isinstance(parent.get("settings"), dict) else None
    if energy_change_max is not None:
        threshold = number(energy_change_max, f"{label}: energy change max", failures)
        for sector in ("sz0", "sz1"):
            change = number(diagnostics.get(f"final_energy_change_{sector}"), f"{label}: final energy change {sector}", failures)
            if change > threshold:
                failures.append(f"{label}: energy plateau {sector} 超门")
            true(acceptance, f"energy_plateau_{sector}", failures, label)
    sweeps0 = number((manifest.get("diagnostics") or {}).get("nsweeps_completed_sz0", expected_sweeps), f"{label}: sweeps Sz0", failures)
    sweeps1 = number((manifest.get("diagnostics") or {}).get("nsweeps_completed_sz1", expected_sweeps), f"{label}: sweeps Sz1", failures)
    if sweeps0 != expected_sweeps or sweeps1 != expected_sweeps:
        failures.append(f"{label}: sweeps 未完成")
    q_count = settings.get("q_count")
    if not isinstance(q_count, int):
        failures.append(f"{label}: q_count 缺失")
        q_count = 0
    read_fullq(child / "structure_factor_fullq.csv", q_count, label, failures)
    provenance = manifest.get("provenance", {})
    valid_hashes(provenance.get("code_sha256") if isinstance(provenance, dict) else None, label, failures)
    return manifest


def validate(run: Path, spec_path: Path) -> dict[str, Any]:
    run, spec_path = under_results(run), under_results(spec_path)
    failures: list[str] = []
    spec = read_json(spec_path, failures, "run spec")
    parent = read_json(run / "manifest.json", failures, "父 manifest")
    status = read_json(run / "status.json", failures, "父 status")
    failures.extend(checksum_ok(run))
    identifier = parent.get("cell_id")
    if not isinstance(identifier, str):
        failures.append("父 manifest: 缺少 cell_id")
        identifier = ""
    expected = expected_cell(spec, identifier, failures)
    if parent.get("status") != "success" or parent.get("accepted") is not True:
        failures.append("父 manifest: 非 accepted success")
    if status.get("status") != "success" or status.get("accepted") is not True:
        failures.append("父 status: 非 accepted success")
    params, settings = parent.get("params", {}), parent.get("settings", {})
    alpha = number(params.get("alpha") if isinstance(params, dict) else None, "alpha", failures)
    beta = number(params.get("beta") if isinstance(params, dict) else None, "beta", failures)
    if not -1.0 <= alpha < 0.0:
        failures.append("alpha 不在 [-1,0)")
    if not 0.0 <= beta <= 1.0:
        failures.append("beta 不在 [0,1]")
    expected_params = expected.get("params", {}) if isinstance(expected, dict) else {}
    for key in ("alpha", "beta", "L", "n_units"):
        if isinstance(params, dict) and params.get(key) != expected_params.get(key):
            failures.append(f"run spec 参数 {key} 不一致")
    expected_budget = expected.get("budget") if isinstance(expected, dict) else None
    if expected_budget is not None and isinstance(settings, dict) and settings.get("nsweeps") != expected_budget:
        failures.append("run spec budget 与 nsweeps 不一致")
    if not isinstance(settings, dict) or not isinstance(settings.get("q_count"), int) or settings.get("q_count", 0) < 401 or settings.get("sectors") != ["Sz=0", "Sz=1"]:
        failures.append("父 manifest: q_count<401 或 Sz 扇区定义错误")
    acceptance = parent.get("acceptance", {})
    for key in ("children_completed", "children_accepted", "finite_pi_ratio", "finite_q_peak", "finite_peak", "finite_peak_ratio"):
        true(acceptance, key, failures, "父 manifest")
    observables = parent.get("observables", {})
    for key in ("structure_factor_peak_q_over_pi", "dominant_structure_factor_ratio"):
        item = observables.get(key) if isinstance(observables, dict) else None
        value = number(item.get("value") if isinstance(item, dict) else None, f"主导诊断 {key}", failures)
        if key.endswith("q_over_pi") and not 0.0 <= value <= 1.0:
            failures.append("主导动量不在 [0,pi]")
    provenance = parent.get("provenance", {})
    if not isinstance(provenance, dict):
        provenance = {}
        failures.append("父 manifest: provenance 缺失")
    for key in ("standard_sha256", "manifest_sha256"):
        value = provenance.get(key)
        if not isinstance(value, str) or HASH_RE.fullmatch(value) is None:
            failures.append(f"父 manifest: {key} 缺失或非法")
        expected_value = expected_hash(spec, key)
        if expected_value is not None and value != expected_value:
            failures.append(f"run spec: {key} 不一致")
    valid_hashes(provenance.get("code_sha256"), "父 manifest", failures)
    child_manifests = (parent.get("diagnostics") or {}).get("child_manifests", [])
    expected_modes = settings.get("init_modes", []) if isinstance(settings, dict) else []
    children: list[dict[str, Any]] = []
    if (
        not isinstance(expected_modes, list) or len(expected_modes) < 2
        or len(set(expected_modes)) != len(expected_modes)
    ):
        failures.append("父 manifest: init_modes 必须包含至少两个互异初态")
        expected_modes = []
    expected_paths = [f"start_{mode}/manifest.json" for mode in expected_modes]
    if not isinstance(child_manifests, list) or child_manifests != expected_paths:
        failures.append("父 manifest: 子 manifest 与 init_modes 不一致")
    else:
        for relative in child_manifests:
            if not isinstance(relative, str):
                failures.append("父 manifest: 子 manifest 路径非法")
                continue
            child_path = (run / relative).parent.resolve()
            try:
                child_path.relative_to(run)
            except ValueError:
                failures.append("父 manifest: 子 manifest 路径越界")
                continue
            children.append(validate_child(parent, child_path, child_path.name.removeprefix("start_"), failures))
    for child in children:
        child_provenance = child.get("provenance", {})
        if not isinstance(child_provenance, dict):
            failures.append("子 manifest: provenance 缺失")
            continue
        for key in ("standard_sha256", "manifest_sha256"):
            if child_provenance.get(key) != provenance.get(key):
                failures.append(f"子 manifest: {key} 与父 cell 不一致")
    return {
        "schema_version": 1, "status": "pass" if not failures else "fail", "run_dir": str(run),
        "run_spec": str(spec_path), "cell_id": identifier, "checks": {
            "unique_run_spec_cell": bool(expected), "terminal_acceptance": parent.get("accepted") is True and status.get("accepted") is True,
            "negative_alpha_range": -1.0 <= alpha < 0.0, "beta_range": 0.0 <= beta <= 1.0,
            "parent_checksums": not checksum_ok(run), "children": len(children) == len(expected_modes) and len(children) >= 2,
        }, "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--run-spec", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = under_results(Path(args.output))
    result = validate(Path(args.run_dir), Path(args.run_spec))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
