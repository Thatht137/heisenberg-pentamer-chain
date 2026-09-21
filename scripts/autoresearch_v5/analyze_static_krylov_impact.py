"""生成 k=3→8 静态对照的敏感性与有限尺寸影响审计。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
COMPARISON_DEFAULT = RESULTS / "autoresearch_v5_20260920" / "static_krylov_controls_r2_comparison_20260920" / "comparison.json"
BASELINE_DEFAULT = RESULTS / "autoresearch_v5_20260920" / "static_krylov_baseline_v3"
CANDIDATE_DEFAULT = RESULTS / "autoresearch_v5_20260920" / "static_krylov_controls_r2_fetch_0945"
RUN_SPEC_DEFAULT = RESULTS / "autoresearch_v5_20260919" / "static_krylov_controls_r2" / "parameter-scan.run_spec.json"
BASELINE_RUN_SPEC_DEFAULT = RESULTS / "autoresearch_v5_20260913" / "negative_phase_independent_pilot_r1" / "parameter-scan.run_spec.json"
BASELINE_RAW_DEFAULT = RESULTS / "autoresearch_v5_20260913" / "negative_phase_independent_pilot_fetch_20260914_2243"
JOINT_DEFAULT = RESULTS / "autoresearch_v5_20260919" / "closeout_stage1_joint_v2" / "joint_size_evidence.csv"
JOINT_SUMMARY_DEFAULT = RESULTS / "autoresearch_v5_20260919" / "closeout_stage1_joint_v2" / "summary.json"
JOINT_QA_DEFAULT = RESULTS / "autoresearch_v5_20260919" / "closeout_stage1_joint_v2" / "qa.json"
OLD_FITS_DEFAULT = RESULTS / "autoresearch_v5_20260919" / "closeout_stage1_reanalysis_v2" / "entropy_fits.csv"
STAGE_STATUS_DEFAULT = RESULTS / "research_progress" / "project_closeout_status_20260919.json"
TERMINAL_DEFAULT = RESULTS / "autoresearch_v5_20260919" / "static_krylov_controls_release_v2" / "compatibility_terminal_snapshot_20260920_0945.json"

POINTS = {
    "negdiag-a01000-b02500-L080": {"alpha": -0.1, "beta": 0.25, "L": 80, "n_units": 16, "candidate_id": "negdiag-a01000-b02500-L080-k08"},
    "negdiag-a01750-b02500-L080": {"alpha": -0.175, "beta": 0.25, "L": 80, "n_units": 16, "candidate_id": "negdiag-a01750-b02500-L080-k08"},
}
MODES = ("center", "ferro_j2")
OBSERVABLES = ("gap", "entropy", "dimer_rms", "connected_quarter", "bond_correlation")
WINDOWS = (0.1, 0.15, 0.2, 0.25)
INITIAL_STATE_SCOPE = "Sz0=start mode; Sz1=center fixed and non-independent"
SCALING_CAVEAT = "L40/L60 are old k3; L80 contains old k3 and new k8; do not combine into a new scaling claim"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"缺少 JSON：{path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON 顶层必须是对象：{path}")
    return value


def read_csv(path: Path, required: Iterable[str] = ()) -> list[dict[str, str]]:
    if not path.is_file():
        raise ValueError(f"缺少 CSV：{path}")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or ())
        missing = sorted(set(required) - fields)
        if missing:
            raise ValueError(f"{path.name} 缺字段：{missing}")
        rows = list(reader)
    if not rows:
        raise ValueError(f"CSV 为空：{path}")
    return rows


def finite(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} 不是数值") from exc
    if not math.isfinite(number):
        raise ValueError(f"{label} 非有限")
    return number


def rel_delta(old: float, new: float) -> float | None:
    denominator = abs(old) + abs(new)
    if denominator == 0.0:
        return None
    return 2.0 * (new - old) / denominator


def relative_spread(values: list[float]) -> float | None:
    if not values:
        return None
    mean = sum(values) / len(values)
    denominator = abs(mean)
    if denominator == 0.0:
        return None
    return (max(values) - min(values)) / denominator


def safe_ratio(numerator: float, denominator: float) -> float | None:
    if denominator == 0.0:
        return None
    return numerator / denominator


def relpath(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def file_record(path: Path, role: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"来源文件缺失：{path}")
    return {"path": relpath(path), "role": role, "bytes": path.stat().st_size, "sha256": sha256(path)}


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    if not rows:
        raise ValueError(f"不能写入空表：{path.name}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def import_entropy_helper():
    script_dir = str(Path(__file__).resolve().parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    from analyze_negative_entropy_sizes import WINDOWS as source_windows  # type: ignore
    from analyze_negative_entropy_sizes import analyze_profile  # type: ignore
    return tuple(float(value) for value in source_windows), analyze_profile


def import_candidate_adapter():
    script_dir = str(Path(__file__).resolve().parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    import static_krylov_candidate_adapter as adapter  # type: ignore
    return adapter


def candidate_cell_dir(candidate_dir: Path, point_id: str) -> Path:
    """解析 fetch 根下的 cells/<cell> 目录。"""
    path = candidate_dir / "cells" / POINTS[point_id]["candidate_id"]
    if not path.is_dir():
        raise ValueError(f"缺少 candidate cell：{path}")
    return path


def validate_comparison(path: Path) -> tuple[dict[str, Any], dict[tuple[str, str, str, int], dict[str, Any]]]:
    comparison = load_json(path)
    if comparison.get("status") != "audit_only" or comparison.get("candidate") != "candidate_verified":
        raise ValueError("comparison 不是 audit_only/candidate_verified")
    if comparison.get("failures"):
        raise ValueError(f"comparison 有 failures：{comparison['failures']}")
    records: dict[tuple[str, str, str, int], dict[str, Any]] = {}
    for point_id, block in (comparison.get("comparisons") or {}).items():
        if point_id not in POINTS or block.get("status") != "audit_only":
            raise ValueError(f"comparison 点或状态异常：{point_id}")
        for row in block.get("records", []):
            key = (point_id, str(row["start"]), str(row["observable"]), int(row["index"]))
            if key in records:
                raise ValueError(f"comparison key 重复：{key}")
            for field in ("baseline_value", "candidate_value", "abs_delta"):
                finite(row[field], f"comparison.{field}")
            records[key] = row
    expected = {point_id for point_id in POINTS}
    if set(comparison.get("comparisons", {})) != expected or len(records) != 648:
        raise ValueError("comparison 不是两点 648 条完整记录")
    return comparison, records


def validate_adapter_audit(
    audit_result: dict[str, Any],
    comparison_records: dict[tuple[str, str, str, int], dict[str, Any]],
) -> int:
    """复用 adapter.audit，并逐条核对已有 648 条 comparison。"""
    if audit_result.get("status") != "audit_only" or audit_result.get("candidate") != "candidate_verified":
        raise ValueError("adapter.audit 不是 audit_only/candidate_verified")
    if audit_result.get("failures"):
        raise ValueError(f"adapter.audit 有 failures：{audit_result['failures']}")
    audited: dict[tuple[str, str, str, int], dict[str, Any]] = {}
    for point_id, block in (audit_result.get("comparisons") or {}).items():
        if point_id not in POINTS or block.get("status") != "audit_only":
            raise ValueError(f"adapter.audit 点或状态异常：{point_id}")
        for row in block.get("records", []):
            key = (point_id, str(row["start"]), str(row["observable"]), int(row["index"]))
            if key in audited:
                raise ValueError(f"adapter.audit key 重复：{key}")
            audited[key] = row
    if len(audited) != 648 or set(audited) != set(comparison_records):
        raise ValueError("adapter.audit 与 comparison 不是同一组 648 条 records")
    fields = ("alpha", "beta", "L", "start", "observable", "index", "baseline_value", "candidate_value", "signed_delta", "abs_delta", "symmetric_relative_delta")
    for key, expected in comparison_records.items():
        actual = audited[key]
        for field in fields:
            left, right = actual.get(field), expected.get(field)
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                if left != right:
                    raise ValueError(f"adapter.audit 与 comparison 数值不一致：{key}/{field}")
            elif left != right:
                raise ValueError(f"adapter.audit 与 comparison 字段不一致：{key}/{field}")
    return len(audited)


def load_profile_rows(path: Path, point_id: str, mode: str, solver: str) -> list[dict[str, Any]]:
    rows = read_csv(path, ("bond", "log_chord", "entropy"))
    expected = list(range(1, POINTS[point_id]["L"]))
    bonds = [int(row["bond"]) for row in rows]
    if bonds != expected:
        raise ValueError(f"熵剖面 bond 不完整：{path}")
    result = []
    for row in rows:
        result.append({"bond": int(row["bond"]), "log_chord": finite(row["log_chord"], "log_chord"), "entropy": finite(row["entropy"], "entropy"), "solver": solver, "point_id": point_id, "start": mode})
    return result


def load_manifest_metrics(manifest_path: Path, metrics_path: Path) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    # metrics 同时含有文字诊断，只保留按需解析的字段。
    metrics = {str(row["metric"]): row["value"] for row in read_csv(metrics_path, ("metric", "value"))}
    diagnostics = manifest.get("diagnostics") or {}
    observables = manifest.get("observables") or {}
    def pick(name: str) -> float:
        if name in diagnostics:
            return finite(diagnostics[name], name)
        if name in metrics:
            return metrics[name]
        raise ValueError(f"manifest/metrics 缺少 {name}：{manifest_path}")
    return {
        "manifest": manifest,
        "q_peak_over_pi": finite(observables["structure_factor_peak_q_over_pi"], "q_peak_over_pi"),
        "dominant_ratio": finite(observables["dominant_structure_factor_ratio"], "dominant_ratio"),
        "final_energy_change_sz0": pick("final_energy_change_sz0"),
        "final_energy_change_sz1": pick("final_energy_change_sz1"),
        "actual_maxdim_sz0": pick("actual_maxdim_sz0"),
        "actual_maxdim_sz1": pick("actual_maxdim_sz1"),
        "requested_maxdim": finite((manifest.get("settings") or {}).get("maxdim", metrics.get("requested_maxdim")), "requested_maxdim"),
        "krylov": int((manifest.get("settings") or {}).get("eigsolve_krylovdim") or 3),
    }


def aggregate_values(rows: list[float]) -> dict[str, Any]:
    if not rows:
        raise ValueError("空 aggregate")
    return {"mean": sum(rows) / len(rows), "min": min(rows), "max": max(rows), "count": len(rows), "relative_spread": relative_spread(rows)}


def build_entropy_profiles(
    baseline_dir: Path,
    candidate_dir: Path,
    point_id: str,
    comparison_records: dict[tuple[str, str, str, int], dict[str, Any]],
) -> list[dict[str, Any]]:
    baseline_rows = read_csv(baseline_dir / "entropy_records.csv", ("cell_id", "start", "bond", "log_chord", "entropy"))
    old = {(row["cell_id"], row["start"], int(row["bond"])): row for row in baseline_rows if row["cell_id"] == point_id}
    output = []
    for mode in MODES:
        cell_dir = candidate_cell_dir(candidate_dir, point_id)
        candidate_rows = load_profile_rows(cell_dir / f"start_{mode}" / "entropy_profile_full.csv", point_id, mode, "k8")
        for row in candidate_rows:
            old_row = old[(point_id, mode, row["bond"])]
            key = (point_id, mode, "entropy", row["bond"])
            comparison = comparison_records[key]
            old_value = finite(old_row["entropy"], "baseline entropy")
            if abs(old_value - float(comparison["baseline_value"])) > 1e-12 or abs(row["entropy"] - float(comparison["candidate_value"])) > 1e-12:
                raise ValueError(f"entropy source 与 comparison 不一致：{key}")
            if abs(finite(old_row["log_chord"], "old log_chord") - row["log_chord"]) > 1e-10:
                raise ValueError(f"entropy log_chord 不一致：{key}")
            output.append({
                "point_id": point_id, "alpha": POINTS[point_id]["alpha"], "beta": POINTS[point_id]["beta"], "L": 80,
                "start": mode, "initial_state_scope": INITIAL_STATE_SCOPE, "bond": row["bond"], "bond_fraction": row["bond"] / 80,
                "old_log_chord": finite(old_row["log_chord"], "old log_chord"), "new_log_chord": row["log_chord"],
                "old_entropy_k3": old_value, "new_entropy_k8": row["entropy"],
                "signed_delta": row["entropy"] - old_value, "abs_delta": abs(row["entropy"] - old_value),
                "symmetric_relative_delta": rel_delta(old_value, row["entropy"]),
            })
    return output


def build_sensitivity_metrics(comparison_records: dict[tuple[str, str, str, int], dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for (point_id, mode, observable, _), row in comparison_records.items():
        grouped[(point_id, mode, observable)].append(row)
    output = []
    for (point_id, mode, observable), rows in sorted(grouped.items()):
        absolute = max(rows, key=lambda row: abs(float(row["signed_delta"])))
        relative_rows = [row for row in rows if row.get("symmetric_relative_delta") is not None]
        relative = max(relative_rows, key=lambda row: abs(float(row["symmetric_relative_delta"]))) if relative_rows else None
        output.append({
            "point_id": point_id, "alpha": POINTS[point_id]["alpha"], "beta": POINTS[point_id]["beta"], "L": 80,
            "start": mode, "observable": observable, "record_count": len(rows), "initial_state_scope": INITIAL_STATE_SCOPE,
            "max_abs_delta": abs(float(absolute["signed_delta"])), "max_abs_index": int(absolute["index"]),
            "max_abs_old": float(absolute["baseline_value"]), "max_abs_new": float(absolute["candidate_value"]),
            "max_abs_symmetric_relative_delta": abs(float(relative["symmetric_relative_delta"])) if relative else None,
            "max_relative_index": int(relative["index"]) if relative else None,
            "max_relative_old": float(relative["baseline_value"]) if relative else None,
            "max_relative_new": float(relative["candidate_value"]) if relative else None,
        })
    return output


def build_spread_metrics(comparison_records: dict[tuple[str, str, str, int], dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, int], dict[str, float]] = defaultdict(dict)
    for (point_id, mode, observable, index), row in comparison_records.items():
        if observable not in OBSERVABLES:
            continue
        grouped[(point_id, observable, index)][mode] = float(row["baseline_value"]), float(row["candidate_value"])
    output = []
    for point_id in POINTS:
        for observable in OBSERVABLES:
            indices = [key for key in grouped if key[:2] == (point_id, observable)]
            if not indices:
                continue
            old_spreads, new_spreads = [], []
            for key in sorted(indices):
                values = grouped[key]
                if set(values) != set(MODES):
                    raise ValueError(f"初态 spread 缺 mode：{key}")
                old_spreads.append(abs(values["center"][0] - values["ferro_j2"][0]))
                new_spreads.append(abs(values["center"][1] - values["ferro_j2"][1]))
            old_metric = aggregate_values(old_spreads)
            new_metric = aggregate_values(new_spreads)
            output.append({
                "point_id": point_id, "alpha": POINTS[point_id]["alpha"], "beta": POINTS[point_id]["beta"], "L": 80,
                "observable": observable, "index_count": len(indices), "initial_state_scope": INITIAL_STATE_SCOPE,
                "spread_semantics": "deterministic center-versus-ferro_j2 range; not CI",
                "old_k3_max_abs_spread": old_metric["max"], "new_k8_max_abs_spread": new_metric["max"],
                "old_k3_mean_abs_spread": old_metric["mean"], "new_k8_mean_abs_spread": new_metric["mean"],
                "max_abs_spread_reduction": old_metric["max"] - new_metric["max"],
                "max_abs_spread_reduction_fraction": safe_ratio(old_metric["max"] - new_metric["max"], old_metric["max"]),
                "mean_abs_spread_reduction": old_metric["mean"] - new_metric["mean"],
                "mean_abs_spread_reduction_fraction": safe_ratio(old_metric["mean"] - new_metric["mean"], old_metric["mean"]),
            })
    return output


def build_solver_drift(baseline_raw: Path, candidate_dir: Path) -> list[dict[str, Any]]:
    output = []
    for point_id, point in POINTS.items():
        for mode in MODES:
            old_child = baseline_raw / point_id / f"start_{mode}"
            new_child = candidate_cell_dir(candidate_dir, point_id) / f"start_{mode}"
            old = load_manifest_metrics(old_child / "manifest.json", old_child / "metrics.csv")
            new = load_manifest_metrics(new_child / "manifest.json", new_child / "metrics.csv")
            if old["krylov"] != 3 or new["krylov"] != 8:
                raise ValueError(f"solver Krylov 不符合 k3→k8：{point_id}/{mode}")
            row = {
                "point_id": point_id, "alpha": point["alpha"], "beta": point["beta"], "L": point["L"], "start": mode,
                "initial_state_scope": INITIAL_STATE_SCOPE, "old_solver": "k3", "new_solver": "k8",
                "old_q_peak_over_pi": old["q_peak_over_pi"], "new_q_peak_over_pi": new["q_peak_over_pi"],
                "old_dominant_ratio": old["dominant_ratio"], "new_dominant_ratio": new["dominant_ratio"],
                "old_final_energy_change_sz0": old["final_energy_change_sz0"], "new_final_energy_change_sz0": new["final_energy_change_sz0"],
                "old_final_energy_change_sz1": old["final_energy_change_sz1"], "new_final_energy_change_sz1": new["final_energy_change_sz1"],
                "new_over_old_final_energy_change_sz0": safe_ratio(abs(new["final_energy_change_sz0"]), abs(old["final_energy_change_sz0"])),
                "new_over_old_final_energy_change_sz1": safe_ratio(abs(new["final_energy_change_sz1"]), abs(old["final_energy_change_sz1"])),
                "old_actual_maxdim_sz0": old["actual_maxdim_sz0"], "new_actual_maxdim_sz0": new["actual_maxdim_sz0"],
                "old_actual_maxdim_sz1": old["actual_maxdim_sz1"], "new_actual_maxdim_sz1": new["actual_maxdim_sz1"],
                "requested_maxdim": new["requested_maxdim"],
                "maxdim_note": "actual maxdim < requested maxdim is diagnostic only, not chi convergence",
                "q_peak_note": "Sz0/observed start mode; Sz1 initialization fixed center and not an independent start",
            }
            output.append(row)
    return output


def fit_rows(path: Path, point_id: str, solver: str, mode_filter: str | None = None) -> list[dict[str, Any]]:
    rows = read_csv(path, ("alpha", "beta", "L", "initial_state", "window", "period", "c_eff", "rmse", "rank", "n", "condition"))
    output = []
    for row in rows:
        alpha = finite(row["alpha"], "fit alpha")
        length = int(row["L"])
        if abs(alpha - POINTS[point_id]["alpha"]) > 1e-12 or length != 80 or (mode_filter and row["initial_state"] != mode_filter):
            continue
        output.append({"point_id": point_id, "alpha": alpha, "beta": finite(row["beta"], "fit beta"), "L": length, "solver": solver, "start": row["initial_state"], "window": finite(row["window"], "fit window"), "period": int(row["period"]), "c_eff": finite(row["c_eff"], "c_eff"), "rmse": finite(row["rmse"], "rmse"), "rank": int(row["rank"]), "n": int(row["n"]), "condition": finite(row["condition"], "condition")})
    return output


def build_candidate_fits(candidate_dir: Path, point_id: str, analyze_profile) -> list[dict[str, Any]]:
    output = []
    for mode in MODES:
        path = candidate_cell_dir(candidate_dir, point_id) / f"start_{mode}" / "entropy_profile_full.csv"
        for row in analyze_profile(path, 80):
            output.append({"point_id": point_id, "alpha": POINTS[point_id]["alpha"], "beta": POINTS[point_id]["beta"], "L": 80, "solver": "k8", "start": mode, "window": float(row["window"]), "period": int(row["period"]), "c_eff": finite(row["c_eff"], "c_eff"), "rmse": finite(row["rmse"], "rmse"), "rank": int(row["rank"]), "n": int(row["n"]), "condition": finite(row["condition"], "condition")})
    return output


def build_finite_size_table(joint_path: Path, old_fits_path: Path, candidate_fits: list[dict[str, Any]], comparison_records: dict[tuple[str, str, str, int], dict[str, Any]]) -> list[dict[str, Any]]:
    joint = read_csv(joint_path, ("alpha", "beta", "L", "gap_mean", "gap_min", "gap_max", "gap_start_relative_spread", "dimer_mean", "dimer_min", "dimer_max", "staggered_connected_mean", "staggered_connected_min", "staggered_connected_max", "connected_samples"))
    joint_map = {(round(finite(row["alpha"], "joint alpha"), 12), int(row["L"])): row for row in joint}
    if len(joint_map) != 12 or {key[1] for key in joint_map} != {40, 60, 80}:
        raise ValueError("joint_size_evidence 不是 12 点 L40/60/80 网格")
    old_fits = read_csv(old_fits_path, ("alpha", "beta", "L", "initial_state", "window", "period", "c_eff"))
    output = []
    for point_id, point in POINTS.items():
        alpha_key = round(point["alpha"], 12)
        for length in (40, 60, 80):
            source = joint_map[(alpha_key, length)]
            fit_values = [finite(row["c_eff"], "old c_eff") for row in old_fits if abs(finite(row["alpha"], "old fit alpha") - point["alpha"]) < 1e-12 and int(row["L"]) == length and int(row["period"]) == 10 and abs(finite(row["window"], "old fit window") - 0.2) < 1e-12]
            if len(fit_values) != 2:
                raise ValueError(f"old entropy fit 缺失：{point_id}/L{length}")
            output.append({
                "point_id": point_id, "alpha": point["alpha"], "beta": point["beta"], "L": length, "solver": "k3", "krylov": 3,
                "initial_state_scope": INITIAL_STATE_SCOPE, "gap_mean": finite(source["gap_mean"], "gap_mean"), "gap_min": finite(source["gap_min"], "gap_min"), "gap_max": finite(source["gap_max"], "gap_max"), "gap_start_relative_spread": finite(source["gap_start_relative_spread"], "gap spread"),
                "dimer_mean": finite(source["dimer_mean"], "dimer_mean"), "dimer_min": finite(source["dimer_min"], "dimer_min"), "dimer_max": finite(source["dimer_max"], "dimer_max"), "connected_mean": finite(source["staggered_connected_mean"], "connected_mean"), "connected_min": finite(source["staggered_connected_min"], "connected_min"), "connected_max": finite(source["staggered_connected_max"], "connected_max"), "connected_samples": int(source["connected_samples"]),
                "entropy_period10_window020_mean": sum(fit_values) / len(fit_values), "entropy_period10_window020_min": min(fit_values), "entropy_period10_window020_max": max(fit_values), "entropy_fit_scope": "existing k3 entropy_fits; effective slope only", "source_role": "closeout_stage1_joint_v2 + closeout_stage1_reanalysis_v2", "scaling_caveat": SCALING_CAVEAT,
            })
        candidate_records = [row for key, row in comparison_records.items() if key[0] == point_id]
        def values(observable: str) -> list[float]:
            return [float(row["candidate_value"]) for row in candidate_records if row["observable"] == observable]
        gaps, dimers, connected = values("gap"), values("dimer_rms"), values("connected_quarter")
        fit_values = [row["c_eff"] for row in candidate_fits if row["point_id"] == point_id and abs(row["window"] - 0.2) < 1e-12 and row["period"] == 10]
        if not gaps or not dimers or not connected or len(fit_values) != 2:
            raise ValueError(f"candidate L80 聚合缺失：{point_id}")
        gap_mean = sum(gaps) / len(gaps)
        output.append({
            "point_id": point_id, "alpha": point["alpha"], "beta": point["beta"], "L": 80, "solver": "k8", "krylov": 8,
            "initial_state_scope": INITIAL_STATE_SCOPE, "gap_mean": sum(gaps) / len(gaps), "gap_min": min(gaps), "gap_max": max(gaps), "gap_start_relative_spread": (max(gaps) - min(gaps)) / abs(gap_mean),
            "dimer_mean": sum(dimers) / len(dimers), "dimer_min": min(dimers), "dimer_max": max(dimers), "connected_mean": sum(connected) / len(connected), "connected_min": min(connected), "connected_max": max(connected), "connected_samples": len(connected),
            "entropy_period10_window020_mean": sum(fit_values) / len(fit_values), "entropy_period10_window020_min": min(fit_values), "entropy_period10_window020_max": max(fit_values), "entropy_fit_scope": "existing analyze_profile helper; effective slope only", "source_role": "r2_fetch_0945", "scaling_caveat": SCALING_CAVEAT,
        })
    return output


def build_source_provenance(
    comparison_path: Path, baseline_dir: Path, candidate_dir: Path, run_spec: Path, baseline_raw: Path,
    joint_path: Path, joint_summary: Path, joint_qa: Path, old_fits_path: Path, stage_status: Path, terminal: Path,
    point_ids: Iterable[str],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[Path] = set()
    def add(path: Path, role: str) -> None:
        path = path.resolve()
        if path in seen:
            return
        seen.add(path)
        records.append(file_record(path, role))
    add(comparison_path, "comparison_audit")
    add(baseline_dir / "manifest.json", "baseline_manifest")
    add(baseline_dir / "baseline_inventory.json", "baseline_inventory")
    add(baseline_dir / "source_hashes.json", "baseline_source_hashes")
    for name in ("gap_records.csv", "entropy_records.csv", "entropy_fits.csv", "bond_correlations.csv", "connected_quarter.csv", "dimer_rms.csv"):
        add(baseline_dir / name, "baseline_measurement")
    add(run_spec, "candidate_run_spec")
    for point_id in point_ids:
        point = POINTS[point_id]
        new_cell = candidate_cell_dir(candidate_dir, point_id)
        old_cell = baseline_raw / point_id
        add(new_cell / "manifest.json", "candidate_parent_manifest")
        add(new_cell / "checksums.sha256", "candidate_parent_checksums")
        for mode in MODES:
            for base, role in ((new_cell / f"start_{mode}", "candidate_measurement"), (old_cell / f"start_{mode}", "baseline_raw_solver_diagnostic")):
                add(base / "manifest.json", role)
                add(base / "metrics.csv", role)
            for name in ("entropy_profile_full.csv", "bond_correlations.csv", "bond_bond_connected.csv"):
                add(new_cell / f"start_{mode}" / name, "candidate_measurement")
    for path, role in ((joint_path, "stage1_joint_table"), (joint_summary, "stage1_joint_summary"), (joint_qa, "stage1_joint_qa"), (old_fits_path, "stage1_existing_entropy_fits"), (terminal, "terminal_validation_receipt"), (Path(__file__), "analysis_script"), (Path(__file__).with_name("analyze_negative_entropy_sizes.py"), "existing_entropy_fit_helper"), (Path(__file__).with_name("audit_pilot_entropy_robustness.py"), "existing_fit_backend"), (Path(__file__).with_name("static_krylov_candidate_adapter.py"), "candidate_audit_adapter")):
        add(path, role)
    return records


def plot_figure(out: Path, entropy_rows: list[dict[str, Any]], sensitivity_rows: list[dict[str, Any]], spread_rows: list[dict[str, Any]], solver_rows: list[dict[str, Any]], fit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    import matplotlib as mpl
    mpl.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    mpl.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"], "svg.fonttype": "none", "pdf.fonttype": 42, "font.size": 7, "axes.spines.right": False, "axes.spines.top": False, "axes.linewidth": 0.8, "legend.frameon": False})
    width = 183 / 25.4
    fig, axes = plt.subplots(2, 3, figsize=(width, 112 / 25.4), constrained_layout=False)
    from matplotlib.patches import Patch

    colors = {"center": "#0072B2", "ferro_j2": "#D55E00"}
    labels = {"center": "center", "ferro_j2": "ferro_j2"}
    point_order = list(POINTS)
    point_labels = {point_order[0]: r"$\alpha=-0.10$", point_order[1]: r"$\alpha=-0.175$"}
    short_point_labels = {point_order[0]: "-.10", point_order[1]: "-.175"}
    panel_labels = "abcdef"
    for index, point_id in enumerate(point_order):
        ax = axes[0, index]
        for mode in MODES:
            rows = sorted((row for row in entropy_rows if row["point_id"] == point_id and row["start"] == mode), key=lambda row: row["bond"])
            x = [row["bond_fraction"] for row in rows]
            ax.plot(x, [row["old_entropy_k3"] for row in rows], color=colors[mode], linestyle="--", linewidth=0.9, alpha=0.72, label=f"{labels[mode]} k3")
            ax.plot(x, [row["new_entropy_k8"] for row in rows], color=colors[mode], linestyle="-", linewidth=1.1, label=f"{labels[mode]} k8")
        ax.set_title(point_labels[point_id], fontsize=8, pad=3)
        ax.set_xlabel("bond / L")
        ax.set_ylabel("entropy")
        ax.set_xlim(0, 1)
        ax.text(-0.14, 1.08, panel_labels[index], transform=ax.transAxes, fontweight="bold", fontsize=8, va="top")
        if index == 0:
            ax.legend(fontsize=5.5, ncol=2, handlelength=2.2, columnspacing=0.8, loc="lower center")

    # 用既有 fit helper 的 period=10/window=.20 结果展示 k3/k8 诊断斜率。
    groups = [(point_id, mode) for point_id in point_order for mode in MODES]
    x = np.arange(len(groups), dtype=float)
    old_slope, new_slope = [], []
    for point_id, mode in groups:
        old = next(row for row in fit_rows if row["point_id"] == point_id and row["start"] == mode and row["solver"] == "k3" and row["window"] == 0.2 and row["period"] == 10)
        new = next(row for row in fit_rows if row["point_id"] == point_id and row["start"] == mode and row["solver"] == "k8" and row["window"] == 0.2 and row["period"] == 10)
        old_slope.append(old["c_eff"])
        new_slope.append(new["c_eff"])
    slope_ax = axes[0, 2]
    slope_ax.bar(x - 0.18, old_slope, width=0.34, color="#8c8c8c")
    slope_ax.bar(x + 0.18, new_slope, width=0.34, color="#56B4E9")
    slope_ax.set_xticks(x, [f"{short_point_labels[p]}\n{'C' if m == 'center' else 'F'}" for p, m in groups], fontsize=6)
    slope_ax.set_title("effective slope diagnostic", fontsize=8, pad=3)
    slope_ax.set_ylabel(r"$c_{\mathrm{eff}}$ (period 10, window .20)")
    slope_ax.text(-0.14, 1.08, panel_labels[2], transform=slope_ax.transAxes, fontweight="bold", fontsize=8, va="top")

    def grouped_panel(ax, observable: str, title: str, ylabel: str, log_scale: bool = False) -> None:
        groups = [(point_id, mode) for point_id in point_order for mode in MODES]
        x = np.arange(len(groups), dtype=float)
        old_values, new_values = [], []
        for point_id, mode in groups:
            row = next(row for row in sensitivity_rows if row["point_id"] == point_id and row["start"] == mode and row["observable"] == observable)
            old_values.append(row["max_abs_old"])
            new_values.append(row["max_abs_new"])
        ax.bar(x - 0.18, old_values, width=0.34, color="#8c8c8c", label="k3")
        ax.bar(x + 0.18, new_values, width=0.34, color="#56B4E9", label="k8")
        ax.set_xticks(x, [f"{short_point_labels[p]}\n{'C' if m == 'center' else 'F'}" for p, m in groups], rotation=0, fontsize=6)
        ax.set_title(title, fontsize=8, pad=3)
        ax.set_ylabel(ylabel)
        if log_scale:
            ax.set_yscale("log")

    grouped_panel(axes[1, 0], "gap", "gap sensitivity", "spin gap ($J_1$)", True)
    grouped_panel(axes[1, 1], "dimer_rms", "dimer sensitivity", "dimer RMS", False)
    grouped_panel(axes[1, 2], "connected_quarter", "connected sensitivity", "staggered connected", True)
    axes[1, 0].text(-0.14, 1.08, panel_labels[3], transform=axes[1, 0].transAxes, fontweight="bold", fontsize=8, va="top")
    axes[1, 1].text(-0.14, 1.08, panel_labels[4], transform=axes[1, 1].transAxes, fontweight="bold", fontsize=8, va="top")
    axes[1, 2].text(-0.14, 1.08, panel_labels[5], transform=axes[1, 2].transAxes, fontweight="bold", fontsize=8, va="top")
    fig.legend(handles=[Patch(facecolor="#8c8c8c", label="k3"), Patch(facecolor="#56B4E9", label="k8")], loc="upper right", bbox_to_anchor=(0.99, 0.97), ncol=2, fontsize=5.5, handlelength=1.4, columnspacing=0.8)
    fig.suptitle("Static Krylov sensitivity: k=3 → k=8", fontsize=9, y=0.995)
    fig.text(0.5, 0.018, "C=center; F=ferro_j2. Deterministic audit only; Sz1 initialization is fixed center and not an independent start; no phase/convergence claim", ha="center", fontsize=5.5)
    fig.subplots_adjust(left=0.07, right=0.99, bottom=0.18, top=0.90, wspace=0.34, hspace=0.48)
    outputs = []
    stem = out / "static_krylov_impact_v1"
    for suffix, kwargs in (("svg", {}), ("pdf", {}), ("png", {"dpi": 600}), ("tiff", {"dpi": 600})):
        path = stem.with_suffix("." + suffix)
        fig.savefig(path, bbox_inches="tight", **kwargs)
        outputs.append({"name": path.name, "path": relpath(path), "bytes": path.stat().st_size, "sha256": sha256(path), "format": suffix})
    plt.close(fig)
    return outputs


def run_analysis(args: argparse.Namespace) -> dict[str, Any]:
    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"拒绝覆盖非空输出目录：{out}")
    out.mkdir(parents=True, exist_ok=True)
    source_windows, analyze_profile = import_entropy_helper()
    if tuple(round(value, 8) for value in source_windows) != tuple(round(value, 8) for value in WINDOWS):
        raise ValueError("entropy helper windows 漂移")
    comparison, comparison_records = validate_comparison(args.comparison)
    adapter = import_candidate_adapter()
    adapter_audit = adapter.audit(args.baseline, args.baseline_run_spec, args.candidate, args.run_spec)
    audited_records = validate_adapter_audit(adapter_audit, comparison_records)
    baseline_manifest = load_json(args.baseline / "manifest.json")
    inventory = load_json(args.baseline / "baseline_inventory.json")
    if baseline_manifest.get("status") != "baseline_verified_candidate_missing" or inventory.get("status") != "baseline_verified_candidate_missing":
        raise ValueError("baseline_v3 状态不符合 candidate_missing")
    run_spec = load_json(args.run_spec)
    if (run_spec.get("settings") or {}).get("eigsolve_krylovdim") != 8:
        raise ValueError("r2 run spec 不是 k8")
    terminal = load_json(args.terminal)
    if terminal.get("status") != "terminal_success":
        raise ValueError("终态回执不是 terminal_success")
    entropy_rows = []
    for point_id in POINTS:
        entropy_rows.extend(build_entropy_profiles(args.baseline, args.candidate, point_id, comparison_records))
    sensitivity_rows = build_sensitivity_metrics(comparison_records)
    spread_rows = build_spread_metrics(comparison_records)
    solver_rows = build_solver_drift(args.baseline_raw, args.candidate)
    candidate_fits = []
    for point_id in POINTS:
        candidate_fits.extend(build_candidate_fits(args.candidate, point_id, analyze_profile))
    old_fit_rows = []
    for point_id in POINTS:
        old_fit_rows.extend(fit_rows(args.old_fits, point_id, "k3"))
    fit_output = old_fit_rows + candidate_fits
    finite_rows = build_finite_size_table(args.joint, args.old_fits, candidate_fits, comparison_records)
    write_csv(out / "entropy_profiles.csv", entropy_rows, ["point_id", "alpha", "beta", "L", "start", "initial_state_scope", "bond", "bond_fraction", "old_log_chord", "new_log_chord", "old_entropy_k3", "new_entropy_k8", "signed_delta", "abs_delta", "symmetric_relative_delta"])
    write_csv(out / "sensitivity_metrics.csv", sensitivity_rows, list(sensitivity_rows[0]))
    write_csv(out / "initial_state_spread.csv", spread_rows, list(spread_rows[0]))
    write_csv(out / "solver_drift.csv", solver_rows, list(solver_rows[0]))
    write_csv(out / "entropy_fit_comparison.csv", fit_output, list(fit_output[0]))
    write_csv(out / "finite_size_impact.csv", finite_rows, list(finite_rows[0]))
    source_records = build_source_provenance(args.comparison, args.baseline, args.candidate, args.run_spec, args.baseline_raw, args.joint, args.joint_summary, args.joint_qa, args.old_fits, args.stage_status, args.terminal, POINTS)
    validator_summary = {
        "adapter": "static_krylov_candidate_adapter.audit",
        "status": adapter_audit["status"],
        "baseline": adapter_audit.get("baseline"),
        "candidate": adapter_audit.get("candidate"),
        "failures": adapter_audit.get("failures", []),
        "comparison_records": audited_records,
        "all_pass": True,
        "terminal": {"path": relpath(args.terminal), "sha256": sha256(args.terminal), "status": terminal.get("status"), "completed_cells": terminal.get("completed_cells"), "checksums_exit_code": terminal.get("all_checksums_exit_code")},
    }
    contract = {
        "core_conclusion": "k=3→k=8 会改变部分 L80 观测量，且初态 spread 与求解器末步能量变化可量化；这些证据不能替代观测量稳定性、有限尺寸标度或物理相判定。",
        "evidence_chain": ["entropy spatial profiles: old/new at two alpha points and two Sz0 start modes", "gap/dimer/connected sensitivity: comparison records", "finite-size context: old k3 L40/L60/L80 plus new k8 L80 only", "solver diagnostics: final energy change, actual maxdim, q_peak and dominant ratio"],
        "archetype": "quantitative grid",
        "backend": "python_matplotlib",
        "journal_width_mm": 183,
        "exports": ["SVG editable text", "PDF editable text", "PNG 600 dpi", "TIFF 600 dpi"],
        "statistics": {"deterministic_data": True, "p_values": False, "initial_state_range_is_ci": False, "effective_slope_is_central_charge": False},
        "review_risks": ["Sz1 initialization is fixed center and non-independent", "actual maxdim below request is not chi convergence", "L40/L60 old k3 and L80 old/new k values must not be combined as a new scaling claim", "no phase claim"],
    }
    write_json(out / "figure_contract.json", contract)
    figure_outputs = plot_figure(out, entropy_rows, sensitivity_rows, spread_rows, solver_rows, fit_output)
    outputs = []
    for name in ("entropy_profiles.csv", "sensitivity_metrics.csv", "initial_state_spread.csv", "solver_drift.csv", "entropy_fit_comparison.csv", "finite_size_impact.csv", "figure_contract.json"):
        outputs.append({"name": name, "path": relpath(out / name), "bytes": (out / name).stat().st_size, "sha256": sha256(out / name)})
    outputs.extend(figure_outputs)
    summary = {
        "schema_version": 1, "status": "audit_only", "claim": "none", "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "analysis": "static_krylov_impact_v1", "comparison": {"path": relpath(args.comparison), "status": comparison.get("status"), "candidate": comparison.get("candidate"), "failures": comparison.get("failures"), "points": len(comparison.get("comparisons", {})), "records": len(comparison_records), "krylov_change": comparison.get("comparisons", {}).get(next(iter(POINTS)), {}).get("krylov_change")},
        "validator_provenance": validator_summary, "source_provenance": {"path": "source_provenance.json", "count": len(source_records), "adapter_comparison_records": audited_records},
        "figure_contract": contract, "windows": list(source_windows), "periods": [5, 10],
        "key_facts": {
            "entropy_period10_window020": [row for row in fit_output if row["period"] == 10 and abs(row["window"] - 0.2) < 1e-12],
            "initial_state_spread": spread_rows,
            "solver_drift": solver_rows,
            "finite_size_rows": len(finite_rows),
        },
        "outputs": outputs,
        "limitations": ["audit_only; no phase/convergence claim", "effective slope/window sensitivity is descriptive and not a thermodynamic central charge", "initial-state spreads are deterministic ranges, not confidence intervals", "Sz1 is fixed center and non-independent", "L40/L60 old k3 and L80 old/new are not a new scaling fit", "no p-values or bootstrap intervals"],
    }
    write_json(out / "source_provenance.json", {"schema_version": 1, "scope": "selected source files only; no state JLD2 hashing; project status is not a permanent input", "files": source_records, "validator": validator_summary, "adapter_audit": {"status": adapter_audit["status"], "baseline": adapter_audit.get("baseline"), "candidate": adapter_audit.get("candidate"), "comparison_records": audited_records, "baseline_provenance": adapter_audit.get("baseline_provenance"), "candidate_provenance": adapter_audit.get("candidate_provenance")}})
    summary["outputs"].append({"name": "source_provenance.json", "path": "source_provenance.json", "bytes": (out / "source_provenance.json").stat().st_size, "sha256": sha256(out / "source_provenance.json")})
    write_json(out / "summary.json", summary)
    outputs.append({"name": "summary.json", "path": "summary.json", "bytes": (out / "summary.json").stat().st_size, "sha256": sha256(out / "summary.json")})
    manifest = {"schema_version": 1, "kind": "static_krylov_impact_v1", "status": "audit_only", "claim": "none", "figure_contract": contract, "analysis_script": file_record(Path(__file__), "analysis_script"), "source_provenance": {"name": "source_provenance.json", "sha256": sha256(out / "source_provenance.json")}, "summary": {"name": "summary.json", "sha256": sha256(out / "summary.json")}, "outputs": outputs}
    write_json(out / "manifest.json", manifest)
    print(json.dumps({"status": "audit_only", "points": len(POINTS), "entropy_rows": len(entropy_rows), "finite_size_rows": len(finite_rows), "validator_pass": validator_summary["all_pass"], "output": relpath(out)}, ensure_ascii=False))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", type=Path, default=COMPARISON_DEFAULT)
    parser.add_argument("--baseline", type=Path, default=BASELINE_DEFAULT)
    parser.add_argument("--candidate", type=Path, default=CANDIDATE_DEFAULT)
    parser.add_argument("--run-spec", type=Path, default=RUN_SPEC_DEFAULT)
    parser.add_argument("--baseline-run-spec", type=Path, default=BASELINE_RUN_SPEC_DEFAULT)
    parser.add_argument("--baseline-raw", type=Path, default=BASELINE_RAW_DEFAULT)
    parser.add_argument("--joint", type=Path, default=JOINT_DEFAULT)
    parser.add_argument("--joint-summary", type=Path, default=JOINT_SUMMARY_DEFAULT)
    parser.add_argument("--joint-qa", type=Path, default=JOINT_QA_DEFAULT)
    parser.add_argument("--old-fits", type=Path, default=OLD_FITS_DEFAULT)
    parser.add_argument("--stage-status", type=Path, default=STAGE_STATUS_DEFAULT)
    parser.add_argument("--terminal", type=Path, default=TERMINAL_DEFAULT)
    parser.add_argument("--out", type=Path, default=RESULTS / "autoresearch_v5_20260920" / "static_krylov_impact_v1")
    run_analysis(parser.parse_args())


if __name__ == "__main__":
    main()
