#!/usr/bin/env python3
"""汇总 R11 通过终态并锁定回传证据。"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from ingest_negative_phase_r6 import load, relative, sha256, verify_checksums, write_json


CELL = "nega-r11-a0050-b0500-L040"
KEY = (-0.05, 0.5, 40)
ACTION = "act-fffdf93a9cae183cb1c1"
MODES = ("center", "ferro_j2")
R6_HALF = 0.011877542575884303


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch-dir", type=Path, required=True)
    parser.add_argument("--run-spec", type=Path, required=True)
    parser.add_argument("--phase-dir", type=Path, required=True)
    return parser.parse_args()


def key(params: dict[str, Any]) -> tuple[float, float, int]:
    return float(params["alpha"]), float(params["beta"]), int(params["L"])


def finite(value: Any, label: str) -> float:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{label} 不是有限数")
    return float(value)


def child(run: Path, mode: str) -> tuple[dict[str, float], float]:
    manifest = load(run / f"start_{mode}" / "manifest.json")
    diag, obs, checks = manifest.get("diagnostics", {}), manifest.get("observables", {}), manifest.get("acceptance", {})
    values = {
        "variance_per_site_sz0": finite(diag.get("variance_per_site_sz0"), f"{mode}.var0"),
        "variance_per_site_sz1": finite(diag.get("variance_per_site_sz1"), f"{mode}.var1"),
        "final_truncation_error_sz0": finite(diag.get("final_truncation_error_sz0"), f"{mode}.trunc0"),
        "final_truncation_error_sz1": finite(diag.get("final_truncation_error_sz1"), f"{mode}.trunc1"),
        "total_sz0": finite(diag.get("total_sz0"), f"{mode}.sz0"),
        "total_sz1": finite(diag.get("total_sz1"), f"{mode}.sz1"),
        "spin_gap": finite(obs.get("spin_gap"), f"{mode}.gap"),
    }
    if (
        manifest.get("status") != "success" or manifest.get("accepted") is not True
        or key(manifest.get("params", {})) != KEY or manifest.get("settings", {}).get("nsweeps") != 128
        or manifest.get("settings", {}).get("q_count") != 401 or not checks or not all(checks.values())
        or max(values["variance_per_site_sz0"], values["variance_per_site_sz1"]) > 1e-8
        or max(values["final_truncation_error_sz0"], values["final_truncation_error_sz1"]) > 1e-9
        or abs(values["total_sz0"]) > 1e-8 or abs(values["total_sz1"] - 1.0) > 1e-8
        or values["spin_gap"] < -1e-8
    ):
        raise ValueError(f"R11 {mode} 未严格通过")
    return values, finite(obs.get("dominant_structure_factor_ratio"), f"{mode}.R")


def main() -> int:
    args = parse_args()
    fetch, spec_path, phase = args.fetch_dir.resolve(), args.run_spec.resolve(), args.phase_dir.resolve()
    run = fetch / CELL
    paths = {
        "manifest": run / "manifest.json", "validation": fetch / "validation" / f"{CELL}.json",
        "receipt": fetch / "receipts" / f"{CELL}.json", "preview": fetch / "previews" / f"{CELL}.json",
        "r10_summary": phase / "r10_failure_ingestion_summary.json",
        "r10_audit": phase / "r10_failure_ingestion_audit.json",
        "calibration": phase / "accepted_calibration_through_r9.json",
        "observations": phase / "observations.json", "actions": phase / "action_index.json",
    }
    for path in (spec_path, *paths.values()):
        if not path.is_file():
            raise FileNotFoundError(path)
    spec = load(spec_path)
    cells, settings, provenance = spec.get("cells", []), spec.get("settings", {}), spec.get("provenance", {})
    if (
        len(cells) != 1 or cells[0].get("cell_id") != CELL or key(cells[0].get("params", {})) != KEY
        or cells[0].get("budget") != 128 or cells[0].get("retry_of") != "nega-r10-a0050-b0500-L040"
        or cells[0].get("controller_action_id") != ACTION or settings.get("nsweeps") != 128
        or settings.get("maxdim_by_L", {}).get("40") != 800 or settings.get("threads") != 8
        or settings.get("q_count") != 401 or settings.get("acceptance", {}).get("variance_per_site_max") != 1e-8
        or settings.get("acceptance", {}).get("spin_gap_min") != -1e-8
        or provenance.get("r10_failure_ingestion_summary_sha256") != sha256(paths["r10_summary"])
        or provenance.get("r10_failure_ingestion_audit_sha256") != sha256(paths["r10_audit"])
        or provenance.get("accepted_calibration_through_r9_sha256") != sha256(paths["calibration"])
        or provenance.get("observations_sha256") != sha256(paths["observations"])
        or provenance.get("action_index_sha256") != sha256(paths["actions"])
        or provenance.get("r6_initial_state_sensitivity_half_difference") != R6_HALF
        or provenance.get("r7_failure_provenance_preserved") is not True
        or provenance.get("r9_failure_provenance_preserved") is not True
        or provenance.get("thresholds_relaxed") is not False
    ):
        raise ValueError("R11 身份、R10 基线或严格门不匹配")
    receipt, preview = load(paths["receipt"]), load(paths["preview"])
    if (
        receipt.get("status") != "pass" or receipt.get("non_clobbering") is not True
        or receipt.get("cell_id") != CELL or Path(receipt.get("destination", "")).resolve() != run
        or receipt.get("manifest_sha256") != sha256(paths["manifest"])
        or receipt.get("preview_sha256") != sha256(paths["preview"])
        or preview.get("status") != "pass" or preview.get("remote_checksum_status") != "pass"
        or preview.get("destination_exists") is not False
        or Path(preview.get("local_destination", "")).resolve() != run
    ):
        raise ValueError("R11 回传身份或非覆盖门失败")
    parent_hashes = verify_checksums(run)
    child_hashes = {mode: verify_checksums(run / f"start_{mode}") for mode in MODES}
    validation, manifest = load(paths["validation"]), load(paths["manifest"])
    if (
        validation.get("status") != "pass" or validation.get("cell_id") != CELL
        or not validation.get("checks") or not all(validation["checks"].values()) or validation.get("failures")
        or manifest.get("status") != "success" or manifest.get("accepted") is not True
    ):
        raise ValueError("R11 validator 或父终态未通过")
    rows = {mode: child(run, mode) for mode in MODES}
    diagnostics = {mode: rows[mode][0] for mode in MODES}
    ratios = {mode: rows[mode][1] for mode in MODES}
    mean, half = 0.5 * sum(ratios.values()), 0.5 * abs(ratios["center"] - ratios["ferro_j2"])
    observable = manifest.get("observables", {}).get("dominant_structure_factor_ratio", {})
    if (
        not math.isclose(observable.get("value"), mean, abs_tol=1e-14)
        or not math.isclose(observable.get("error"), half, abs_tol=1e-14)
    ):
        raise ValueError("R11 父观测量不是双初态均值与半差")
    validation_summary = fetch / "validation" / "summary.json"
    write_json(validation_summary, {
        "schema_version": 1, "status": "pass", "cell_count": 1, "counts": {"pass": 1, "fail": 0},
        "rows": [{"cell_id": CELL, "validator_status": "pass", "exit_code": 0,
                  "output": str(paths["validation"]), "sha256": sha256(paths["validation"])}],
    })
    handoff_audit = fetch / "handoff_audit.json"
    write_json(handoff_audit, {
        "schema_version": 1, "status": "pass", "cell_id": CELL,
        "remote_checksums": "parent_and_two_children_pass", "local_checksums": "pass",
        "non_clobbering_fetch": True,
        "checksum_entries": {"parent": len(parent_hashes), "children": {k: len(v) for k, v in child_hashes.items()}},
        "validator": {"status": "pass", "sha256": sha256(paths["validation"])},
        "accepted_only_eligible": True, "thresholds_relaxed": False,
    })
    success_summary = fetch / "success_handoff_summary.json"
    summary = {
        "schema_version": 1, "status": "accepted", "cell_id": CELL,
        "params": {"alpha": -0.05, "beta": 0.5, "L": 40}, "budget": 128,
        "artifact": relative(paths["manifest"]), "validation": relative(paths["validation"]),
        "receipt": relative(paths["receipt"]), "accepted_observable": {"value": mean, "error": half},
        "q_peak_over_pi": manifest["observables"]["structure_factor_peak_q_over_pi"],
        "strict_numerical_gates": diagnostics,
        "validation_summary": {"artifact": relative(validation_summary), "sha256": sha256(validation_summary)},
        "handoff_audit": {"artifact": relative(handoff_audit), "sha256": sha256(handoff_audit)},
        "r9_r10_failure_provenance_required": True, "r6_half_difference": R6_HALF,
        "r7_failure_provenance_preserved": True, "thresholds_relaxed": False,
    }
    write_json(success_summary, summary)
    print(json.dumps({"status": "pass", "cell": CELL, "summary": str(success_summary)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
