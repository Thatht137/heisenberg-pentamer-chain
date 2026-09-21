#!/usr/bin/env python3
"""生成 Stage A R12 剩余五单元顺序批次。"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha"
PHASE = RUN / "phase-diagram-v2"
STAGE = RUN / "stage-a-beta050-calibration-r12-remaining5"
R11_SUMMARY = PHASE / "r11_success_ingestion_summary.json"
R11_AUDIT = PHASE / "r11_success_ingestion_audit.json"
R11_FETCH = RUN / "fetches/stage-a-beta050-calibration-r11-a0050-L040-20260811-1133"
R11_HANDOFF = R11_FETCH / "success_handoff_summary.json"
R11_VALIDATION = R11_FETCH / "validation/summary.json"
CALIBRATION = PHASE / "accepted_calibration_through_r9.json"
OBSERVATIONS = PHASE / "observations.json"
ACTION_INDEX = PHASE / "action_index.json"
STANDARD = ROOT / "docs/full_phase_diagram_negative_standard_20260809.md"
R6_HALF = 0.011877542575884303
SOURCES = [
    "Project.toml", "Manifest.toml", "docs/full_phase_diagram_negative_standard_20260809.md",
    "src/PentamerChain.jl", "src/hamiltonian.jl", "src/order_parameters.jl",
    "scripts/autoresearch_v5/progress.py", "scripts/autoresearch_v5/negative_static_cell.jl",
    "scripts/autoresearch_v5/run_negative_static_cell.py",
    "scripts/autoresearch_v5/run_negative_phase_structure_cell.py",
    "scripts/autoresearch_v5/run_negative_phase_structure_batch.py",
    "scripts/autoresearch_v5/validate_negative_phase_run.py",
    "scripts/autoresearch_v5/launch_negative_phase_stage_a_r12_remaining5.sh",
]
CELL_SPECS = [
    ("nega-r12-a0050-b0500-L060", -0.05, 60, 12, 64, "act-7016420e7cbf8fc354b7", False),
    ("nega-r12-a0050-b0500-L080", -0.05, 80, 16, 64, None, True),
    ("nega-r12-a0025-b0500-L040", -0.025, 40, 8, 32, "act-4503b7acb169c6a5092f", False),
    ("nega-r12-a0025-b0500-L060", -0.025, 60, 12, 32, "act-3d1ab066156655e22ec8", False),
    ("nega-r12-a0025-b0500-L080", -0.025, 80, 16, 64, None, True),
]


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    except BaseException:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass
        raise


def write_lf(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


def main() -> int:
    generated = [STAGE / name for name in ("parameter-scan.run_spec.json", "r12_source_hashes.sha256", "launch-contract.json")]
    if any(path.exists() for path in generated):
        raise ValueError("R12 launch-ready 文件已存在，拒绝覆盖")
    required = [R11_SUMMARY, R11_AUDIT, R11_HANDOFF, R11_VALIDATION,
                CALIBRATION, OBSERVATIONS, ACTION_INDEX, STANDARD]
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)
    summary, audit, handoff, validation = map(load, [R11_SUMMARY, R11_AUDIT, R11_HANDOFF, R11_VALIDATION])
    if (
        summary.get("status") != "accepted" or summary.get("cell_id") != "nega-r11-a0050-b0500-L040"
        or summary.get("counts") != {"controller_success_total": 13, "controller_failed_total": 0,
                                     "controller_pending_total": 3, "calibration_accepted_total": 6}
        or summary.get("r9_r10_failure_provenance_preserved") is not True
        or audit.get("status") != "pass" or not all(audit.get("invariants", {}).values())
        or handoff.get("status") != "accepted" or handoff.get("budget") != 128
        or validation.get("counts") != {"pass": 1, "fail": 0}
        or summary.get("success_handoff", {}).get("sha256") != sha256(R11_HANDOFF)
        or summary.get("ingestion_audit", {}).get("sha256") != sha256(R11_AUDIT)
        or summary.get("observations", {}).get("sha256") != sha256(OBSERVATIONS)
        or summary.get("action_index", {}).get("sha256") != sha256(ACTION_INDEX)
        or summary.get("accepted_calibration", {}).get("sha256") != sha256(CALIBRATION)
        or summary.get("thresholds_relaxed") is not False
    ):
        raise ValueError("R11 accepted-only 基线不匹配")
    observations = load(OBSERVATIONS).get("records", [])
    counts = {name: sum(row.get("status") == name for row in observations) for name in ("success", "failed", "pending")}
    if counts != {"success": 13, "failed": 0, "pending": 3}:
        raise ValueError(f"R11 controller 计数异常: {counts}")
    indexed = {(row["params"]["alpha"], row["params"]["beta"], row["params"]["L"]): row for row in observations}
    for alpha, length in ((-0.05, 60), (-0.025, 40), (-0.025, 60)):
        row = indexed.get((alpha, 0.5, length))
        if not row or row.get("status") != "pending" or row.get("budget") != 32:
            raise ValueError(f"R12 controller 来源不是 pending: {(alpha, length)}")
    accepted = indexed.get((-0.05, 0.5, 40))
    if (
        not accepted or accepted.get("status") != "success" or accepted.get("budget") != 128
        or accepted.get("r10_failure_provenance", {}).get("preserved") is not True
    ):
        raise ValueError("R12 保守预算依据不匹配")
    action_rows = {row["action_id"]: row for row in load(ACTION_INDEX).get("actions", [])}
    for _, _, _, _, _, action_id, calibration_only in CELL_SPECS:
        if not calibration_only:
            row = action_rows.get(action_id)
            if not row or row.get("observation_status") != "pending" or row.get("accepted") is not False:
                raise ValueError(f"R12 action 未保持 pending: {action_id}")

    cells = []
    for cell_id, alpha, length, units, budget, action_id, calibration_only in CELL_SPECS:
        cell = {
            "cell_id": cell_id, "params": {"alpha": alpha, "beta": 0.5, "L": length, "n_units": units},
            "budget": budget, "stage": "A-R12-remaining5", "controller_action_id": action_id,
            "calibration_only": calibration_only, "continued_from": cell_id.replace("nega-r12-", "nega-r9-"),
        }
        if alpha == -0.05 and length == 60:
            cell["budget_promotion_reason"] = "同alpha的L40需128 sweeps才通过，L60保守提升32→64"
            cell["original_action_budget"] = 32
        cells.append(cell)
    code_hashes = {name: sha256(ROOT / name) for name in SOURCES}
    run_spec = {
        "schema_version": 1, "run_id": "pentamer-negative-phase-stage-a-r12-remaining5-20260811",
        "scope": "beta=0.5 Stage A remaining 5 cells; alpha=-0.05,-0.025; Fig.9 excluded",
        "controller": "local_only", "cells": cells,
        "settings": {
            "method": "finite_dmrg_multistart_fullq", "boundary": "OBC",
            "hamiltonian": "five-site unit cell Heisenberg chain, J1=1, J2=alpha, J3=beta",
            "sectors": ["Sz=0", "Sz=1"], "maxdim_by_L": {"40": 800, "60": 1000, "80": 1200},
            "nsweeps": 32, "cutoff": 1e-11, "threads": 8, "q_count": 401,
            "init_modes": ["center", "ferro_j2"], "budget_definition": "cell budget覆盖默认nsweeps；每个独立初态使用相同预算",
            "acceptance": {"variance_per_site_max": 1e-8, "final_truncation_error_max": 1e-9,
                           "sector_tolerance": 1e-8, "spin_gap_min": -1e-8,
                           "nonnegative_gap_required": True, "q_count_min": 401},
            "offline": True, "execution": "direct SSH; concurrency=1; stop on first failed cell",
        },
        "provenance": {
            "negative_alpha_included": True,
            "continuation_reason": "R11严格接入后续跑Stage A剩余三个controller点与两个L80校准点",
            "conservative_budget_policy": "alpha=-0.05,L60由32提升至64；因同alpha,L40需128才严格通过",
            "r11_success_ingestion_summary_sha256": sha256(R11_SUMMARY),
            "r11_success_ingestion_audit_sha256": sha256(R11_AUDIT),
            "r11_success_handoff_sha256": sha256(R11_HANDOFF),
            "r11_validation_summary_sha256": sha256(R11_VALIDATION),
            "accepted_calibration_through_r9_sha256": sha256(CALIBRATION),
            "observations_sha256": sha256(OBSERVATIONS), "action_index_sha256": sha256(ACTION_INDEX),
            "r9_r10_failure_provenance_preserved": True,
            "r6_initial_state_sensitivity_half_difference": R6_HALF,
            "r7_failure_provenance_preserved": True,
            "standard_sha256": sha256(STANDARD), "manifest_sha256": sha256(ROOT / "Manifest.toml"),
            "project_sha256": sha256(ROOT / "Project.toml"),
            "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                            text=True, check=True).stdout.strip(),
            "code_sha256": code_hashes, "gap_gate_enforced": True,
            "thresholds_relaxed": False, "exploratory_data_not_accepted": True,
        },
    }
    STAGE.mkdir(parents=True, exist_ok=True)
    spec_path, hashes_path = STAGE / "parameter-scan.run_spec.json", STAGE / "r12_source_hashes.sha256"
    write_json(spec_path, run_spec)
    write_lf(hashes_path, "".join(f"{digest}  {name}\n" for name, digest in code_hashes.items()))
    contract = {
        "schema_version": 1, "launch_ready": True, "cell_count": 5,
        "controller_cell_count": 3, "calibration_cell_count": 2, "concurrency": 1,
        "stop_on_first_failure": True, "offline": True, "eta_hours": {"low": 1.0, "high": 2.5},
        "budget_schedule": {"a0050_L060": 64, "a0050_L080": 64,
                            "a0025_L040": 32, "a0025_L060": 32, "a0025_L080": 64},
        "run_spec_sha256": sha256(spec_path), "source_hashes_sha256": sha256(hashes_path),
        "standard_sha256": sha256(STANDARD), "manifest_sha256": sha256(ROOT / "Manifest.toml"),
        "r11_success_ingestion_summary_sha256": sha256(R11_SUMMARY),
        "observations_sha256": sha256(OBSERVATIONS), "action_index_sha256": sha256(ACTION_INDEX),
        "r6_r7_r9_r10_evidence_preserved": True, "gap_gate_enforced": True,
        "thresholds_relaxed": False,
    }
    write_json(STAGE / "launch-contract.json", contract)
    print(json.dumps({"run_spec": str(spec_path), "cells": 5, "eta_hours": [1.0, 2.5]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
