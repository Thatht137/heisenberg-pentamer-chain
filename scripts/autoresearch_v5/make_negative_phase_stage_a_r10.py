#!/usr/bin/env python3
"""生成 Stage A R10 的 L40 单点严格重试包。"""

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
STAGE = RUN / "stage-a-beta050-calibration-r10-a0050-L040"
FETCH = RUN / "fetches/stage-a-beta050-calibration-r9-remaining7-20260811-0932"
R9_SPEC = RUN / "stage-a-beta050-calibration-r9-remaining7/parameter-scan.run_spec.json"
R9_SUMMARY = PHASE / "r9_partial_ingestion_summary.json"
R9_AUDIT = PHASE / "r9_partial_ingestion_audit.json"
R9_HANDOFF = FETCH / "partial_handoff_summary.json"
R9_VALIDATION = FETCH / "validation/summary.json"
CALIBRATION = PHASE / "accepted_calibration_through_r9.json"
OBSERVATIONS = PHASE / "observations.json"
ACTION_INDEX = PHASE / "action_index.json"
STANDARD = ROOT / "docs/full_phase_diagram_negative_standard_20260809.md"
R9_CELL = "nega-r9-a0050-b0500-L040"
R10_CELL = "nega-r10-a0050-b0500-L040"
ACTION = "act-fffdf93a9cae183cb1c1"
R6_HALF = 0.011877542575884303
SOURCE_FILES = [
    "Project.toml", "Manifest.toml", "docs/full_phase_diagram_negative_standard_20260809.md",
    "src/PentamerChain.jl", "src/hamiltonian.jl", "src/order_parameters.jl",
    "scripts/autoresearch_v5/progress.py", "scripts/autoresearch_v5/negative_static_cell.jl",
    "scripts/autoresearch_v5/run_negative_static_cell.py",
    "scripts/autoresearch_v5/run_negative_phase_structure_cell.py",
    "scripts/autoresearch_v5/run_negative_phase_structure_batch.py",
    "scripts/autoresearch_v5/validate_negative_phase_run.py",
]


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    handle, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    except BaseException:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass
        raise


def has_measurement(value: Any) -> bool:
    if isinstance(value, dict):
        return any(name in {"value", "error"} or has_measurement(item) for name, item in value.items())
    if isinstance(value, list):
        return any(has_measurement(item) for item in value)
    return False


