#!/usr/bin/env python3
"""生成 Stage A R16 三初态收敛修复包。"""

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
STAGE = RUN / "stage-a-beta050-calibration-r16-a0050-L080"
SUMMARY = PHASE / "r15_terminal_ingestion_summary.json"
AUDIT = PHASE / "r15_terminal_ingestion_audit.json"
FAILED = PHASE / "failed_calibration_r15.json"
CALIBRATION = PHASE / "accepted_calibration_through_r9.json"
OBSERVATIONS = PHASE / "observations.json"
ACTION_INDEX = PHASE / "action_index.json"
STANDARD = ROOT / "docs/full_phase_diagram_negative_standard_20260809.md"
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
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def main() -> int:
    generated = [STAGE / name for name in ("parameter-scan.run_spec.json", "r16_source_hashes.sha256", "launch-contract.json")]
    if any(path.exists() for path in generated):
        raise ValueError("R16 launch-ready 文件已存在，拒绝覆盖")
    for path in (SUMMARY, AUDIT, FAILED, CALIBRATION, OBSERVATIONS, ACTION_INDEX, STANDARD):
        if not path.is_file():
            raise FileNotFoundError(path)
    summary, audit, failed = map(load, (SUMMARY, AUDIT, FAILED))
    center = failed.get("strict_numerical_diagnostics", {}).get("center", {})
    ferro = failed.get("strict_numerical_diagnostics", {}).get("ferro_j2", {})
    if (
        summary.get("status") != "failed_calibration_final_tier"
        or summary.get("cell_id") != "nega-r15-a0050-b0500-L080"
        or summary.get("counts") != {"controller_success_total": 14, "controller_failed_total": 0,
                                     "controller_pending_total": 2, "calibration_accepted_total": 6}
        or summary.get("terminal_result", {}).get("sha256") != sha256(FAILED)
        or summary.get("ingestion_audit", {}).get("sha256") != sha256(AUDIT)
        or audit.get("status") != "pass" or audit.get("controller_unchanged") is not True
        or failed.get("status") != "failed_calibration" or failed.get("budget") != 128
        or failed.get("accepted_only_eligible") is not False
        or failed.get("child_acceptance") != {"center": False, "ferro_j2": True}
        or float(center.get("spin_gap", 0.0)) >= -1e-8
        or float(ferro.get("spin_gap", -1.0)) < -1e-8
        or summary.get("thresholds_relaxed") is not False
    ):
        raise ValueError("R15 最终失败基线不匹配")
    code_hashes = {name: sha256(ROOT / name) for name in SOURCES}
    run_spec = {
        "schema_version": 1,
        "run_id": "pentamer-negative-phase-stage-a-r16-a0050-L080-20260811",
        "scope": "alpha=-0.05, beta=0.5, L=80; convergence-protocol repair; Fig.9 excluded",
        "controller": "local_only",
        "cells": [{
            "cell_id": "nega-r16-a0050-b0500-L080",
            "params": {"alpha": -0.05, "beta": 0.5, "L": 80, "n_units": 16},
            "budget": 256,
            "stage": "A-R16",
            "retry_of": "nega-r15-a0050-b0500-L080",
            "retry_policy": "固定门槛下使用三初态、repair noise 和能量平台门；禁止事后选支",
            "controller_action_id": None,
            "calibration_only": True,
        }],
        "settings": {
            "method": "finite_dmrg_multistart_fullq",
            "boundary": "OBC",
            "hamiltonian": "five-site unit cell Heisenberg chain, J1=1, J2=alpha, J3=beta",
            "sectors": ["Sz=0", "Sz=1"],
            "maxdim_by_L": {"80": 1200},
            "nsweeps": 256,
            "cutoff": 1e-11,
            "threads": 8,
            "q_count": 401,
            "init_modes": ["center_random", "ferro_j2", "domain"],
            "noise_profile": "repair",
            "random_seed": 20260811,
            "energy_change_max": 1e-8,
            "energy_spread_max": 1e-6,
            "budget_definition": "每个独立初态均为256 sweeps",
            "acceptance": {"variance_per_site_max": 1e-8, "final_truncation_error_max": 1e-9,
                           "sector_tolerance": 1e-8, "spin_gap_min": -1e-8,
                           "energy_change_max": 1e-8, "energy_spread_max": 1e-6,
                           "q_count_min": 401},
            "offline": True,
            "execution": "direct SSH; concurrency=1; stop on first failed cell",
        },
        "provenance": {
            "negative_alpha_included": True,
            "r16_reason": "R15两条高精度分支给出冲突隙，改用预声明三初态协议判定一致低能分支",
            "r15_terminal_ingestion_summary_sha256": sha256(SUMMARY),
            "r15_terminal_ingestion_audit_sha256": sha256(AUDIT),
            "r15_failed_calibration_sha256": sha256(FAILED),
            "accepted_calibration_through_r9_sha256": sha256(CALIBRATION),
            "observations_sha256": sha256(OBSERVATIONS),
            "action_index_sha256": sha256(ACTION_INDEX),
            "r15_and_earlier_failure_provenance_preserved": True,
            "standard_sha256": sha256(STANDARD),
            "manifest_sha256": sha256(ROOT / "Manifest.toml"),
            "project_sha256": sha256(ROOT / "Project.toml"),
            "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                            text=True, check=True).stdout.strip(),
            "code_sha256": code_hashes,
            "thresholds_relaxed": False,
            "posthoc_branch_selection_forbidden": True,
            "exploratory_data_not_accepted": True,
        },
    }
    STAGE.mkdir(parents=True, exist_ok=True)
    spec = STAGE / "parameter-scan.run_spec.json"
    hashes = STAGE / "r16_source_hashes.sha256"
    write_json(spec, run_spec)
    with hashes.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("".join(f"{digest}  {name}\n" for name, digest in code_hashes.items()))
    contract = {
        "schema_version": 1, "launch_ready": True, "cell_count": 1, "calibration_cell_count": 1,
        "concurrency": 1, "stop_on_first_failure": True, "offline": True,
        "eta_minutes": {"low": 50, "high": 75}, "run_spec_sha256": sha256(spec),
        "source_hashes_sha256": sha256(hashes), "standard_sha256": sha256(STANDARD),
        "manifest_sha256": sha256(ROOT / "Manifest.toml"),
        "r15_terminal_ingestion_summary_sha256": sha256(SUMMARY),
        "r15_failed_calibration_sha256": sha256(FAILED),
        "observations_sha256": sha256(OBSERVATIONS), "action_index_sha256": sha256(ACTION_INDEX),
        "history_evidence_preserved": True, "gap_gate_enforced": True,
        "energy_plateau_enforced": True, "three_start_enforced": True,
        "energy_consistency_enforced": True, "energy_spread_max": 1e-6,
        "posthoc_branch_selection_forbidden": True, "thresholds_relaxed": False,
    }
    write_json(STAGE / "launch-contract.json", contract)
    print(json.dumps({"run_spec": str(spec), "cells": 1, "eta_minutes": [50, 75]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
