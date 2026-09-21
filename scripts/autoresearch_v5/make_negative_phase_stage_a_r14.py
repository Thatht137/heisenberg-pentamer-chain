#!/usr/bin/env python3
"""生成 Stage A R14 未物化四单元续跑批次。"""

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
STAGE = RUN / "stage-a-beta050-calibration-r14-remaining4"
R13_SUMMARY = PHASE / "r13_success_ingestion_summary.json"
R13_AUDIT = PHASE / "r13_success_ingestion_audit.json"
R13_FETCH = RUN / "fetches/stage-a-beta050-calibration-r13-a0050-L060-20260811-1434"
R13_HANDOFF = R13_FETCH / "success_handoff_summary.json"
R13_VALIDATION = R13_FETCH / "validation/summary.json"
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
    "scripts/autoresearch_v5/launch_negative_phase_stage_a_r14_remaining4.sh",
]
CELL_SPECS = [
    ("nega-r14-a0050-b0500-L080", -0.05, 80, 16, None, True),
    ("nega-r14-a0025-b0500-L040", -0.025, 40, 8, "act-4503b7acb169c6a5092f", False),
    ("nega-r14-a0025-b0500-L060", -0.025, 60, 12, "act-3d1ab066156655e22ec8", False),
    ("nega-r14-a0025-b0500-L080", -0.025, 80, 16, None, True),
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
    generated = [STAGE / name for name in ("parameter-scan.run_spec.json", "r14_source_hashes.sha256", "launch-contract.json")]
    if any(path.exists() for path in generated):
        raise ValueError("R14 launch-ready 文件已存在，拒绝覆盖")
    for path in (R13_SUMMARY, R13_AUDIT, R13_HANDOFF, R13_VALIDATION,
                 CALIBRATION, OBSERVATIONS, ACTION_INDEX, STANDARD):
        if not path.is_file(): raise FileNotFoundError(path)
    summary, audit, handoff, validation = map(load, [R13_SUMMARY, R13_AUDIT, R13_HANDOFF, R13_VALIDATION])
    if (
        summary.get("status") != "accepted" or summary.get("cell_id") != "nega-r13-a0050-b0500-L060"
        or summary.get("counts") != {"controller_success_total": 14, "controller_failed_total": 0,
                                     "controller_pending_total": 2, "calibration_accepted_total": 6}
        or summary.get("history_provenance_preserved") is not True
        or audit.get("status") != "pass" or not all(audit.get("invariants", {}).values())
        or handoff.get("status") != "accepted" or handoff.get("budget") != 128
        or validation.get("counts") != {"pass": 1, "fail": 0}
        or summary.get("success_handoff", {}).get("sha256") != sha256(R13_HANDOFF)
        or summary.get("ingestion_audit", {}).get("sha256") != sha256(R13_AUDIT)
        or summary.get("observations", {}).get("sha256") != sha256(OBSERVATIONS)
        or summary.get("action_index", {}).get("sha256") != sha256(ACTION_INDEX)
        or summary.get("accepted_calibration", {}).get("sha256") != sha256(CALIBRATION)
        or summary.get("thresholds_relaxed") is not False
    ): raise ValueError("R13 accepted-only 基线不匹配")
    observations = load(OBSERVATIONS).get("records", [])
    counts = {name: sum(row.get("status") == name for row in observations) for name in ("success", "failed", "pending")}
    if counts != {"success": 14, "failed": 0, "pending": 2}: raise ValueError(f"R13 controller 计数异常: {counts}")
    indexed = {(row["params"]["alpha"], row["params"]["beta"], row["params"]["L"]): row for row in observations}
    for length in (40, 60):
        row = indexed.get((-0.025, 0.5, length))
        if not row or row.get("status") != "pending" or row.get("budget") != 32:
            raise ValueError(f"R14 controller 来源不是 pending: L={length}")
    for length in (40, 60):
        row = indexed.get((-0.05, 0.5, length))
        if not row or row.get("status") != "success" or row.get("budget") != 128:
            raise ValueError("邻近 alpha 收敛依据不匹配")
    action_rows = {row["action_id"]: row for row in load(ACTION_INDEX).get("actions", [])}
    for _, _, _, _, action_id, calibration_only in CELL_SPECS:
        if not calibration_only:
            row = action_rows.get(action_id)
            if not row or row.get("observation_status") != "pending" or row.get("accepted") is not False:
                raise ValueError(f"R14 action 未保持 pending: {action_id}")

    cells = []
    for cell_id, alpha, length, units, action_id, calibration_only in CELL_SPECS:
        cell = {"cell_id": cell_id, "params": {"alpha": alpha, "beta": 0.5, "L": length, "n_units": units},
                "budget": 64, "stage": "A-R14-remaining4", "controller_action_id": action_id,
                "calibration_only": calibration_only, "continued_from": cell_id.replace("nega-r14-", "nega-r12-")}
        if alpha == -0.025 and not calibration_only:
            cell["budget_promotion_reason"] = "邻近alpha=-0.05的L40/L60均需128 sweeps才严格通过，保守提升32→64"
            cell["original_action_budget"] = 32
        cells.append(cell)
    code_hashes = {name: sha256(ROOT / name) for name in SOURCES}
    run_spec = {"schema_version": 1, "run_id": "pentamer-negative-phase-stage-a-r14-remaining4-20260811",
        "scope": "beta=0.5 Stage A remaining 4 cells; alpha=-0.05,-0.025; Fig.9 excluded",
        "controller": "local_only", "cells": cells,
        "settings": {"method": "finite_dmrg_multistart_fullq", "boundary": "OBC",
            "hamiltonian": "five-site unit cell Heisenberg chain, J1=1, J2=alpha, J3=beta",
            "sectors": ["Sz=0", "Sz=1"], "maxdim_by_L": {"40": 800, "60": 1000, "80": 1200},
            "nsweeps": 64, "cutoff": 1e-11, "threads": 8, "q_count": 401,
            "init_modes": ["center", "ferro_j2"], "budget_definition": "每个独立初态均为64 sweeps",
            "acceptance": {"variance_per_site_max": 1e-8, "final_truncation_error_max": 1e-9,
                           "sector_tolerance": 1e-8, "spin_gap_min": -1e-8,
                           "nonnegative_gap_required": True, "q_count_min": 401},
            "offline": True, "execution": "direct SSH; concurrency=1; stop on first failed cell"},
        "provenance": {"negative_alpha_included": True,
            "continuation_reason": "R13严格接入后独立续跑R12未物化四单元",
            "conservative_budget_policy": "alpha=-0.025的L40/L60由32提升至64；邻近alpha=-0.05的同尺寸需128才通过",
            "r13_success_ingestion_summary_sha256": sha256(R13_SUMMARY),
            "r13_success_ingestion_audit_sha256": sha256(R13_AUDIT),
            "r13_success_handoff_sha256": sha256(R13_HANDOFF),
            "r13_validation_summary_sha256": sha256(R13_VALIDATION),
            "accepted_calibration_through_r9_sha256": sha256(CALIBRATION),
            "observations_sha256": sha256(OBSERVATIONS), "action_index_sha256": sha256(ACTION_INDEX),
            "r12_and_earlier_history_preserved": True,
            "r6_initial_state_sensitivity_half_difference": R6_HALF,
            "r7_failure_provenance_preserved": True,
            "standard_sha256": sha256(STANDARD), "manifest_sha256": sha256(ROOT / "Manifest.toml"),
            "project_sha256": sha256(ROOT / "Project.toml"),
            "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                            text=True, check=True).stdout.strip(),
            "code_sha256": code_hashes, "gap_gate_enforced": True,
            "thresholds_relaxed": False, "exploratory_data_not_accepted": True}}
    STAGE.mkdir(parents=True, exist_ok=True)
    spec_path, hashes_path = STAGE / "parameter-scan.run_spec.json", STAGE / "r14_source_hashes.sha256"
    write_json(spec_path, run_spec)
    write_lf(hashes_path, "".join(f"{digest}  {name}\n" for name, digest in code_hashes.items()))
    contract = {"schema_version": 1, "launch_ready": True, "cell_count": 4,
        "controller_cell_count": 2, "calibration_cell_count": 2, "concurrency": 1,
        "stop_on_first_failure": True, "offline": True, "eta_hours": {"low": 1.0, "high": 2.0},
        "budget_schedule": {"a0050_L080": 64, "a0025_L040": 64, "a0025_L060": 64, "a0025_L080": 64},
        "run_spec_sha256": sha256(spec_path), "source_hashes_sha256": sha256(hashes_path),
        "standard_sha256": sha256(STANDARD), "manifest_sha256": sha256(ROOT / "Manifest.toml"),
        "r13_success_ingestion_summary_sha256": sha256(R13_SUMMARY),
        "observations_sha256": sha256(OBSERVATIONS), "action_index_sha256": sha256(ACTION_INDEX),
        "history_evidence_preserved": True, "gap_gate_enforced": True, "thresholds_relaxed": False}
    write_json(STAGE / "launch-contract.json", contract)
    print(json.dumps({"run_spec": str(spec_path), "cells": 4, "eta_hours": [1.0, 2.0]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
