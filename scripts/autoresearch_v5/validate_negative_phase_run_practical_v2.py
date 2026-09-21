#!/usr/bin/env python3
"""按 V2 实用门独立验收负 alpha 双初态 cell。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


VARIANCE_MAX = 5e-8
TRUNCATION_MAX = 1e-9
SECTOR_TOL = 1e-8
GAP_MIN = -1e-8
Q_COUNT_MIN = 401


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def checksum_failures(run: Path) -> list[str]:
    source = run / "checksums.sha256"
    if not source.is_file():
        return [f"{run.name}: 缺少 checksums.sha256"]
    failures = []
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, relative = line.split(maxsplit=1)
        target = (run / relative.strip().lstrip("*")).resolve()
        try:
            target.relative_to(run.resolve())
        except ValueError:
            failures.append(f"{run.name}: checksum 路径越界")
            continue
        if not target.is_file() or sha256(target) != digest:
            failures.append(f"{run.name}: checksum 失败 {relative}")
    return failures


def finite(value: object, label: str, failures: list[str]) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        failures.append(f"{label}: 缺少数值")
        return math.nan
    if not math.isfinite(number):
        failures.append(f"{label}: 非有限")
    return number


def fullq_ok(path: Path, expected: int, failures: list[str], label: str) -> None:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        if len(rows) != expected or expected < Q_COUNT_MIN:
            failures.append(f"{label}: full-q 点数错误")
        for row in rows:
            for key in ("q", "q_over_pi", "Sq"):
                finite(row.get(key), f"{label}: full-q {key}", failures)
    except (OSError, csv.Error):
        failures.append(f"{label}: full-q 不可读")


def validate_child(parent: dict, run: Path, mode: str) -> tuple[dict, list[str]]:
    failures = checksum_failures(run)
    manifest = load(run / "manifest.json")
    status = load(run / "status.json")
    label = f"{parent.get('cell_id')}:{mode}"
    if manifest.get("status") != "success" or manifest.get("returncode") != 0:
        failures.append(f"{label}: 计算未正常退出")
    if status.get("status") != "success" or status.get("returncode") != 0:
        failures.append(f"{label}: status 非 success")

    params = manifest.get("params") or {}
    for key in ("alpha", "beta", "L", "n_units"):
        if params.get(key) != (parent.get("params") or {}).get(key):
            failures.append(f"{label}: 参数 {key} 不一致")
    settings = manifest.get("settings") or {}
    parent_settings = parent.get("settings") or {}
    if settings.get("sectors") != ["Sz=0", "Sz=1"]:
        failures.append(f"{label}: 扇区错误")
    if settings.get("nsweeps") != parent_settings.get("nsweeps"):
        failures.append(f"{label}: sweeps 不一致")

    diagnostics = manifest.get("diagnostics") or {}
    values = {"mode": mode}
    for sector in ("sz0", "sz1"):
        variance = finite(diagnostics.get(f"variance_per_site_{sector}"), f"{label}: variance {sector}", failures)
        truncation = finite(diagnostics.get(f"final_truncation_error_{sector}"), f"{label}: truncation {sector}", failures)
        values[f"variance_per_site_{sector}"] = variance
        values[f"final_truncation_error_{sector}"] = truncation
        if variance > VARIANCE_MAX:
            failures.append(f"{label}: variance {sector} 超过 V2 门")
        if truncation > TRUNCATION_MAX:
            failures.append(f"{label}: truncation {sector} 超门")
    total0 = finite(diagnostics.get("total_sz0"), f"{label}: Sz0", failures)
    total1 = finite(diagnostics.get("total_sz1"), f"{label}: Sz1", failures)
    if abs(total0) > SECTOR_TOL or abs(total1 - 1.0) > SECTOR_TOL:
        failures.append(f"{label}: Sz 扇区超门")
    gap = finite((manifest.get("observables") or {}).get("spin_gap"), f"{label}: gap", failures)
    values.update({"total_sz0": total0, "total_sz1": total1, "spin_gap": gap})
    if gap < GAP_MIN:
        failures.append(f"{label}: 负 gap 超门")

    acceptance = manifest.get("acceptance") or {}
    for key in (
        "execution_success",
        "truncation_sz0_le_1e-9",
        "truncation_sz1_le_1e-9",
        "sz0_sector",
        "sz1_sector",
        "nonnegative_gap",
        "all_sweeps_completed",
        "fullq_file",
        "fullq_count",
        "measurement_files",
    ):
        if acceptance.get(key) is not True:
            failures.append(f"{label}: 原非方差门 {key} 未通过")
    q_count = int(settings.get("q_count", 0))
    fullq_ok(run / "structure_factor_fullq.csv", q_count, failures, label)
    return values, sorted(set(failures))


def validate(run: Path, run_spec: Path) -> dict:
    run = run.resolve()
    parent = load(run / "manifest.json")
    status = load(run / "status.json")
    spec = load(run_spec.resolve())
    failures = checksum_failures(run)
    identifier = parent.get("cell_id")
    matches = [cell for cell in spec.get("cells", []) if cell.get("cell_id") == identifier]
    if len(matches) != 1:
        failures.append("run spec: cell_id 不是唯一匹配")
        expected = {}
    else:
        expected = matches[0]
    for key in ("alpha", "beta", "L", "n_units"):
        if (parent.get("params") or {}).get(key) != (expected.get("params") or {}).get(key):
            failures.append(f"父 cell: 参数 {key} 与 run spec 不一致")
    settings = parent.get("settings") or {}
    if settings.get("nsweeps") != expected.get("budget"):
        failures.append("父 cell: sweep 预算与 run spec 不一致")
    if settings.get("sectors") != ["Sz=0", "Sz=1"] or int(settings.get("q_count", 0)) < Q_COUNT_MIN:
        failures.append("父 cell: 扇区或 q_count 错误")
    if status.get("returncode") not in (0, 1):
        failures.append("父 status: 非预期退出码")

    parent_acceptance = parent.get("acceptance") or {}
    for key in ("children_completed", "finite_pi_ratio", "finite_q_peak", "finite_peak", "finite_peak_ratio"):
        if parent_acceptance.get(key) is not True:
            failures.append(f"父 cell: {key} 未通过")
    if "energy_consistency" in parent_acceptance and parent_acceptance.get("energy_consistency") is not True:
        failures.append("父 cell: 多初态能量一致性未通过")
    for key in ("structure_factor_peak_q_over_pi", "dominant_structure_factor_ratio"):
        item = (parent.get("observables") or {}).get(key) or {}
        finite(item.get("value"), f"父 cell: {key}", failures)
        finite(item.get("error"), f"父 cell: {key} error", failures)

    child_values = []
    for mode in ("center", "ferro_j2"):
        values, child_failures = validate_child(parent, run / f"start_{mode}", mode)
        child_values.append(values)
        failures.extend(child_failures)

    accepted = not failures
    return {
        "schema_version": 2,
        "status": "pass" if accepted else "fail",
        "acceptance_label": "accepted_under_practical_v2" if accepted else "rejected_under_practical_v2",
        "run_dir": str(run),
        "cell_id": identifier,
        "params": parent.get("params"),
        "settings": {"nsweeps": settings.get("nsweeps"), "maxdim": settings.get("maxdim"), "q_count": settings.get("q_count")},
        "thresholds": {
            "variance_per_site_max": VARIANCE_MAX,
            "final_truncation_error_max": TRUNCATION_MAX,
            "sector_tolerance": SECTOR_TOL,
            "spin_gap_min": GAP_MIN,
        },
        "legacy_parent_accepted": parent.get("accepted") is True,
        "legacy_parent_status": parent.get("status"),
        "children": child_values,
        "failures": sorted(set(failures)),
        "provenance": {
            "policy": "docs/negative_alpha_practical_convergence_standard_20260829.md",
            "original_manifest_sha256": sha256(run / "manifest.json"),
            "original_run_spec_sha256": sha256(run_spec.resolve()),
            "original_files_unchanged": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--run-spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = validate(args.run_dir, args.run_spec)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "cell_id": result["cell_id"], "failures": result["failures"]}, ensure_ascii=False))
    raise SystemExit(0 if result["status"] == "pass" else 2)


if __name__ == "__main__":
    main()
