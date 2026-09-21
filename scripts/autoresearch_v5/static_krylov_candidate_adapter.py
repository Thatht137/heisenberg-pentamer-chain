#!/usr/bin/env python3
"""把 legacy=3 与 candidate=8 结果接到只读 audit comparator。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from closeout_negative_size_comparison import connected_quarter, dimer_rms
from compare_static_krylov_controls import compare_records
from static_krylov_control_inputs import KNOWN_LEGACY_DEFAULT3
from validate_negative_phase_run_practical_v2 import validate as practical_validate


ROOT = Path(__file__).resolve().parents[2]
BASELINE_DEFAULT = ROOT / "results/autoresearch_v5_20260919/static_krylov_baseline_v2"
BASELINE_RUN_SPEC_DEFAULT = ROOT / "results/autoresearch_v5_20260913/negative_phase_independent_pilot_r1/parameter-scan.run_spec.json"
CANDIDATE_DEFAULT = ROOT / "results/autoresearch_v5_20260919/static_krylov_controls_r1"
CANDIDATE_RUN_SPEC_DEFAULT = CANDIDATE_DEFAULT / "parameter-scan.run_spec.json"

POINTS = {
    "negdiag-a01000-b02500-L080": {
        "candidate_id": "negdiag-a01000-b02500-L080-k08",
        "alpha": -0.1,
        "beta": 0.25,
        "L": 80,
        "n_units": 16,
    },
    "negdiag-a01750-b02500-L080": {
        "candidate_id": "negdiag-a01750-b02500-L080-k08",
        "alpha": -0.175,
        "beta": 0.25,
        "L": 80,
        "n_units": 16,
    },
}
STARTS = ("center", "ferro_j2")
REQUIRED_PARENT_FILES = ("manifest.json", "status.json", "checksums.sha256")
REQUIRED_CHILD_FILES = (
    "manifest.json",
    "status.json",
    "checksums.sha256",
    "metrics.csv",
    "state_sz0.jld2",
    "entropy_profile_full.csv",
    "bond_correlations.csv",
    "bond_bond_connected.csv",
)
CHECKSUM_PARENT_FILES = tuple(name for name in REQUIRED_PARENT_FILES if name != "checksums.sha256")
CHECKSUM_CHILD_FILES = tuple(name for name in REQUIRED_CHILD_FILES if name != "checksums.sha256")
EXPECTED_SWEEPS = 64
STATE_NORM_TOL = 1e-8
SECTOR_TOL = 1e-8
REQUIRED_METRICS = (
    "energy_sz0",
    "energy_sz1",
    "total_sz0",
    "total_sz1",
    "state_norm_sz0",
    "state_norm_sz1",
    "nsweeps_completed_sz0",
    "nsweeps_completed_sz1",
)
PROTOCOL_FIELDS = (
    "sectors",
    "nsweeps",
    "maxdim",
    "cutoff",
    "threads",
    "q_count",
    "init_modes",
    "noise_profile",
    "random_seed",
    "variance_per_site_max",
    "save_state",
    "enriched_diagnostics",
    "eigsolve_maxiter",
    "eigsolve_tol",
    "eigsolve_krylovdim",
)


class AdapterError(ValueError):
    """输入完整性或固定协议不满足。"""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise AdapterError(f"缺少 JSON：{path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AdapterError(f"JSON 顶层不是对象：{path}")
    return value


def strict_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return set(left) == set(right) and all(strict_equal(left[key], right[key]) for key in left)
    if isinstance(left, (list, tuple)):
        return len(left) == len(right) and all(strict_equal(a, b) for a, b in zip(left, right))
    return left == right


def strict_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or type(value) is not int:
        raise AdapterError(f"{label} 必须是整数，不能是 bool/浮点")
    return value


def require_krylov(value: Any, expected: int, label: str) -> int:
    parsed = strict_int(value, label)
    if parsed != expected:
        raise AdapterError(f"{label}={parsed}，期望 {expected}")
    return parsed


def finite(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise AdapterError(f"{label} 不是数值") from error
    if not math.isfinite(number):
        raise AdapterError(f"{label} 非有限")
    return number


def checksum_failures(directory: Path, required: Iterable[str] = ()) -> list[str]:
    checksum = directory / "checksums.sha256"
    if not checksum.is_file():
        return [f"{directory}: 缺少 checksums.sha256"]
    failures: list[str] = []
    seen: set[str] = set()
    for line in checksum.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            expected, relative = line.split(maxsplit=1)
        except ValueError:
            failures.append(f"{directory}: checksum 行格式错误")
            continue
        relative_name = relative.strip().lstrip("*")
        normalized_name = Path(relative_name).as_posix()
        seen.add(normalized_name)
        target = (directory / relative_name).resolve()
        try:
            target.relative_to(directory.resolve())
        except ValueError:
            failures.append(f"{directory}: checksum 路径越界")
            continue
        if not target.is_file() or sha256(target) != expected:
            failures.append(f"{directory}: checksum 失败 {relative}")
    for name in required:
        if Path(name).as_posix() not in seen:
            failures.append(f"{directory}: checksum 未覆盖 {name}")
    return failures


def missing_files(directory: Path, names: Iterable[str]) -> list[str]:
    return [str(directory / name) for name in names if not (directory / name).is_file()]


def artifact_hashes(directory: Path, names: Iterable[str]) -> dict[str, str]:
    """记录已验收文件的实际哈希，代码来源与产物来源分开。"""
    return {name: sha256(directory / name) for name in names}


def read_csv(path: Path, required: Iterable[str]) -> list[dict[str, str]]:
    if not path.is_file():
        raise AdapterError(f"缺少 CSV：{path}")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or ())
        missing = sorted(set(required) - fields)
        if missing:
            raise AdapterError(f"{path.name} 缺字段：{missing}")
        rows = list(reader)
    if not rows:
        raise AdapterError(f"CSV 为空：{path}")
    return rows


def read_metrics(path: Path) -> dict[str, Any]:
    rows = read_csv(path, ("metric", "value"))
    values: dict[str, Any] = {}
    for row in rows:
        name = row["metric"]
        if name in values:
            raise AdapterError(f"metrics 重复字段：{name}")
        values[name] = row["value"]
    for name in REQUIRED_METRICS:
        if name not in values:
            raise AdapterError(f"metrics 缺少实际扇区字段：{name}")
        finite(values[name], f"metrics.{name}")
    for name in ("state_norm_sz0", "state_norm_sz1"):
        if abs(finite(values[name], f"metrics.{name}") - 1.0) > STATE_NORM_TOL:
            raise AdapterError(f"metrics.{name} 不满足归一化门")
    for name, expected in (("total_sz0", 0.0), ("total_sz1", 1.0)):
        if abs(finite(values[name], f"metrics.{name}") - expected) > SECTOR_TOL:
            raise AdapterError(f"metrics.{name} 不满足 Sz 扇区门")
    for name in ("nsweeps_completed_sz0", "nsweeps_completed_sz1"):
        if finite(values[name], f"metrics.{name}") != EXPECTED_SWEEPS:
            raise AdapterError(f"metrics.{name} 不等于 {EXPECTED_SWEEPS}")
    return values


def _metadata(settings: Mapping[str, Any], params: Mapping[str, Any], krylov: int) -> dict[str, Any]:
    length = strict_int(params["L"], "L")
    maxdim_by_l = settings.get("maxdim_by_L")
    if isinstance(maxdim_by_l, dict):
        maxdim = maxdim_by_l.get(str(length))
    else:
        maxdim = settings.get("maxdim")
    if maxdim is None:
        raise AdapterError("settings 缺少 maxdim")
    return {
        "alpha": float(params["alpha"]),
        "beta": float(params["beta"]),
        "L": length,
        "n_units": strict_int(params["n_units"], "n_units"),
        "sectors": settings.get("sectors"),
        "nsweeps": strict_int(settings.get("nsweeps"), "nsweeps"),
        "maxdim": strict_int(maxdim, "maxdim"),
        "cutoff": float(settings.get("cutoff")),
        "threads": strict_int(settings.get("threads"), "threads"),
        "q_count": strict_int(settings.get("q_count"), "q_count"),
        "init_modes": settings.get("init_modes"),
        "noise_profile": settings.get("noise_profile", "legacy"),
        "random_seed": strict_int(settings.get("random_seed", 20260811), "random_seed"),
        "variance_per_site_max": float(settings.get("variance_per_site_max")),
        "save_state": settings.get("save_state"),
        "enriched_diagnostics": settings.get("enriched_diagnostics"),
        "eigsolve_maxiter": strict_int(settings.get("eigsolve_maxiter", 1), "eigsolve_maxiter"),
        "eigsolve_tol": float(settings.get("eigsolve_tol", 1e-14)),
        "eigsolve_krylovdim": krylov,
    }


def _manifest_settings(manifest: Mapping[str, Any], mode: str | None = None) -> dict[str, Any]:
    settings = manifest.get("settings")
    if not isinstance(settings, dict):
        raise AdapterError("manifest 缺少 settings")
    actual = dict(settings)
    if mode is not None:
        actual["init_modes"] = [settings.get("init_mode_sz0"), settings.get("init_mode_sz1")]
    return actual


def validate_fixed_settings(
    manifest: Mapping[str, Any],
    expected: Mapping[str, Any],
    label: str,
    mode: str | None = None,
) -> None:
    actual = _manifest_settings(manifest, mode)
    for field in PROTOCOL_FIELDS:
        if field not in actual:
            raise AdapterError(f"{label}: settings 缺少 {field}")
        if field == "eigsolve_krylovdim":
            require_krylov(actual[field], 8, f"{label}.{field}")
        elif field == "eigsolve_maxiter":
            if strict_int(actual[field], f"{label}.{field}") != expected[field]:
                raise AdapterError(f"{label}.{field} 与固定 settings 不一致")
        elif not strict_equal(actual[field], expected[field]):
            raise AdapterError(f"{label}.{field} 与固定 settings 不一致")


def record(alpha: float, beta: float, length: int, start: str, observable: str, index: int, value: Any) -> dict[str, Any]:
    return {
        "alpha": alpha,
        "beta": beta,
        "L": length,
        "start": start,
        "observable": observable,
        "index": strict_int(index, "record.index"),
        "value": finite(value, f"record.{observable}.{index}"),
    }


def _point_from_params(params: Mapping[str, Any]) -> tuple[float, float, int, int]:
    return (float(params["alpha"]), float(params["beta"]), strict_int(params["L"], "L"), strict_int(params["n_units"], "n_units"))


def _records_from_inventory(inventory: Mapping[str, Any], point_id: str, point: Mapping[str, Any]) -> list[dict[str, Any]]:
    tables = inventory.get("tables")
    if not isinstance(tables, dict):
        raise AdapterError("baseline inventory 缺少 tables；请使用 baseline_inventory.json 的同目录 CSV")
    alpha, beta, length = float(point["alpha"]), float(point["beta"]), strict_int(point["L"], "baseline L")
    records: list[dict[str, Any]] = []
    def rows(name: str) -> list[dict[str, Any]]:
        value = tables.get(name)
        if not isinstance(value, list):
            raise AdapterError(f"baseline inventory 缺少表：{name}")
        return [row for row in value if row.get("cell_id") == point_id]
    for row in rows("gaps"):
        records.append(record(alpha, beta, length, str(row["start"]), "gap", 0, row["gap"]))
    for row in rows("entropy"):
        records.append(record(alpha, beta, length, str(row["start"]), "entropy", strict_int(int(row["bond"]), "bond"), row["entropy"]))
    for row in rows("bond_correlations"):
        records.append(record(alpha, beta, length, str(row["start"]), "bond_correlation", strict_int(int(row["bond"]), "bond"), row["correlation"]))
    for row in rows("connected_quarter"):
        index = int(row["reference_bond"]) * 1000 + int(row["target_bond"])
        records.append(record(alpha, beta, length, str(row["start"]), "connected_quarter", index, row["staggered_connected"]))
    for row in rows("dimer"):
        records.append(record(alpha, beta, length, str(row["start"]), "dimer_rms", 0, row["dimer_rms"]))
    if not records:
        raise AdapterError(f"baseline {point_id} 没有可比较 records")
    return records


def _candidate_records(child: Path, point: Mapping[str, Any], mode: str) -> list[dict[str, Any]]:
    alpha, beta, length = float(point["alpha"]), float(point["beta"]), strict_int(point["L"], "candidate L")
    child_manifest = load_json(child / "manifest.json")
    observed = child_manifest.get("observables") or {}
    if "spin_gap" not in observed:
        raise AdapterError(f"{child}: 缺少 spin_gap observable")
    records = [record(alpha, beta, length, mode, "gap", 0, observed["spin_gap"])]
    entropy = read_csv(child / "entropy_profile_full.csv", ("bond", "bond_class", "log_chord", "entropy"))
    bonds = read_csv(child / "bond_correlations.csv", ("bond", "left_site", "right_site", "bond_class", "correlation"))
    connected_raw = read_csv(child / "bond_bond_connected.csv", ("bond_class", "reference_bond", "target_bond", "distance_units", "connected"))
    if len(entropy) != length - 1 or {int(row["bond"]) for row in entropy} != set(range(1, length)):
        raise AdapterError(f"{child}: entropy 键不完整")
    if len(bonds) != length - 1 or {int(row["bond"]) for row in bonds} != set(range(1, length)):
        raise AdapterError(f"{child}: bond correlation 不完整")
    for row in entropy:
        records.append(record(alpha, beta, length, mode, "entropy", int(row["bond"]), row["entropy"]))
    for row in bonds:
        records.append(record(alpha, beta, length, mode, "bond_correlation", int(row["bond"]), row["correlation"]))
    connected = []
    for row in connected_raw:
        item = dict(row)
        item["distance_over_units"] = float(row["distance_units"]) / (length / 5)
        item["distance_units"] = float(row["distance_units"])
        item["reference_bond"] = int(row["reference_bond"])
        item["target_bond"] = int(row["target_bond"])
        item["bond_class"] = int(row["bond_class"])
        item["connected"] = float(row["connected"])
        connected.append(item)
    quarter = connected_quarter(connected, length)
    selected = [row for row in connected if row["bond_class"] == 0 and row["distance_units"] == length // 20]
    for row, value in zip(selected, quarter):
        index = row["reference_bond"] * 1000 + row["target_bond"]
        records.append(record(alpha, beta, length, mode, "connected_quarter", index, value))
    dimer_rows = [{"bond": int(row["bond"]), "correlation": float(row["correlation"])} for row in bonds]
    dimer, _ = dimer_rms(dimer_rows, length)
    records.append(record(alpha, beta, length, mode, "dimer_rms", 0, dimer))
    return records


def validate_run_spec(run_spec: Mapping[str, Any], expected_settings: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    settings = run_spec.get("settings")
    if not isinstance(settings, dict):
        raise AdapterError("candidate run-spec 缺少 settings")
    if settings.get("sectors") != ["Sz=0", "Sz=1"] or settings.get("nsweeps") != 64:
        raise AdapterError("candidate run-spec 扇区或 sweeps 不符合协议")
    if settings.get("maxdim_by_L", {}).get("80") != 1200 or float(settings.get("cutoff")) != 1e-11:
        raise AdapterError("candidate run-spec maxdim/cutoff 不符合协议")
    if settings.get("init_modes") != ["center", "ferro_j2"] or settings.get("noise_profile") != "legacy":
        raise AdapterError("candidate run-spec 初态/noise 不符合协议")
    if settings.get("save_state") is not True or settings.get("enriched_diagnostics") is not True:
        raise AdapterError("candidate run-spec 缺保存态或增强观测")
    if settings.get("warmstart") is not False or settings.get("retry_policy") != "none" or settings.get("maxdim_escalation") is not False:
        raise AdapterError("candidate run-spec warmstart/retry/maxdim escalation 漂移")
    require_krylov(settings.get("eigsolve_krylovdim"), 8, "candidate run-spec eigsolve_krylovdim")
    if strict_int(settings.get("eigsolve_maxiter"), "candidate run-spec eigsolve_maxiter") != 1:
        raise AdapterError("candidate run-spec maxiter 不符合协议")
    cells: dict[str, dict[str, Any]] = {}
    for cell in run_spec.get("cells", []):
        cell_id = cell.get("cell_id")
        if cell_id in cells:
            raise AdapterError(f"candidate run-spec cell 重复：{cell_id}")
        if cell_id not in {point["candidate_id"] for point in POINTS.values()}:
            raise AdapterError(f"candidate run-spec cell 未登记：{cell_id}")
        params = cell.get("params") or {}
        expected = next(point for point in POINTS.values() if point["candidate_id"] == cell_id)
        for key in ("alpha", "beta", "L", "n_units"):
            if params.get(key) != expected[key]:
                raise AdapterError(f"{cell_id}.params.{key} 与固定物理点不一致")
        require_krylov(params.get("eigsolve_krylovdim"), 8, f"{cell_id}.params.eigsolve_krylovdim")
        if cell.get("budget") != 64:
            raise AdapterError(f"{cell_id}.budget 不符合 64 sweeps 协议")
        cells[cell_id] = {"params": params, "budget": cell.get("budget")}
    if set(cells) != {point["candidate_id"] for point in POINTS.values()}:
        raise AdapterError("candidate run-spec 两个 cell 不完整")
    if expected_settings:
        actual_protocol = {
            field: (settings.get("maxdim_by_L", {}).get("80") if field == "maxdim" else settings.get(field))
            for field in PROTOCOL_FIELDS
        }
        expected_protocol = {field: expected_settings[field] for field in PROTOCOL_FIELDS}
        if not strict_equal(actual_protocol, expected_protocol):
            raise AdapterError("candidate run-spec fixed settings 漂移")
    return cells


def _verify_baseline_manifest(directory: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = load_json(directory / "manifest.json")
    inventory = load_json(directory / "baseline_inventory.json")
    for item in [manifest.get("baseline_inventory"), *manifest.get("measurement_files", []), manifest.get("source_hashes")]:
        if not isinstance(item, dict) or not item.get("name"):
            raise AdapterError("baseline manifest artifact 声明不完整")
        path = directory / str(item["name"])
        if not path.is_file() or sha256(path) != item.get("sha256"):
            raise AdapterError(f"baseline artifact hash 失败：{path}")
    if inventory.get("status") != "baseline_verified_candidate_missing":
        raise AdapterError("baseline inventory 状态不是已验收 candidate_missing")
    return manifest, inventory


def load_baseline_dataset(inventory_dir: Path, run_spec_path: Path) -> dict[str, Any]:
    _, inventory = _verify_baseline_manifest(inventory_dir)
    points = inventory.get("points")
    if not isinstance(points, list) or len(points) != len(POINTS) or {p.get("cell_id") for p in points} != set(POINTS):
        raise AdapterError("baseline inventory 两个物理点不完整")
    for point in points:
        krylov = point.get("krylov") or {}
        require_krylov(krylov.get("value"), 3, f"baseline {point.get('cell_id')} krylov")
        source_hashes = set(krylov.get("source_hashes") or [])
        if not source_hashes or not source_hashes.issubset(KNOWN_LEGACY_DEFAULT3):
            raise AdapterError(f"baseline {point.get('cell_id')} 不是已登记 legacy=3 来源")
    spec = load_json(run_spec_path)
    settings = spec.get("settings") or {}
    tables: dict[str, list[dict[str, Any]]] = {}
    for name in ("gap_records.csv", "entropy_records.csv", "bond_correlations.csv", "connected_quarter.csv", "dimer_rms.csv"):
        with (inventory_dir / name).open(encoding="utf-8", newline="") as handle:
            tables[name] = list(csv.DictReader(handle))
    normalized = {}
    metadata = {}
    for point_id, point_def in POINTS.items():
        point = next(item for item in points if item.get("cell_id") == point_id)
        params = point["params"]
        baseline_params = {"alpha": params["alpha"], "beta": params["beta"], "L": params["L"], "n_units": params["n_units"]}
        metadata[point_id] = _metadata(settings, baseline_params, 3)
        compact = {"tables": {"gaps": [row for row in tables["gap_records.csv"] if row.get("cell_id") == point_id], "entropy": [row for row in tables["entropy_records.csv"] if row.get("cell_id") == point_id], "bond_correlations": [row for row in tables["bond_correlations.csv"] if row.get("cell_id") == point_id], "connected_quarter": [row for row in tables["connected_quarter.csv"] if row.get("cell_id") == point_id], "dimer": [row for row in tables["dimer_rms.csv"] if row.get("cell_id") == point_id]}}
        normalized[point_id] = _records_from_inventory(compact, point_id, point_def | baseline_params)
    return {
        "status": "baseline_verified",
        "points": normalized,
        "metadata": metadata,
        "provenance": {"inventory_dir": str(inventory_dir.resolve()), "inventory_manifest_sha256": sha256(inventory_dir / "manifest.json"), "source_records": inventory.get("source_records", [])},
    }


def extract_candidate_dataset(
    candidate_dir: Path,
    run_spec_path: Path,
    validator: Callable[[Path, Path], dict[str, Any]] = practical_validate,
) -> dict[str, Any]:
    if not candidate_dir.exists() or not (candidate_dir / "cells").is_dir():
        return {"status": "candidate_missing", "failures": [f"缺少 candidate cells：{candidate_dir}"], "points": {}, "provenance": {}}
    try:
        run_spec = load_json(run_spec_path)
        settings = run_spec.get("settings") or {}
        expected_settings = _metadata(settings, {"alpha": -0.1, "beta": 0.25, "L": 80, "n_units": 16}, 8)
        cells = validate_run_spec(run_spec, expected_settings)
    except Exception as error:
        return {"status": "not_evaluable", "failures": [str(error)], "points": {}, "provenance": {}}
    failures: list[str] = []
    points: dict[str, dict[str, Any]] = {}
    provenance: dict[str, Any] = {"run_spec": {"path": str(run_spec_path.resolve()), "sha256": sha256(run_spec_path)}, "cells": {}}
    for baseline_id, point in POINTS.items():
        candidate_id = point["candidate_id"]
        cell_dir = candidate_dir / "cells" / candidate_id
        if not cell_dir.is_dir():
            failures.append(f"{candidate_id}: 缺少 cell")
            continue
        cell_failures: list[str] = checksum_failures(cell_dir, CHECKSUM_PARENT_FILES) + [f"{candidate_id}: 缺文件 {name}" for name in missing_files(cell_dir, REQUIRED_PARENT_FILES)]
        try:
            parent = load_json(cell_dir / "manifest.json")
            parent_status = load_json(cell_dir / "status.json")
            params = parent.get("params") or {}
            for key in ("alpha", "beta", "L", "n_units"):
                if params.get(key) != point[key]:
                    raise AdapterError(f"{candidate_id}: parent 参数 {key} 漂移")
            validate_fixed_settings(parent, _metadata(settings, point, 8), f"{candidate_id}:parent")
            if parent.get("status") != "success" or parent_status.get("status") != "success" or parent.get("accepted") is not True:
                raise AdapterError(f"{candidate_id}: parent 未 accepted")
            validation = validator(cell_dir, run_spec_path)
            if validation.get("status") != "pass" or validation.get("failures"):
                raise AdapterError(f"{candidate_id}: PracticalV2 未通过：{validation.get('failures', [])}")
            records: list[dict[str, Any]] = []
            cell_provenance = {
                "practical_v2": {
                    "status": validation.get("status"),
                    "acceptance_label": validation.get("acceptance_label"),
                    "failures": validation.get("failures", []),
                },
                "parent": {
                    "manifest": parent.get("provenance", {}),
                    "artifact_hashes": artifact_hashes(cell_dir, REQUIRED_PARENT_FILES),
                },
                "children": {},
            }
            for mode in STARTS:
                child = cell_dir / f"start_{mode}"
                child_failures = checksum_failures(child, CHECKSUM_CHILD_FILES) + [f"{candidate_id}:{mode}: 缺文件 {name}" for name in missing_files(child, REQUIRED_CHILD_FILES)]
                if child_failures:
                    raise AdapterError("；".join(child_failures))
                child_manifest = load_json(child / "manifest.json")
                child_status = load_json(child / "status.json")
                require_krylov((child_manifest.get("settings") or {}).get("eigsolve_krylovdim"), 8, f"{candidate_id}:{mode}.krylov")
                child_expected = _metadata(settings, point, 8)
                child_expected["init_modes"] = [mode, "center"]
                validate_fixed_settings(child_manifest, child_expected, f"{candidate_id}:{mode}", mode)
                child_params = child_manifest.get("params") or {}
                for key in ("alpha", "beta", "L", "n_units"):
                    if child_params.get(key) != point[key]:
                        raise AdapterError(f"{candidate_id}:{mode}: 参数 {key} 漂移")
                if child_manifest.get("status") != "success" or child_status.get("status") != "success" or child_manifest.get("accepted") is not True:
                    raise AdapterError(f"{candidate_id}:{mode}: child 未 accepted")
                read_metrics(child / "metrics.csv")
                records.extend(_candidate_records(child, point, mode))
                cell_provenance["children"][mode] = {
                    "manifest": child_manifest.get("provenance", {}),
                    "artifact_hashes": artifact_hashes(child, REQUIRED_CHILD_FILES),
                }
            points[baseline_id] = {"records": records, "metadata": _metadata(settings, point, 8)}
            provenance["cells"][candidate_id] = cell_provenance
        except Exception as error:
            failures.extend(cell_failures)
            failures.append(str(error))
    if failures:
        return {"status": "not_evaluable", "failures": sorted(set(failures)), "points": {}, "provenance": provenance}
    return {"status": "candidate_verified", "failures": [], "points": points, "provenance": provenance}


def audit(
    baseline_inventory: Path,
    baseline_run_spec: Path,
    candidate_dir: Path,
    candidate_run_spec: Path,
    validator: Callable[[Path, Path], dict[str, Any]] = practical_validate,
) -> dict[str, Any]:
    baseline = load_baseline_dataset(baseline_inventory, baseline_run_spec)
    candidate = extract_candidate_dataset(candidate_dir, candidate_run_spec, validator)
    result: dict[str, Any] = {
        "schema_version": 1,
        "status": candidate["status"] if candidate["status"] != "candidate_verified" else "audit_only",
        "audit_only": True,
        "claim": "none",
        "baseline": baseline["status"],
        "candidate": candidate["status"],
        "failures": candidate.get("failures", []),
        "baseline_provenance": baseline["provenance"],
        "candidate_provenance": candidate.get("provenance", {}),
        "comparisons": {},
    }
    if candidate["status"] != "candidate_verified":
        return result
    for point_id in POINTS:
        result["comparisons"][point_id] = compare_records(
            baseline["points"][point_id],
            candidate["points"][point_id]["records"],
            baseline["metadata"][point_id],
            candidate["points"][point_id]["metadata"],
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-inventory", type=Path, default=BASELINE_DEFAULT)
    parser.add_argument("--baseline-run-spec", type=Path, default=BASELINE_RUN_SPEC_DEFAULT)
    parser.add_argument("--candidate-dir", type=Path, default=CANDIDATE_DEFAULT)
    parser.add_argument("--candidate-run-spec", type=Path, default=CANDIDATE_RUN_SPEC_DEFAULT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="只输出状态，不写结果文件")
    args = parser.parse_args()
    result = audit(args.baseline_inventory, args.baseline_run_spec, args.candidate_dir, args.candidate_run_spec)
    summary = {"status": result["status"], "candidate": result["candidate"], "failures": result["failures"], "comparison_points": len(result["comparisons"])}
    print(json.dumps(summary, ensure_ascii=False))
    if args.output is not None and not args.dry_run:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
