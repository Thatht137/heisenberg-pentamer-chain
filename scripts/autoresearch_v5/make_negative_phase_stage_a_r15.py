#!/usr/bin/env python3
"""生成 Stage A R15 的 L80 最终级校准重试包。"""

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
STAGE = RUN / "stage-a-beta050-calibration-r15-a0050-L080"
R14_SUMMARY = PHASE / "r14_failure_ingestion_summary.json"
R14_AUDIT = PHASE / "r14_failure_ingestion_audit.json"
R14_FAILED = PHASE / "failed_calibration_r14.json"
R14_HANDOFF = RUN / "fetches/stage-a-beta050-calibration-r14-remaining4-20260811-1556/failure_handoff_summary.json"
CALIBRATION = PHASE / "accepted_calibration_through_r9.json"
OBSERVATIONS = PHASE / "observations.json"
ACTION_INDEX = PHASE / "action_index.json"
STANDARD = ROOT / "docs/full_phase_diagram_negative_standard_20260809.md"
R6_HALF = 0.011877542575884303
SOURCES = ["Project.toml", "Manifest.toml", "docs/full_phase_diagram_negative_standard_20260809.md",
    "src/PentamerChain.jl", "src/hamiltonian.jl", "src/order_parameters.jl",
    "scripts/autoresearch_v5/progress.py", "scripts/autoresearch_v5/negative_static_cell.jl",
    "scripts/autoresearch_v5/run_negative_static_cell.py",
    "scripts/autoresearch_v5/run_negative_phase_structure_cell.py",
    "scripts/autoresearch_v5/run_negative_phase_structure_batch.py",
    "scripts/autoresearch_v5/validate_negative_phase_run.py"]


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
            stream.flush(); os.fsync(stream.fileno())
        os.replace(name, path)
    except BaseException:
        try: os.unlink(name)
        except FileNotFoundError: pass
        raise