def main() -> int:
    generated = [STAGE / name for name in ("parameter-scan.run_spec.json", "r10_source_hashes.sha256", "launch-contract.json")]
    existing = [path for path in generated if path.exists()]
    if existing and existing != [generated[0]]:
        raise ValueError("R10 launch-ready 文件已存在，拒绝覆盖")
    required = [R9_SPEC, R9_SUMMARY, R9_AUDIT, R9_HANDOFF, R9_VALIDATION,
                CALIBRATION, OBSERVATIONS, ACTION_INDEX, STANDARD]
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)

    summary, audit, handoff, validation = map(load, [R9_SUMMARY, R9_AUDIT, R9_HANDOFF, R9_VALIDATION])
    if (
        summary.get("status") != "partial_failure_ingested"
        or summary.get("failed_controller_cell") != R9_CELL
        or summary.get("counts") != {"controller_success_total": 12, "controller_failed_total": 1,
                                     "controller_pending_total": 3, "calibration_accepted_total": 6}
        or summary.get("failed_observation_contains_value_or_error") is not False
        or audit.get("status") != "pass_partial_failure"
        or not all(audit.get("invariants", {}).values())
        or handoff.get("status") != "partial_failure"
        or validation.get("counts") != {"pass": 1, "fail": 1}
        or summary.get("accepted_calibration", {}).get("sha256") != sha256(CALIBRATION)
        or summary.get("handoff", {}).get("sha256") != sha256(R9_HANDOFF)
        or summary.get("ingestion_audit", {}).get("sha256") != sha256(R9_AUDIT)
        or summary.get("observations", {}).get("sha256") != sha256(OBSERVATIONS)
        or summary.get("action_index", {}).get("sha256") != sha256(ACTION_INDEX)
        or summary.get("thresholds_relaxed") is not False
    ):
        raise ValueError("R9 接入证据锁不匹配")

    records = load(OBSERVATIONS).get("records", [])
    target = next((row for row in records if row.get("params") == {"alpha": -0.05, "beta": 0.5, "L": 40}), None)
    r6 = next((row for row in records if row.get("params") == {"alpha": -0.1, "beta": 0.5, "L": 40}), None)
    r8 = next((row for row in records if row.get("params") == {"alpha": -0.1, "beta": 0.5, "L": 60}), None)
    if (
        not target or target.get("status") != "failed" or target.get("controller_action_id") != ACTION
        or target.get("budget") != 32 or has_measurement(target)
        or target.get("failure_evidence", {}).get("failed_gates") != ["variance_sz0_per_site_le_1e-8", "variance_sz1_per_site_le_1e-8"]
        or not r6 or r6.get("error") != R6_HALF
        or not r8 or r8.get("r7_failure_provenance", {}).get("preserved") is not True
    ):
        raise ValueError("R9 失败目标或 R6/R7 provenance 不匹配")
    action = next((row for row in load(ACTION_INDEX).get("actions", []) if row.get("action_id") == ACTION), None)
    if not action or action.get("observation_status") != "failed" or action.get("accepted") is not False:
        raise ValueError("R9 action_index 未锁定失败")

    code_hashes = {name: sha256(ROOT / name) for name in SOURCE_FILES}
    cell = {
        "cell_id": R10_CELL, "params": {"alpha": -0.05, "beta": 0.5, "L": 40, "n_units": 8},
        "budget": 64, "stage": "A-R10", "retry_of": R9_CELL,
        "retry_policy": "仅R9方差失败单元32→64 sweeps；其余门槛不变",
        "controller_action_id": ACTION, "calibration_only": False,
    }
    settings = {
        "method": "finite_dmrg_multistart_fullq", "boundary": "OBC",
        "hamiltonian": "five-site unit cell Heisenberg chain, J1=1, J2=alpha, J3=beta",
        "sectors": ["Sz=0", "Sz=1"], "maxdim_by_L": {"40": 800}, "nsweeps": 64,
        "cutoff": 1e-11, "threads": 8, "q_count": 401, "init_modes": ["center", "ferro_j2"],
        "budget_definition": "每个独立初态均为64 sweeps",
        "acceptance": {"variance_per_site_max": 1e-8, "final_truncation_error_max": 1e-9,
                       "sector_tolerance": 1e-8, "spin_gap_min": -1e-8,
                       "nonnegative_gap_required": True, "q_count_min": 401},
        "offline": True, "execution": "direct SSH; concurrency=1; stop on first failed cell",
    }
    run_spec = {
        "schema_version": 1, "run_id": "pentamer-negative-phase-stage-a-r10-a0050-L040-20260811",
        "scope": "alpha=-0.05, beta=0.5, L=40; one-cell strict retry; Fig.9 excluded",
        "controller": "local_only", "cells": [cell], "settings": settings,
        "provenance": {
            "negative_alpha_included": True, "r10_reason": "R9双初态仅方差超门，按32→64单点重试",
            "r9_run_spec_sha256": sha256(R9_SPEC), "r9_partial_ingestion_summary_sha256": sha256(R9_SUMMARY),
            "r9_partial_ingestion_audit_sha256": sha256(R9_AUDIT),
            "r9_partial_handoff_sha256": sha256(R9_HANDOFF),
            "r9_validation_summary_sha256": sha256(R9_VALIDATION),
            "accepted_calibration_through_r9_sha256": sha256(CALIBRATION),
            "observations_sha256": sha256(OBSERVATIONS), "action_index_sha256": sha256(ACTION_INDEX),
            "r6_initial_state_sensitivity_half_difference": R6_HALF,
            "r7_failure_provenance_preserved": True, "r6_half_difference_preserved": True,
            "standard_sha256": sha256(STANDARD), "manifest_sha256": sha256(ROOT / "Manifest.toml"),
            "project_sha256": sha256(ROOT / "Project.toml"),
            "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                            text=True, check=True).stdout.strip(),
            "code_sha256": code_hashes, "gap_gate_enforced": True,
            "thresholds_relaxed": False, "exploratory_data_not_accepted": True,
        },
    }
    STAGE.mkdir(parents=True, exist_ok=True)
    spec_path, hashes_path = STAGE / "parameter-scan.run_spec.json", STAGE / "r10_source_hashes.sha256"
    write_json(spec_path, run_spec)
    with hashes_path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("".join(f"{digest}  {name}\n" for name, digest in code_hashes.items()))
    contract = {
        "schema_version": 1, "launch_ready": True, "cell_count": 1, "concurrency": 1, "offline": True,
        "eta_minutes": {"low": 10, "high": 25}, "run_spec_sha256": sha256(spec_path),
        "source_hashes_sha256": sha256(hashes_path), "standard_sha256": sha256(STANDARD),
        "manifest_sha256": sha256(ROOT / "Manifest.toml"),
        "r9_partial_ingestion_summary_sha256": sha256(R9_SUMMARY),
        "r9_partial_ingestion_audit_sha256": sha256(R9_AUDIT),
        "r9_partial_handoff_sha256": sha256(R9_HANDOFF),
        "r9_validation_summary_sha256": sha256(R9_VALIDATION),
        "accepted_calibration_through_r9_sha256": sha256(CALIBRATION),
        "observations_sha256": sha256(OBSERVATIONS), "action_index_sha256": sha256(ACTION_INDEX),
        "r6_r7_evidence_preserved": True, "gap_gate_enforced": True,
        "nonnegative_gap_min": -1e-8, "thresholds_relaxed": False,
    }
    write_json(STAGE / "launch-contract.json", contract)
    print(json.dumps({"run_spec": str(spec_path), "cells": 1, "eta_minutes": [10, 25]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
