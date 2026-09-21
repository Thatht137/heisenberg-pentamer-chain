#!/usr/bin/env python3
"""生成 Stage A R13 的 L60 最终级严格重试包。"""

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
STAGE = RUN / "stage-a-beta050-calibration-r13-a0050-L060"
FETCH = RUN / "fetches/stage-a-beta050-calibration-r12-remaining5-20260811-1333"
R12_SPEC = RUN / "stage-a-beta050-calibration-r12-remaining5/parameter-scan.run_spec.json"
R12_SUMMARY = PHASE / "r12_failure_ingestion_summary.json"
R12_AUDIT = PHASE / "r12_failure_ingestion_audit.json"
R12_HANDOFF = FETCH / "failure_handoff_summary.json"
R12_VALIDATION = FETCH / "validation/summary.json"
CALIBRATION = PHASE / "accepted_calibration_through_r9.json"
OBSERVATIONS = PHASE / "observations.json"
ACTION_INDEX = PHASE / "action_index.json"
STANDARD = ROOT / "docs/full_phase_diagram_negative_standard_20260809.md"
R12_CELL = "nega-r12-a0050-b0500-L060"
R13_CELL = "nega-r13-a0050-b0500-L060"
ACTION = "act-7016420e7cbf8fc354b7"
R6_HALF = 0.011877542575884303
SOURCES = [
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


def forbidden(value: Any) -> bool:
    if isinstance(value, dict):
        return any(name in {"value", "error"} or forbidden(item) for name, item in value.items())
    if isinstance(value, list):
        return any(forbidden(item) for item in value)
    return False


def main() -> int:
    generated = [STAGE / name for name in ("parameter-scan.run_spec.json", "r13_source_hashes.sha256", "launch-contract.json")]
    if any(path.exists() for path in generated):
        raise ValueError("R13 launch-ready 文件已存在，拒绝覆盖")
    required = [R12_SPEC, R12_SUMMARY, R12_AUDIT, R12_HANDOFF, R12_VALIDATION,
                CALIBRATION, OBSERVATIONS, ACTION_INDEX, STANDARD]
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)
    summary, audit, handoff, validation = map(load, [R12_SUMMARY, R12_AUDIT, R12_HANDOFF, R12_VALIDATION])
    if (
        summary.get("status") != "blocked_by_validation_failure" or summary.get("cell_id") != R12_CELL
        or summary.get("counts") != {"controller_success_total": 13, "controller_failed_total": 1,
                                     "controller_pending_total": 2, "calibration_accepted_total": 6}
        or summary.get("unmaterialized_cells") != 4
        or summary.get("failed_observation_contains_value_or_error") is not False
        or audit.get("status") != "pass_failure_only" or not all(audit.get("invariants", {}).values())
        or handoff.get("status") != "failed_validation" or handoff.get("budget") != 64
        or handoff.get("accepted_only_eligible") is not False or forbidden(handoff)
        or validation.get("counts") != {"pass": 0, "fail": 1}
        or summary.get("failure_handoff", {}).get("sha256") != sha256(R12_HANDOFF)
        or summary.get("ingestion_audit", {}).get("sha256") != sha256(R12_AUDIT)
        or summary.get("observations", {}).get("sha256") != sha256(OBSERVATIONS)
        or summary.get("action_index", {}).get("sha256") != sha256(ACTION_INDEX)
        or summary.get("accepted_calibration", {}).get("sha256") != sha256(CALIBRATION)
        or summary.get("thresholds_relaxed") is not False
    ):
        raise ValueError("R12 失败接入证据锁不匹配")
    records = load(OBSERVATIONS).get("records", [])
    target = next((row for row in records if row.get("params") == {"alpha": -0.05, "beta": 0.5, "L": 60}), None)
    r11 = next((row for row in records if row.get("params") == {"alpha": -0.05, "beta": 0.5, "L": 40}), None)
    if (
        not target or target.get("status") != "failed" or target.get("budget") != 64
        or target.get("controller_action_id") != ACTION or forbidden(target)
        or target.get("r12_provenance", {}).get("r11_accepted_provenance_preserved") is not True
        or not r11 or r11.get("status") != "success" or r11.get("budget") != 128
        or r11.get("r10_failure_provenance", {}).get("preserved") is not True
    ):
        raise ValueError("R12 failed observation 或历史 provenance 不匹配")
    action = next((row for row in load(ACTION_INDEX).get("actions", []) if row.get("action_id") == ACTION), None)
    if (
        not action or action.get("observation_status") != "failed" or action.get("accepted") is not False
        or action.get("retry_recommendation", {}).get("next_budget") != 128
    ):
        raise ValueError("R12 action_index 未放行 128 sweeps")

    code_hashes = {name: sha256(ROOT / name) for name in SOURCES}
    run_spec = {
        "schema_version": 1, "run_id": "pentamer-negative-phase-stage-a-r13-a0050-L060-20260811",
        "scope": "alpha=-0.05, beta=0.5, L=60; one-cell final-tier strict retry; Fig.9 excluded",
        "controller": "local_only",
        "cells": [{
            "cell_id": R13_CELL, "params": {"alpha": -0.05, "beta": 0.5, "L": 60, "n_units": 12},
            "budget": 128, "stage": "A-R13", "retry_of": R12_CELL,
            "retry_policy": "仅R12失败单元64→128 sweeps；方差、gap及其余门槛不变",
            "controller_action_id": ACTION, "calibration_only": False,
        }],
        "settings": {
            "method": "finite_dmrg_multistart_fullq", "boundary": "OBC",
            "hamiltonian": "five-site unit cell Heisenberg chain, J1=1, J2=alpha, J3=beta",
            "sectors": ["Sz=0", "Sz=1"], "maxdim_by_L": {"60": 1000}, "nsweeps": 128,
            "cutoff": 1e-11, "threads": 8, "q_count": 401, "init_modes": ["center", "ferro_j2"],
            "budget_definition": "每个独立初态均为128 sweeps",
            "acceptance": {"variance_per_site_max": 1e-8, "final_truncation_error_max": 1e-9,
                           "sector_tolerance": 1e-8, "spin_gap_min": -1e-8,
                           "nonnegative_gap_required": True, "q_count_min": 401},
            "offline": True, "execution": "direct SSH; concurrency=1; stop on first failed cell",
        },
        "provenance": {
            "negative_alpha_included": True,
            "r13_reason": "R12双初态仅Sz1方差超门，按64→128最终级单点重试",
            "r12_run_spec_sha256": sha256(R12_SPEC),
            "r12_failure_ingestion_summary_sha256": sha256(R12_SUMMARY),
            "r12_failure_ingestion_audit_sha256": sha256(R12_AUDIT),
            "r12_failure_handoff_sha256": sha256(R12_HANDOFF),
            "r12_validation_summary_sha256": sha256(R12_VALIDATION),
            "accepted_calibration_through_r9_sha256": sha256(CALIBRATION),
            "observations_sha256": sha256(OBSERVATIONS), "action_index_sha256": sha256(ACTION_INDEX),
            "r11_accepted_and_r9_r10_failure_provenance_preserved": True,
            "r6_initial_state_sensitivity_half_difference": R6_HALF,
            "r7_failure_provenance_preserved": True,
            "post_success_continuation": "R12未物化4 cells另建独立续跑批次",
            "standard_sha256": sha256(STANDARD), "manifest_sha256": sha256(ROOT / "Manifest.toml"),
            "project_sha256": sha256(ROOT / "Project.toml"),
            "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                            text=True, check=True).stdout.strip(),
            "code_sha256": code_hashes, "gap_gate_enforced": True,
            "thresholds_relaxed": False, "exploratory_data_not_accepted": True,
        },
    }
    STAGE.mkdir(parents=True, exist_ok=True)
    spec_path, hashes_path = STAGE / "parameter-scan.run_spec.json", STAGE / "r13_source_hashes.sha256"
    write_json(spec_path, run_spec)
    write_lf(hashes_path, "".join(f"{digest}  {name}\n" for name, digest in code_hashes.items()))
    contract = {
        "schema_version": 1, "launch_ready": True, "cell_count": 1, "concurrency": 1,
        "stop_on_first_failure": True, "offline": True, "eta_minutes": {"low": 20, "high": 45},
        "run_spec_sha256": sha256(spec_path), "source_hashes_sha256": sha256(hashes_path),
        "standard_sha256": sha256(STANDARD), "manifest_sha256": sha256(ROOT / "Manifest.toml"),
        "r12_failure_ingestion_summary_sha256": sha256(R12_SUMMARY),
        "r12_failure_ingestion_audit_sha256": sha256(R12_AUDIT),
        "r12_failure_handoff_sha256": sha256(R12_HANDOFF),
        "r12_validation_summary_sha256": sha256(R12_VALIDATION),
        "accepted_calibration_through_r9_sha256": sha256(CALIBRATION),
        "observations_sha256": sha256(OBSERVATIONS), "action_index_sha256": sha256(ACTION_INDEX),
        "r6_r7_r9_r10_r11_evidence_preserved": True, "gap_gate_enforced": True,
        "nonnegative_gap_min": -1e-8, "thresholds_relaxed": False,
    }
    write_json(STAGE / "launch-contract.json", contract)
    print(json.dumps({"run_spec": str(spec_path), "cells": 1, "eta_minutes": [20, 45]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
