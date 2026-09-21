#!/usr/bin/env python3
"""生成 Stage A R11 的 L40 单点严格重试包。"""

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
STAGE = RUN / "stage-a-beta050-calibration-r11-a0050-L040"
FETCH = RUN / "fetches/stage-a-beta050-calibration-r10-a0050-L040-20260811-1032"
R10_SPEC = RUN / "stage-a-beta050-calibration-r10-a0050-L040/parameter-scan.run_spec.json"
R10_SUMMARY = PHASE / "r10_failure_ingestion_summary.json"
R10_AUDIT = PHASE / "r10_failure_ingestion_audit.json"
R10_HANDOFF = FETCH / "failure_handoff_summary.json"
R10_VALIDATION = FETCH / "validation/summary.json"
CALIBRATION = PHASE / "accepted_calibration_through_r9.json"
OBSERVATIONS = PHASE / "observations.json"
ACTION_INDEX = PHASE / "action_index.json"
STANDARD = ROOT / "docs/full_phase_diagram_negative_standard_20260809.md"
R10_CELL = "nega-r10-a0050-b0500-L040"
R11_CELL = "nega-r11-a0050-b0500-L040"
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
    generated = [STAGE / name for name in ("parameter-scan.run_spec.json", "r11_source_hashes.sha256", "launch-contract.json")]
    if any(path.exists() for path in generated):
        raise ValueError("R11 launch-ready 文件已存在，拒绝覆盖")
    required = [R10_SPEC, R10_SUMMARY, R10_AUDIT, R10_HANDOFF, R10_VALIDATION,
                CALIBRATION, OBSERVATIONS, ACTION_INDEX, STANDARD]
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)
    summary, audit, handoff, validation = map(load, [R10_SUMMARY, R10_AUDIT, R10_HANDOFF, R10_VALIDATION])
    if (
        summary.get("status") != "blocked_by_validation_failure" or summary.get("cell_id") != R10_CELL
        or summary.get("counts") != {"controller_success_total": 12, "controller_failed_total": 1,
                                     "controller_pending_total": 3, "calibration_accepted_total": 6}
        or summary.get("failed_observation_contains_value_or_error") is not False
        or audit.get("status") != "pass_failure_only" or not all(audit.get("invariants", {}).values())
        or handoff.get("status") != "failed_validation" or handoff.get("budget") != 64
        or handoff.get("accepted_only_eligible") is not False or forbidden(handoff)
        or validation.get("counts") != {"pass": 0, "fail": 1}
        or summary.get("failure_handoff", {}).get("sha256") != sha256(R10_HANDOFF)
        or summary.get("ingestion_audit", {}).get("sha256") != sha256(R10_AUDIT)
        or summary.get("observations", {}).get("sha256") != sha256(OBSERVATIONS)
        or summary.get("action_index", {}).get("sha256") != sha256(ACTION_INDEX)
        or summary.get("accepted_calibration", {}).get("sha256") != sha256(CALIBRATION)
        or summary.get("thresholds_relaxed") is not False
    ):
        raise ValueError("R10 失败接入证据锁不匹配")
    records = load(OBSERVATIONS).get("records", [])
    target = next((row for row in records if row.get("params") == {"alpha": -0.05, "beta": 0.5, "L": 40}), None)
    r6 = next((row for row in records if row.get("params") == {"alpha": -0.1, "beta": 0.5, "L": 40}), None)
    r8 = next((row for row in records if row.get("params") == {"alpha": -0.1, "beta": 0.5, "L": 60}), None)
    if (
        not target or target.get("status") != "failed" or target.get("budget") != 64
        or target.get("controller_action_id") != ACTION or forbidden(target)
        or target.get("r10_provenance", {}).get("r9_failure_provenance_preserved") is not True
        or not r6 or r6.get("error") != R6_HALF
        or not r8 or r8.get("r7_failure_provenance", {}).get("preserved") is not True
    ):
        raise ValueError("R10 failed observation 或历史 provenance 不匹配")
    action = next((row for row in load(ACTION_INDEX).get("actions", []) if row.get("action_id") == ACTION), None)
    if (
        not action or action.get("observation_status") != "failed" or action.get("accepted") is not False
        or action.get("retry_recommendation", {}).get("next_budget") != 128
    ):
        raise ValueError("R10 action_index 未放行 128 sweeps 重试")
    r10_spec = load(R10_SPEC)
    if (
        len(r10_spec.get("cells", [])) != 1 or r10_spec["cells"][0].get("cell_id") != R10_CELL
        or r10_spec["cells"][0].get("budget") != 64
    ):
        raise ValueError("R10 run spec 身份不匹配")

    code_hashes = {name: sha256(ROOT / name) for name in SOURCE_FILES}
    run_spec = {
        "schema_version": 1, "run_id": "pentamer-negative-phase-stage-a-r11-a0050-L040-20260811",
        "scope": "alpha=-0.05, beta=0.5, L=40; one-cell strict retry; Fig.9 excluded",
        "controller": "local_only",
        "cells": [{
            "cell_id": R11_CELL, "params": {"alpha": -0.05, "beta": 0.5, "L": 40, "n_units": 8},
            "budget": 128, "stage": "A-R11", "retry_of": R10_CELL,
            "retry_policy": "仅R10失败单元64→128 sweeps；方差、gap及其余门槛不变",
            "controller_action_id": ACTION, "calibration_only": False,
        }],
        "settings": {
            "method": "finite_dmrg_multistart_fullq", "boundary": "OBC",
            "hamiltonian": "five-site unit cell Heisenberg chain, J1=1, J2=alpha, J3=beta",
            "sectors": ["Sz=0", "Sz=1"], "maxdim_by_L": {"40": 800}, "nsweeps": 128,
            "cutoff": 1e-11, "threads": 8, "q_count": 401, "init_modes": ["center", "ferro_j2"],
            "budget_definition": "每个独立初态均为128 sweeps",
            "acceptance": {"variance_per_site_max": 1e-8, "final_truncation_error_max": 1e-9,
                           "sector_tolerance": 1e-8, "spin_gap_min": -1e-8,
                           "nonnegative_gap_required": True, "q_count_min": 401},
            "offline": True, "execution": "direct SSH; concurrency=1; stop on first failed cell",
        },
        "provenance": {
            "negative_alpha_included": True,
            "r11_reason": "R10 center初态Sz0方差和gap超门，按64→128单点最终数值重试",
            "r10_run_spec_sha256": sha256(R10_SPEC),
            "r10_failure_ingestion_summary_sha256": sha256(R10_SUMMARY),
            "r10_failure_ingestion_audit_sha256": sha256(R10_AUDIT),
            "r10_failure_handoff_sha256": sha256(R10_HANDOFF),
            "r10_validation_summary_sha256": sha256(R10_VALIDATION),
            "accepted_calibration_through_r9_sha256": sha256(CALIBRATION),
            "observations_sha256": sha256(OBSERVATIONS), "action_index_sha256": sha256(ACTION_INDEX),
            "r9_failure_provenance_preserved": True,
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
    spec_path, hashes_path = STAGE / "parameter-scan.run_spec.json", STAGE / "r11_source_hashes.sha256"
    write_json(spec_path, run_spec)
    write_lf(hashes_path, "".join(f"{digest}  {name}\n" for name, digest in code_hashes.items()))
    contract = {
        "schema_version": 1, "launch_ready": True, "cell_count": 1, "concurrency": 1, "offline": True,
        "eta_minutes": {"low": 20, "high": 45}, "run_spec_sha256": sha256(spec_path),
        "source_hashes_sha256": sha256(hashes_path), "standard_sha256": sha256(STANDARD),
        "manifest_sha256": sha256(ROOT / "Manifest.toml"),
        "r10_failure_ingestion_summary_sha256": sha256(R10_SUMMARY),
        "r10_failure_ingestion_audit_sha256": sha256(R10_AUDIT),
        "r10_failure_handoff_sha256": sha256(R10_HANDOFF),
        "r10_validation_summary_sha256": sha256(R10_VALIDATION),
        "accepted_calibration_through_r9_sha256": sha256(CALIBRATION),
        "observations_sha256": sha256(OBSERVATIONS), "action_index_sha256": sha256(ACTION_INDEX),
        "r6_r7_r9_evidence_preserved": True, "gap_gate_enforced": True,
        "nonnegative_gap_min": -1e-8, "thresholds_relaxed": False,
    }
    write_json(STAGE / "launch-contract.json", contract)
    print(json.dumps({"run_spec": str(spec_path), "cells": 1, "eta_minutes": [20, 45]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
