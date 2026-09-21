#!/usr/bin/env python3
"""比较同一点 k=8 与 k=12；结果永远只标记为 audit_only。"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any


BASELINE_KRYLOV = 8
CANDIDATE_KRYLOV = 12
KRYLOV_FIELD = "eigsolve_krylovdim"
STARTS = ("center", "ferro_j2")
POINT_FIELDS = ("alpha", "beta", "L", "n_units")
SECTORS = ("sz0", "sz1")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON 顶层必须是对象：{path}")
    return value


def finite(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label} 必须是有限实数")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} 必须是有限实数") from error
    if not math.isfinite(number):
        raise ValueError(f"{label} 必须是有限实数")
    return number


def _relative_delta(old: float, new: float) -> float | None:
    denominator = abs(old) + abs(new)
    return None if denominator == 0.0 else 2.0 * (new - old) / denominator


def _value(observables: dict[str, Any], name: str, label: str) -> float:
    value = observables.get(name)
    if isinstance(value, dict):
        value = value.get("value")
    return finite(value, label)


def _read_metrics(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {str(row["metric"]): row["value"] for row in rows if row.get("metric") is not None and row.get("value") is not None}


def _metric(manifest: dict[str, Any], child: Path, section: str, name: str) -> float:
    source = manifest.get(section)
    if isinstance(source, dict) and name in source:
        return finite(source[name], f"{child}/{section}.{name}")
    metrics = _read_metrics(child / "metrics.csv")
    if name in metrics:
        return finite(metrics[name], f"{child}/metrics.{name}")
    raise ValueError(f"{child}: 缺少 {section}.{name}")


def _load_profile(child: Path, length: int, label: str) -> dict[int, dict[str, float | None]]:
    path = child / "entropy_profile_full.csv"
    if not path.is_file():
        raise ValueError(f"{label}: 缺少 entropy_profile_full.csv")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or ())
        if not {"bond", "entropy"}.issubset(fields):
            raise ValueError(f"{label}: entropy profile 缺字段")
        result: dict[int, dict[str, float | None]] = {}
        for row in reader:
            try:
                bond = int(row["bond"])
            except (TypeError, ValueError) as error:
                raise ValueError(f"{label}: bond 不是整数") from error
            if bond in result or not 1 <= bond < length:
                raise ValueError(f"{label}: bond 不完整或重复：{bond}")
            log_chord = None
            if row.get("log_chord") not in (None, ""):
                log_chord = finite(row["log_chord"], f"{label}.log_chord[{bond}]")
            result[bond] = {"entropy": finite(row["entropy"], f"{label}.entropy[{bond}]"), "log_chord": log_chord}
    expected = set(range(1, length))
    if set(result) != expected:
        raise ValueError(f"{label}: entropy profile bond 集合不完整")
    return result


def _point(manifest: dict[str, Any], label: str) -> dict[str, Any]:
    params = manifest.get("params")
    if not isinstance(params, dict):
        raise ValueError(f"{label}: 缺少 params")
    result: dict[str, Any] = {}
    for field in POINT_FIELDS:
        if field not in params:
            raise ValueError(f"{label}: 缺少 params.{field}")
        result[field] = finite(params[field], f"{label}.params.{field}") if field in ("alpha", "beta") else params[field]
    if type(result["L"]) is not int or type(result["n_units"]) is not int:
        raise ValueError(f"{label}: L/n_units 必须是整数")
    if result["L"] <= 1 or result["n_units"] <= 0:
        raise ValueError(f"{label}: L/n_units 范围错误")
    return result


def _krylov(manifest: dict[str, Any], expected: int, label: str) -> int:
    settings = manifest.get("settings")
    value = settings.get(KRYLOV_FIELD) if isinstance(settings, dict) else None
    if type(value) is not int or value != expected:
        raise ValueError(f"{label}: {KRYLOV_FIELD} 必须严格为 {expected}")
    return value


def _load_run(root: Path, expected: int, label: str) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, Any]]:
    parent = load_json(root / "manifest.json")
    point = _point(parent, label)
    _krylov(parent, expected, f"{label}.parent")
    children: dict[str, dict[str, Any]] = {}
    for mode in STARTS:
        child = load_json(root / f"start_{mode}" / "manifest.json")
        child_point = _point(child, f"{label}.{mode}")
        if child_point != point:
            raise ValueError(f"{label}.{mode}: 物理点与 parent 不一致")
        _krylov(child, expected, f"{label}.{mode}")
        children[mode] = child
    return parent, children, point


def _row(start: str, observable: str, index: int, old: float, new: float) -> dict[str, Any]:
    signed = new - old
    return {
        "start": start,
        "observable": observable,
        "index": index,
        "baseline_k8": old,
        "candidate_k12": new,
        "signed_delta": signed,
        "abs_delta": abs(signed),
        "symmetric_relative_delta": _relative_delta(old, new),
    }


def compare_runs(k8_run: Path, k12_run: Path) -> dict[str, Any]:
    """校验 k8→k12 合同并比较所有指定观测量。"""
    old_root = Path(k8_run).resolve()
    new_root = Path(k12_run).resolve()
    old_parent, old_children, old_point = _load_run(old_root, BASELINE_KRYLOV, "k8")
    new_parent, new_children, new_point = _load_run(new_root, CANDIDATE_KRYLOV, "k12")
    if old_point != new_point:
        raise ValueError(f"k8/k12 不是同一物理点：{old_point} != {new_point}")

    comparisons: dict[str, Any] = {}
    records: list[dict[str, Any]] = []
    for mode in STARTS:
        old_child, new_child = old_children[mode], new_children[mode]
        old_obs = old_child.get("observables") or {}
        new_obs = new_child.get("observables") or {}
        old_diag = old_child.get("diagnostics") or {}
        new_diag = new_child.get("diagnostics") or {}
        mode_block: dict[str, Any] = {}

        scalar_specs = (
            ("gap", "spin_gap", "observables"),
            ("q_peak_over_pi", "structure_factor_peak_q_over_pi", "observables"),
            ("dominant_ratio", "dominant_structure_factor_ratio", "observables"),
        )
        for output_name, source_name, section in scalar_specs:
            old_value = _value(old_obs, source_name, f"k8.{mode}.{source_name}")
            new_value = _value(new_obs, source_name, f"k12.{mode}.{source_name}")
            item = _row(mode, output_name, 0, old_value, new_value)
            mode_block[output_name] = item
            records.append(item)

        maxdim: dict[str, Any] = {}
        energy: dict[str, Any] = {}
        for sector in SECTORS:
            maxdim_name = f"actual_maxdim_{sector}"
            energy_name = f"final_energy_change_{sector}"
            maxdim[sector] = _row(mode, maxdim_name, 0, _metric(old_child, old_root / f"start_{mode}", "diagnostics", maxdim_name), _metric(new_child, new_root / f"start_{mode}", "diagnostics", maxdim_name))
            energy[sector] = _row(mode, energy_name, 0, _metric(old_child, old_root / f"start_{mode}", "diagnostics", energy_name), _metric(new_child, new_root / f"start_{mode}", "diagnostics", energy_name))
            records.extend((maxdim[sector], energy[sector]))
        mode_block["actual_maxdim"] = maxdim
        mode_block["energy_change"] = energy

        old_profile = _load_profile(old_root / f"start_{mode}", old_point["L"], f"k8.{mode}")
        new_profile = _load_profile(new_root / f"start_{mode}", new_point["L"], f"k12.{mode}")
        entropy_rows = []
        for bond in sorted(old_profile):
            item = _row(mode, "entropy", bond, float(old_profile[bond]["entropy"]), float(new_profile[bond]["entropy"]))
            item["baseline_log_chord"] = old_profile[bond]["log_chord"]
            item["candidate_log_chord"] = new_profile[bond]["log_chord"]
            entropy_rows.append(item)
            records.append(item)
        mode_block["entropy_profile"] = entropy_rows
        comparisons[mode] = mode_block

    return {
        "schema_version": 1,
        "status": "audit_only",
        "claim": "none",
        "audit_only": True,
        "krylov_change": {"baseline": BASELINE_KRYLOV, "candidate": CANDIDATE_KRYLOV},
        "point": old_point,
        "baseline_run": str(old_root),
        "candidate_run": str(new_root),
        "comparison_count": len(records),
        "comparisons": comparisons,
        "records": records,
    }


compare = compare_runs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k8-run", type=Path, required=True)
    parser.add_argument("--k12-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare_runs(args.k8_run, args.k12_run)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "comparison_count": result["comparison_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
