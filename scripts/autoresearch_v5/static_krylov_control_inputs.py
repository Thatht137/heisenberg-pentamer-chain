"""只读提取两个 L80 基线点，供 Krylov 对照使用。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
DEFAULT_RUN_SPEC = RESULTS / "autoresearch_v5_20260913" / "negative_phase_independent_pilot_r1" / "parameter-scan.run_spec.json"
DEFAULT_BASELINES = (
    RESULTS / "autoresearch_v5_20260913" / "negative_phase_independent_pilot_fetch_20260914_2243" / "negdiag-a01000-b02500-L080",
    RESULTS / "autoresearch_v5_20260913" / "negative_phase_independent_pilot_fetch_20260914_2243" / "negdiag-a01750-b02500-L080",
)
DEFAULT_OUT = RESULTS / "autoresearch_v5_20260919" / "static_krylov_baseline_v1"
EXPECTED_POINTS = {
    "negdiag-a01000-b02500-L080": (-0.1, 0.25, 80, 16),
    "negdiag-a01750-b02500-L080": (-0.175, 0.25, 80, 16),
}
KRYLOV_SOURCE = "scripts/autoresearch_v5/negative_static_cell.jl"
KNOWN_LEGACY_DEFAULT3 = {
    # 两个既有 L80 manifest 的明确历史代码哈希；不推广到未知来源。
    "0363dbd631f8ad01ce7e6b0b3cf1489b55a157c834ac56919e38876a2d831c29": 3,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"缺少 JSON：{path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"JSON 不可读：{path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON 顶层必须是对象：{path}")
    return value


def finite(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} 不是数值") from exc
    if not math.isfinite(number):
        raise ValueError(f"{label} 非有限")
    return number


def read_csv_rows(path: Path, required: Iterable[str]) -> list[dict[str, str]]:
    if not path.is_file():
        raise ValueError(f"缺少测量文件：{path}")
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = set(reader.fieldnames or ())
            missing = sorted(set(required) - fields)
            if missing:
                raise ValueError(f"{path.name} 缺少字段：{missing}")
            rows = list(reader)
    except (OSError, csv.Error) as exc:
        raise ValueError(f"CSV 不可读：{path}") from exc
    if not rows:
        raise ValueError(f"CSV 为空：{path}")
    return rows


def verify_recorded_hash(path: Path, expected: str) -> None:
    """测试和现场提取共用的单文件哈希核对。"""
    if sha256(path) != expected:
        raise ValueError(f"哈希不匹配：{path}")


def validate_entropy_rows(rows: list[dict[str, str]], length: int, label: str) -> list[dict[str, Any]]:
    if len(rows) != length - 1:
        raise ValueError(f"{label} 键数错误：{len(rows)}")
    output = []
    bonds = []
    for row in rows:
        try:
            bond = int(row["bond"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"{label} bond 无效") from exc
        bonds.append(bond)
        output.append({
            "bond": bond,
            "bond_class": int(row["bond_class"]),
            "log_chord": finite(row["log_chord"], f"{label}.log_chord"),
            "entropy": finite(row["entropy"], f"{label}.entropy"),
        })
    if sorted(bonds) != list(range(1, length)):
        raise ValueError(f"{label} bond 缺失或重复")
    return output


def _import_stage1_helpers():
    """按现有脚本路径导入 Stage1 函数和 V2 validator。"""
    script_dir = str(Path(__file__).resolve().parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    from audit_pilot_entropy_robustness import WINDOWS, fit  # type: ignore
    from closeout_negative_size_comparison import connected_quarter, dimer_rms  # type: ignore
    from validate_negative_phase_run_practical_v2 import validate  # type: ignore
    return WINDOWS, fit, dimer_rms, connected_quarter, validate


def _checksum_files(run: Path) -> list[Path]:
    files = [run / "manifest.json", run / "status.json", run / "checksums.sha256"]
    for mode in ("center", "ferro_j2"):
        child = run / f"start_{mode}"
        files.extend([child / "manifest.json", child / "status.json", child / "checksums.sha256"])
        files.extend(child / name for name in (
            "metrics.csv", "entropy_profile_full.csv", "bond_correlations.csv",
            "bond_bond_connected.csv", "sweep_history_sz0.csv", "sweep_history_sz1.csv",
        ))
    return files


def _krylov_value(manifests: list[dict[str, Any]], cell_id: str) -> dict[str, Any]:
    resolved: list[int] = []
    details: list[dict[str, Any]] = []
    source_hashes: list[str] = []
    for index, manifest in enumerate(manifests):
        settings = manifest.get("settings") or {}
        if "eigsolve_krylovdim" in settings:
            value = settings["eigsolve_krylovdim"]
            if isinstance(value, bool) or type(value) is not int or not 3 <= value <= 32:
                raise ValueError(f"{cell_id}: manifest[{index}] eigsolve_krylovdim 无效")
            resolved.append(value)
            details.append({"manifest_index": index, "value": value, "inference": "explicit"})
            continue
        code_hash = (manifest.get("provenance") or {}).get("code_sha256", {}).get(KRYLOV_SOURCE)
        if code_hash not in KNOWN_LEGACY_DEFAULT3:
            raise ValueError(f"{cell_id}: manifest[{index}] 缺字段且源码 hash 未登记")
        source_hashes.append(str(code_hash))
        value = KNOWN_LEGACY_DEFAULT3[code_hash]
        resolved.append(value)
        details.append({"manifest_index": index, "value": value, "inference": "recorded-default3", "source_hash": code_hash})
    if not resolved or len(set(resolved)) != 1:
        raise ValueError(f"{cell_id}: 各 manifest 的 Krylov 值不一致")
    return {
        "value": resolved[0],
        "inference": "per_manifest_consistent",
        "manifest_values": details,
        "source_hashes": sorted(set(source_hashes)),
        "reason": "每份 manifest 均独立解析，显式值或已登记历史默认值一致",
    }


def _fit_entropy(rows: list[dict[str, Any]], windows: tuple[float, ...], fit) -> list[dict[str, Any]]:
    import numpy as np

    bonds = np.asarray([row["bond"] for row in rows], dtype=int)
    x = np.asarray([row["log_chord"] for row in rows], dtype=float)
    y = np.asarray([row["entropy"] for row in rows], dtype=float)
    output = []
    for window in windows:
        keep = (bonds >= window * len(bonds) / (1 - 0.0)) & (bonds <= (len(bonds) + 1) * (1 - window))
        # 与 Stage1 相同的 L 归一化；上式的长度是 bonds+1。
        keep = (bonds >= window * (len(bonds) + 1)) & (bonds <= (len(bonds) + 1) * (1 - window))
        for period in (5, 10):
            result = fit(x[keep], y[keep], bonds[keep] % period)
            output.append({"window": window, "period": period, **result})
    return output


def _select_connected_quarter_rows(rows: list[dict[str, Any]], length: int) -> list[dict[str, Any]]:
    distance = length // 20
    return [
        row for row in rows
        if int(row["bond_class"]) == 0 and float(row["distance_units"]) == distance
    ]


def _extract_point(run: Path, run_spec: Path, expected: tuple[float, float, int, int]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    windows, fit, dimer_rms, connected_quarter, validate = _import_stage1_helpers()
    parent = load_json(run / "manifest.json")
    cell_id = parent.get("cell_id")
    if cell_id not in EXPECTED_POINTS or tuple(expected) != EXPECTED_POINTS[cell_id]:
        raise ValueError(f"不是允许的两个 L80 点：{cell_id}")
    params = parent.get("params") or {}
    actual = (float(params.get("alpha")), float(params.get("beta")), int(params.get("L")), int(params.get("n_units")))
    if actual != expected:
        raise ValueError(f"{cell_id}: 参数不匹配")

    validation = validate(run, run_spec)
    if validation.get("status") != "pass" or validation.get("failures"):
        raise ValueError(f"{cell_id}: V2 validator 未通过：{validation.get('failures')}")
    manifests = [parent]
    starts = []
    all_entropy, all_fits, all_bonds, all_connected, gaps, dimers = [], [], [], [], [], []
    for mode in ("center", "ferro_j2"):
        child = run / f"start_{mode}"
        child_manifest = load_json(child / "manifest.json")
        manifests.append(child_manifest)
        child_params = child_manifest.get("params") or {}
        if float(child_params.get("alpha")) != expected[0] or float(child_params.get("beta")) != expected[1] or int(child_params.get("L")) != expected[2]:
            raise ValueError(f"{cell_id}:{mode}: 子 manifest 参数漂移")
        observed = child_manifest.get("observables") or {}
        gap = finite(observed.get("spin_gap"), f"{cell_id}:{mode}.spin_gap")
        entropy = validate_entropy_rows(read_csv_rows(child / "entropy_profile_full.csv", ("bond", "bond_class", "log_chord", "entropy")), expected[2], f"{cell_id}:{mode}.entropy")
        fits = _fit_entropy(entropy, windows, fit)
        bond_rows_raw = read_csv_rows(child / "bond_correlations.csv", ("bond", "left_site", "right_site", "bond_class", "correlation"))
        bond_rows = []
        for row in bond_rows_raw:
            bond_rows.append({
                "bond": int(row["bond"]), "left_site": int(row["left_site"]), "right_site": int(row["right_site"]),
                "bond_class": int(row["bond_class"]), "correlation": finite(row["correlation"], f"{cell_id}:{mode}.correlation"),
            })
        if len(bond_rows) != expected[2] - 1 or {row["bond"] for row in bond_rows} != set(range(1, expected[2])):
            raise ValueError(f"{cell_id}:{mode}: bond correlation 缺失或重复")
        connected_raw = read_csv_rows(child / "bond_bond_connected.csv", ("bond_class", "reference_bond", "target_bond", "distance_units", "connected"))
        connected = []
        for row in connected_raw:
            distance_units = finite(row["distance_units"], f"{cell_id}:{mode}.distance_units")
            connected.append({
                "bond_class": int(row["bond_class"]), "reference_bond": int(row["reference_bond"]),
                "target_bond": int(row["target_bond"]), "distance_units": distance_units,
                "distance_over_units": distance_units / (expected[2] / 5),
                "connected": finite(row["connected"], f"{cell_id}:{mode}.connected"),
            })
        dimer, pair_count = dimer_rms(bond_rows, expected[2])
        quarter_values = connected_quarter(connected, expected[2])
        quarter_rows = _select_connected_quarter_rows(connected, expected[2])
        if len(quarter_rows) != len(quarter_values):
            raise ValueError(f"{cell_id}:{mode}: quarter 行和值数量不一致")
        point_fields = {"cell_id": cell_id, "alpha": expected[0], "beta": expected[1], "L": expected[2], "start": mode}
        gaps.append({**point_fields, "gap": gap})
        dimers.append({**point_fields, "dimer_rms": dimer, "pair_count": pair_count})
        all_entropy.extend({**point_fields, **row} for row in entropy)
        all_fits.extend({**point_fields, **row} for row in fits)
        all_bonds.extend({**point_fields, **row} for row in bond_rows)
        for row, value in zip(quarter_rows, quarter_values):
            all_connected.append({**point_fields, "reference_bond": row["reference_bond"], "target_bond": row["target_bond"], "distance_units": row["distance_units"], "connected": row["connected"], "staggered_connected": value})
        starts.append({"start": mode, "gap": gap, "entropy_count": len(entropy), "fit_count": len(fits), "bond_correlation_count": len(bond_rows), "connected_quarter_count": len(quarter_values), "dimer_rms": dimer, "dimer_pair_count": pair_count})

    krylov = _krylov_value(manifests, cell_id)
    summary = {"cell_id": cell_id, "params": {"alpha": expected[0], "beta": expected[1], "L": expected[2], "n_units": expected[3]}, "validator": {"status": validation["status"], "acceptance_label": validation["acceptance_label"], "failures": validation["failures"]}, "krylov": krylov, "starts": starts}
    return summary, [{"gaps": gaps, "entropy": all_entropy, "fits": all_fits, "bond_correlations": all_bonds, "connected_quarter": all_connected, "dimer": dimers}]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"不能写入空测量表：{path.name}")
    fields = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def build_inventory(baselines: tuple[Path, Path], run_spec: Path) -> dict[str, Any]:
    if not run_spec.is_file():
        raise ValueError(f"缺少 run spec：{run_spec}")
    summaries = []
    tables = {"gaps": [], "entropy": [], "fits": [], "bond_correlations": [], "connected_quarter": [], "dimer": []}
    source_paths: list[tuple[Path, str]] = [(run_spec, "run_spec")]
    seen_ids = set()
    for run in baselines:
        run = run.resolve()
        if not run.is_dir():
            raise ValueError(f"缺少 baseline：{run}")
        parent = load_json(run / "manifest.json")
        cell_id = parent.get("cell_id")
        if cell_id in seen_ids or cell_id not in EXPECTED_POINTS:
            raise ValueError(f"baseline cell_id 重复或不允许：{cell_id}")
        seen_ids.add(cell_id)
        summary, extracted_list = _extract_point(run, run_spec, EXPECTED_POINTS[cell_id])
        summaries.append(summary)
        extracted = extracted_list[0]
        for name, rows in extracted.items():
            tables[name].extend(rows)
        for path in _checksum_files(run):
            source_paths.append((path, "baseline_input"))
    if seen_ids != set(EXPECTED_POINTS):
        raise ValueError(f"baseline 点不完整：{sorted(seen_ids)}")
    for path in (Path(__file__), ROOT / "scripts" / "autoresearch_v5" / "audit_pilot_entropy_robustness.py", ROOT / "scripts" / "autoresearch_v5" / "closeout_negative_size_comparison.py", ROOT / "scripts" / "autoresearch_v5" / "validate_negative_phase_run_practical_v2.py", ROOT / "scripts" / "autoresearch_v5" / "negative_dmrg_options.py", ROOT / "scripts" / "autoresearch_v5" / "negative_static_cell.jl"):
        source_paths.append((path, "analysis_source"))
    source_records = []
    dedup = set()
    for path, role in source_paths:
        path = path.resolve()
        if path in dedup:
            continue
        dedup.add(path)
        if not path.is_file():
            raise ValueError(f"source 文件缺失：{path}")
        source_records.append({"path": str(path), "role": role, "sha256": sha256(path)})
    return {
        "schema_version": 1,
        "status": "baseline_verified_candidate_missing",
        "audit_only": True,
        "baseline_verified": True,
        "candidate_present": False,
        "candidate_status": "missing",
        "points": summaries,
        "counts": {"points": len(summaries), "starts": len(tables["gaps"]), "gap_records": len(tables["gaps"]), "entropy_records": len(tables["entropy"]), "fit_records": len(tables["fits"]), "bond_correlation_records": len(tables["bond_correlations"]), "dimer_records": len(tables["dimer"]), "connected_quarter_records": len(tables["connected_quarter"])},
        "source_records": source_records,
        "tables": tables,
    }


def write_inventory(inventory: dict[str, Any], out: Path) -> None:
    out = out.resolve()
    try:
        out.relative_to(RESULTS.resolve())
    except ValueError as exc:
        raise ValueError("输出目录必须位于 results 下") from exc
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise FileExistsError(f"拒绝覆盖非空输出：{out}")
    out.mkdir(parents=True, exist_ok=True)
    tables = inventory.pop("tables")
    table_names = {
        "gaps": "gap_records.csv", "entropy": "entropy_records.csv", "fits": "entropy_fits.csv",
        "bond_correlations": "bond_correlations.csv", "connected_quarter": "connected_quarter.csv", "dimer": "dimer_rms.csv",
    }
    for key, name in table_names.items():
        _write_csv(out / name, tables[key])
    source_payload = {"schema_version": 1, "sources": inventory["source_records"]}
    (out / "source_hashes.json").write_text(json.dumps(source_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    inventory["measurement_files"] = [{"name": name, "sha256": sha256(out / name)} for name in table_names.values()]
    inventory["source_hashes_file"] = {"name": "source_hashes.json", "sha256": sha256(out / "source_hashes.json")}
    (out / "baseline_inventory.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {"schema_version": 1, "kind": "static_krylov_baseline_inventory", "status": inventory["status"], "audit_only": True, "candidate_present": False, "baseline_inventory": {"name": "baseline_inventory.json", "sha256": sha256(out / "baseline_inventory.json")}, "measurement_files": inventory["measurement_files"], "source_hashes": inventory["source_hashes_file"]}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", action="append", dest="baselines", type=Path)
    parser.add_argument("--run-spec", type=Path, default=DEFAULT_RUN_SPEC)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    baselines = tuple(args.baselines) if args.baselines is not None else DEFAULT_BASELINES
    if len(baselines) != 2:
        raise SystemExit("本工具只接受两个固定 L80 baseline")
    inventory = build_inventory(baselines, args.run_spec)
    write_inventory(inventory, args.out)
    print(json.dumps({"status": inventory["status"], "points": inventory["counts"]["points"], "starts": inventory["counts"]["starts"], "fit_records": inventory["counts"]["fit_records"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