def write_lf(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


def main() -> int:
    generated = [STAGE / name for name in ("parameter-scan.run_spec.json", "r15_source_hashes.sha256", "launch-contract.json")]
    if any(path.exists() for path in generated): raise ValueError("R15 launch-ready 文件已存在，拒绝覆盖")
    for path in (R14_SUMMARY, R14_AUDIT, R14_FAILED, R14_HANDOFF,
                 CALIBRATION, OBSERVATIONS, ACTION_INDEX, STANDARD):
        if not path.is_file(): raise FileNotFoundError(path)
    summary, audit, failed = map(load, [R14_SUMMARY, R14_AUDIT, R14_FAILED])
    if (
        summary.get("status") != "blocked_calibration_failure" or summary.get("cell_id") != "nega-r14-a0050-b0500-L080"
        or summary.get("counts") != {"controller_success_total": 14, "controller_failed_total": 0,
                                     "controller_pending_total": 2, "calibration_accepted_total": 6}
        or summary.get("failed_calibration", {}).get("sha256") != sha256(R14_FAILED)
        or summary.get("failure_handoff", {}).get("sha256") != sha256(R14_HANDOFF)
        or summary.get("ingestion_audit", {}).get("sha256") != sha256(R14_AUDIT)
        or summary.get("observations", {}).get("sha256") != sha256(OBSERVATIONS)
        or summary.get("action_index", {}).get("sha256") != sha256(ACTION_INDEX)
        or summary.get("accepted_calibration", {}).get("sha256") != sha256(CALIBRATION)
        or audit.get("status") != "pass_calibration_failure_only"
        or failed.get("status") != "failed_calibration" or failed.get("budget") != 64
        or failed.get("accepted_only_eligible") is not False
        or summary.get("thresholds_relaxed") is not False
    ): raise ValueError("R14 calibration failure 基线不匹配")
    code_hashes = {name: sha256(ROOT / name) for name in SOURCES}
    run_spec = {"schema_version": 1, "run_id": "pentamer-negative-phase-stage-a-r15-a0050-L080-20260811",
        "scope": "alpha=-0.05, beta=0.5, L=80; final-tier calibration retry; Fig.9 excluded",
        "controller": "local_only",
        "cells": [{"cell_id": "nega-r15-a0050-b0500-L080",
                   "params": {"alpha": -0.05, "beta": 0.5, "L": 80, "n_units": 16},
                   "budget": 128, "stage": "A-R15", "retry_of": "nega-r14-a0050-b0500-L080",
                   "retry_policy": "仅R14校准失败单元64→128 sweeps；所有门槛不变",
                   "controller_action_id": None, "calibration_only": True}],
        "settings": {"method": "finite_dmrg_multistart_fullq", "boundary": "OBC",
            "hamiltonian": "five-site unit cell Heisenberg chain, J1=1, J2=alpha, J3=beta",
            "sectors": ["Sz=0", "Sz=1"], "maxdim_by_L": {"80": 1200}, "nsweeps": 128,
            "cutoff": 1e-11, "threads": 8, "q_count": 401, "init_modes": ["center", "ferro_j2"],
            "budget_definition": "每个独立初态均为128 sweeps",
            "acceptance": {"variance_per_site_max": 1e-8, "final_truncation_error_max": 1e-9,
                           "sector_tolerance": 1e-8, "spin_gap_min": -1e-8,
                           "nonnegative_gap_required": True, "q_count_min": 401},
            "offline": True, "execution": "direct SSH; concurrency=1; stop on first failed cell"},
        "provenance": {"negative_alpha_included": True,
            "r15_reason": "R14双初态方差超门，按64→128最后一级校准重试",
            "r14_failure_ingestion_summary_sha256": sha256(R14_SUMMARY),
            "r14_failure_ingestion_audit_sha256": sha256(R14_AUDIT),
            "r14_failed_calibration_sha256": sha256(R14_FAILED),
            "r14_failure_handoff_sha256": sha256(R14_HANDOFF),
            "accepted_calibration_through_r9_sha256": sha256(CALIBRATION),
            "observations_sha256": sha256(OBSERVATIONS), "action_index_sha256": sha256(ACTION_INDEX),
            "r14_and_earlier_failure_provenance_preserved": True,
            "r6_initial_state_sensitivity_half_difference": R6_HALF,
            "standard_sha256": sha256(STANDARD), "manifest_sha256": sha256(ROOT / "Manifest.toml"),
            "project_sha256": sha256(ROOT / "Project.toml"),
            "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                            text=True, check=True).stdout.strip(),
            "code_sha256": code_hashes, "gap_gate_enforced": True,
            "thresholds_relaxed": False, "exploratory_data_not_accepted": True}}
    STAGE.mkdir(parents=True, exist_ok=True)
    spec_path, hashes_path = STAGE / "parameter-scan.run_spec.json", STAGE / "r15_source_hashes.sha256"
    write_json(spec_path, run_spec)
    write_lf(hashes_path, "".join(f"{digest}  {name}\n" for name, digest in code_hashes.items()))
    contract = {"schema_version": 1, "launch_ready": True, "cell_count": 1, "calibration_cell_count": 1,
        "concurrency": 1, "stop_on_first_failure": True, "offline": True,
        "eta_minutes": {"low": 25, "high": 60}, "run_spec_sha256": sha256(spec_path),
        "source_hashes_sha256": sha256(hashes_path), "standard_sha256": sha256(STANDARD),
        "manifest_sha256": sha256(ROOT / "Manifest.toml"),
        "r14_failure_ingestion_summary_sha256": sha256(R14_SUMMARY),
        "r14_failed_calibration_sha256": sha256(R14_FAILED),
        "accepted_calibration_through_r9_sha256": sha256(CALIBRATION),
        "observations_sha256": sha256(OBSERVATIONS), "action_index_sha256": sha256(ACTION_INDEX),
        "history_evidence_preserved": True, "gap_gate_enforced": True,
        "nonnegative_gap_min": -1e-8, "thresholds_relaxed": False}
    write_json(STAGE / "launch-contract.json", contract)
    print(json.dumps({"run_spec": str(spec_path), "cells": 1, "eta_minutes": [25, 60]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
