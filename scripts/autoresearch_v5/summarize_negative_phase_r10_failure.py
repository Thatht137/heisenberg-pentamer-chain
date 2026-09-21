#!/usr/bin/env python3
"""汇总 R10 失败终态并锁定回传证据。"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from ingest_negative_phase_r6 import load, relative, sha256, verify_checksums, write_json


ROOT = Path(__file__).resolve().parents[2]
CELL = "nega-r10-a0050-b0500-L040"
KEY = (-0.05, 0.5, 40)
ACTION = "act-fffdf93a9cae183cb1c1"
MODES = ("center", "ferro_j2")
CENTER_FAILURES = {"variance_sz0_per_site_le_1e-8", "nonnegative_gap"}


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


def forbidden(value: Any) -> bool:
    if isinstance(value, dict):
        return any(name in {"value", "error"} or forbidden(item) for name, item in value.items())
    if isinstance(value, list):
        return any(forbidden(item) for item in value)
    return False


def diagnostics(run: Path, mode: str) -> tuple[dict[str, float], set[str], bool]:
    child = load(run / f"start_{mode}" / "manifest.json")
    accept = child.get("acceptance", {})
    false_flags = {name for name, passed in accept.items() if passed is False}
    diag, obs = child.get("diagnostics", {}), child.get("observables", {})
    values = {
        "variance_per_site_sz0": finite(diag.get("variance_per_site_sz0"), f"{mode}.var0"),
        "variance_per_site_sz1": finite(diag.get("variance_per_site_sz1"), f"{mode}.var1"),
        "final_truncation_error_sz0": finite(diag.get("final_truncation_error_sz0"), f"{mode}.trunc0"),
        "final_truncation_error_sz1": finite(diag.get("final_truncation_error_sz1"), f"{mode}.trunc1"),
        "total_sz0": finite(diag.get("total_sz0"), f"{mode}.sz0"),
        "total_sz1": finite(diag.get("total_sz1"), f"{mode}.sz1"),
        "spin_gap": finite(obs.get("spin_gap"), f"{mode}.gap"),
    }
    common = (
        child.get("status") == "success" and key(child.get("params", {})) == KEY
        and child.get("settings", {}).get("nsweeps") == 64
        and child.get("settings", {}).get("q_count") == 401
        and child.get("settings", {}).get("cutoff") == 1e-11
        and max(values["final_truncation_error_sz0"], values["final_truncation_error_sz1"]) <= 1e-9
        and abs(values["total_sz0"]) <= 1e-8 and abs(values["total_sz1"] - 1.0) <= 1e-8
    )
    if not common:
        raise ValueError(f"R10 {mode} 基础门失败")
    return values, false_flags, child.get("accepted") is True


def main() -> int:
    args = parse_args()
    fetch, spec_path, phase = args.fetch_dir.resolve(), args.run_spec.resolve(), args.phase_dir.resolve()
    run = fetch / CELL
    paths = {
        "manifest": run / "manifest.json", "validation": fetch / "validation" / f"{CELL}.json",
        "receipt": fetch / "receipts" / f"{CELL}.json", "preview": fetch / "previews" / f"{CELL}.json",
        "r9_summary": phase / "r9_partial_ingestion_summary.json",
        "r9_audit": phase / "r9_partial_ingestion_audit.json",
        "r9_calibration": phase / "accepted_calibration_through_r9.json",
        "observations": phase / "observations.json", "actions": phase / "action_index.json",
    }
    for path in (spec_path, *paths.values()):
        if not path.is_file():
            raise FileNotFoundError(path)

    spec = load(spec_path)
    cells, settings, provenance = spec.get("cells", []), spec.get("settings", {}), spec.get("provenance", {})
    if (
        len(cells) != 1 or cells[0].get("cell_id") != CELL or key(cells[0].get("params", {})) != KEY
        or cells[0].get("budget") != 64 or cells[0].get("retry_of") != "nega-r9-a0050-b0500-L040"
        or cells[0].get("controller_action_id") != ACTION or settings.get("nsweeps") != 64
        or settings.get("maxdim_by_L", {}).get("40") != 800 or settings.get("threads") != 8
        or settings.get("q_count") != 401 or settings.get("cutoff") != 1e-11
        or settings.get("acceptance", {}).get("variance_per_site_max") != 1e-8
        or settings.get("acceptance", {}).get("spin_gap_min") != -1e-8
        or provenance.get("r9_partial_ingestion_summary_sha256") != sha256(paths["r9_summary"])
        or provenance.get("r9_partial_ingestion_audit_sha256") != sha256(paths["r9_audit"])
        or provenance.get("accepted_calibration_through_r9_sha256") != sha256(paths["r9_calibration"])
        or provenance.get("observations_sha256") != sha256(paths["observations"])
        or provenance.get("action_index_sha256") != sha256(paths["actions"])
        or provenance.get("r6_initial_state_sensitivity_half_difference") != 0.011877542575884303
        or provenance.get("r7_failure_provenance_preserved") is not True
        or provenance.get("thresholds_relaxed") is not False
    ):
        raise ValueError("R10 身份、R9 基线或严格门不匹配")

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
        raise ValueError("R10 回传身份或非覆盖门失败")
    parent_hashes = verify_checksums(run)
    child_hashes = {mode: verify_checksums(run / f"start_{mode}") for mode in MODES}
    validation, manifest = load(paths["validation"]), load(paths["manifest"])
    if (
        validation.get("status") != "fail" or validation.get("cell_id") != CELL
        or validation.get("checks", {}).get("terminal_acceptance") is not False
        or any(passed is not True for name, passed in validation.get("checks", {}).items() if name != "terminal_acceptance")
        or not validation.get("failures") or manifest.get("status") != "failed" or manifest.get("accepted") is not False
    ):
        raise ValueError("R10 validator 或父终态不匹配")
    center, center_flags, center_accepted = diagnostics(run, "center")
    ferro, ferro_flags, ferro_accepted = diagnostics(run, "ferro_j2")
    if (
        center_accepted or center_flags != CENTER_FAILURES
        or center["variance_per_site_sz0"] <= 1e-8 or center["variance_per_site_sz1"] > 1e-8
        or center["spin_gap"] >= -1e-8
        or not ferro_accepted or ferro_flags
        or max(ferro["variance_per_site_sz0"], ferro["variance_per_site_sz1"]) > 1e-8
        or ferro["spin_gap"] < -1e-8
    ):
        raise ValueError("R10 双初态失败模式不匹配")

    validation_summary = fetch / "validation" / "summary.json"
    write_json(validation_summary, {
        "schema_version": 1, "status": "fail", "cell_count": 1, "counts": {"pass": 0, "fail": 1},
        "rows": [{"cell_id": CELL, "validator_status": "fail", "exit_code": 1,
                  "output": str(paths["validation"]), "sha256": sha256(paths["validation"])}],
    })
    handoff_audit = fetch / "handoff_audit.json"
    write_json(handoff_audit, {
        "schema_version": 1, "status": "pass_failure_only", "cell_id": CELL,
        "remote_checksums": "parent_and_two_children_pass", "local_checksums": "pass",
        "non_clobbering_fetch": True,
        "checksum_entries": {"parent": len(parent_hashes), "children": {k: len(v) for k, v in child_hashes.items()}},
        "validator": {"status": "fail", "sha256": sha256(paths["validation"])},
        "accepted_only_eligible": False, "thresholds_relaxed": False,
    })
    failure_summary = fetch / "failure_handoff_summary.json"
    failure = {
        "schema_version": 1, "status": "failed_validation", "cell_id": CELL,
        "params": {"alpha": -0.05, "beta": 0.5, "L": 40}, "budget": 64,
        "artifact": relative(paths["validation"]), "manifest": relative(paths["manifest"]),
        "receipt": relative(paths["receipt"]), "failed_gates": {"center": sorted(CENTER_FAILURES), "ferro_j2": []},
        "strict_numerical_diagnostics": {"center": center, "ferro_j2": ferro},
        "accepted_only_eligible": False,
        "validation_summary": {"artifact": relative(validation_summary), "sha256": sha256(validation_summary)},
        "handoff_audit": {"artifact": relative(handoff_audit), "sha256": sha256(handoff_audit)},
        "r9_failure_provenance_required": True, "r6_half_difference": 0.011877542575884303,
        "r7_failure_provenance_preserved": True, "thresholds_relaxed": False,
    }
    if forbidden(failure):
        raise ValueError("R10 failure handoff 含 value/error")
    write_json(failure_summary, failure)
    print(json.dumps({"status": "fail", "cell": CELL, "summary": str(failure_summary)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
