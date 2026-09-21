#!/usr/bin/env python3
"""生成 R18 alpha=-0.025、L40 的 128 sweeps 最终重试包。"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RUN_REL = "results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha"
RUN = ROOT / RUN_REL
PHASE = RUN / "phase-diagram-v2"
STAGE_REL = f"{RUN_REL}/stage-a-beta050-calibration-r18-a0025-L040"
STAGE = ROOT / STAGE_REL
FETCH = RUN / "fetches/stage-a-beta050-calibration-r17-remaining3-20260812-0630"
R17_SPEC = RUN / "stage-a-beta050-calibration-r17-remaining3/parameter-scan.run_spec.json"
R17_SUMMARY = PHASE / "r17_failure_ingestion_summary.json"
R17_AUDIT = PHASE / "r17_failure_ingestion_audit.json"
R17_VALIDATION = FETCH / "validation/summary.json"
R17_RECEIPT = FETCH / "receipts/nega-r17-a0025-b0500-L040.json"
CALIBRATION = PHASE / "accepted_calibration_through_r16.json"
OBSERVATIONS = PHASE / "observations.json"
ACTION_INDEX = PHASE / "action_index.json"
STANDARD = ROOT / "docs/full_phase_diagram_negative_standard_20260809.md"
LAUNCHER = "scripts/autoresearch_v5/launch_negative_phase_stage_a_r18_a0025_L040.sh"
CELL = "nega-r18-a0025-b0500-L040"
ACTION = "act-4503b7acb169c6a5092f"
SOURCES = [
    "Project.toml", "Manifest.toml", "docs/full_phase_diagram_negative_standard_20260809.md",
    "src/PentamerChain.jl", "src/hamiltonian.jl", "src/order_parameters.jl",
    "scripts/autoresearch_v5/progress.py", "scripts/autoresearch_v5/negative_static_cell.jl",
    "scripts/autoresearch_v5/run_negative_static_cell.py",
    "scripts/autoresearch_v5/run_negative_phase_structure_cell.py",
    "scripts/autoresearch_v5/run_negative_phase_structure_batch.py",
    "scripts/autoresearch_v5/validate_negative_phase_run.py", LAUNCHER,
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
        Path(name).unlink(missing_ok=True)
        raise


def main() -> int:
    outputs = [STAGE / name for name in ("parameter-scan.run_spec.json", "r18_source_hashes.sha256",
                                         "launch-contract.json", "server_upload_manifest.json")]
    if any(path.exists() for path in outputs):
        raise FileExistsError("R18 launch-ready 文件已存在，拒绝覆盖")
    required = (R17_SPEC, R17_SUMMARY, R17_AUDIT, R17_VALIDATION, R17_RECEIPT,
                CALIBRATION, OBSERVATIONS, ACTION_INDEX, STANDARD, ROOT / LAUNCHER)
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)
    summary, audit, validation = load(R17_SUMMARY), load(R17_AUDIT), load(R17_VALIDATION)
    if (
        summary.get("status") != "failed_first_cell_ingested"
        or summary.get("failed_cell") != "nega-r17-a0025-b0500-L040"
        or summary.get("counts") != {"controller_success_total": 14, "controller_failed_total": 1,
                                     "controller_pending_total": 1, "calibration_accepted_total": 7}
        or summary.get("retry") != {"cell": "nega-r17-a0025-b0500-L040", "budget": 128,
                                    "last_budget": True, "thresholds_relaxed": False}
        or audit.get("status") != "pass_failure" or not all(audit.get("invariants", {}).values())
        or validation.get("counts") != {"pass": 0, "fail": 1}
        or summary.get("ingestion_audit", {}).get("sha256") != sha256(R17_AUDIT)
        or summary.get("observations", {}).get("sha256") != sha256(OBSERVATIONS)
        or summary.get("action_index", {}).get("sha256") != sha256(ACTION_INDEX)
        or summary.get("accepted_calibration", {}).get("sha256") != sha256(CALIBRATION)
        or summary.get("boundary_thresholds_relaxed") is not False
    ):
        raise ValueError("R17 失败接入证据锁不匹配")
    records = load(OBSERVATIONS).get("records", [])
    target = next((row for row in records if row.get("params") == {"alpha": -0.025, "beta": 0.5, "L": 40}), None)
    if (
        not target or target.get("status") != "failed" or target.get("budget") != 64
        or target.get("controller_action_id") != ACTION
        or target.get("failure_evidence", {}).get("thresholds_relaxed") is not False
    ):
        raise ValueError("R17 failed observation 不匹配")
    action = next((row for row in load(ACTION_INDEX).get("actions", []) if row.get("action_id") == ACTION), None)
    if (
        not action or action.get("observation_status") != "failed" or action.get("accepted") is not False
        or action.get("retry_recommendation") != {"next_budget": 128, "thresholds_relaxed": False}
    ):
        raise ValueError("R17 action_index 未放行 128 sweeps")

    code_hashes = {name: sha256(ROOT / name) for name in SOURCES}
    run_spec = {
        "schema_version": 1, "run_id": "pentamer-negative-phase-stage-a-r18-a0025-L040-20260812",
        "scope": "alpha=-0.025,beta=0.5,L40; last-budget strict retry; Fig.9 excluded",
        "controller": "local_only",
        "cells": [{
            "cell_id": CELL, "params": {"alpha": -0.025, "beta": 0.5, "L": 40, "n_units": 8},
            "budget": 128, "stage": "A-R18", "retry_of": "nega-r17-a0025-b0500-L040",
            "retry_policy": "仅R17失败单元64→128 sweeps；所有数值门不变",
            "controller_action_id": ACTION, "calibration_only": False,
        }],
        "settings": {
            "method": "finite_dmrg_multistart_fullq", "boundary": "OBC",
            "hamiltonian": "five-site unit cell Heisenberg chain, J1=1, J2=alpha, J3=beta",
            "sectors": ["Sz=0", "Sz=1"], "maxdim_by_L": {"40": 800}, "nsweeps": 128,
            "cutoff": 1e-11, "threads": 8, "q_count": 401, "init_modes": ["center", "ferro_j2"],
            "acceptance": {"variance_per_site_max": 1e-8, "final_truncation_error_max": 1e-9,
                           "sector_tolerance": 1e-8, "spin_gap_min": -1e-8,
                           "nonnegative_gap_required": True, "q_count_min": 401},
            "offline": True, "execution": "direct SSH; concurrency=1; stop on first failed cell",
        },
        "provenance": {
            "negative_alpha_included": True,
            "r18_reason": "R17 双初态仅 Sz1 variance=1.27080e-8 超门，执行64→128最后一级重试",
            "r17_run_spec_sha256": sha256(R17_SPEC),
            "r17_failure_ingestion_summary_sha256": sha256(R17_SUMMARY),
            "r17_failure_ingestion_audit_sha256": sha256(R17_AUDIT),
            "r17_validation_summary_sha256": sha256(R17_VALIDATION),
            "r17_receipt_sha256": sha256(R17_RECEIPT),
            "accepted_calibration_through_r16_sha256": sha256(CALIBRATION),
            "observations_sha256": sha256(OBSERVATIONS), "action_index_sha256": sha256(ACTION_INDEX),
            "r16_strict_failure_preserved": True, "r16_boundary_ineligible_preserved": True,
            "standard_sha256": sha256(STANDARD), "manifest_sha256": sha256(ROOT / "Manifest.toml"),
            "project_sha256": sha256(ROOT / "Project.toml"),
            "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                             capture_output=True, text=True, check=True).stdout.strip(),
            "code_sha256": code_hashes, "gap_gate_enforced": True,
            "thresholds_relaxed": False, "last_budget": True,
        },
    }
    STAGE.mkdir(parents=True, exist_ok=True)
    spec_path, hashes_path = STAGE / "parameter-scan.run_spec.json", STAGE / "r18_source_hashes.sha256"
    write_json(spec_path, run_spec)
    with hashes_path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("".join(f"{digest}  {name}\n" for name, digest in code_hashes.items()))
    contract = {
        "schema_version": 1, "launch_ready": True, "cell_count": 1, "concurrency": 1,
        "offline": True, "last_budget": True, "eta_minutes": {"low": 15, "high": 35},
        "run_spec_sha256": sha256(spec_path), "source_hashes_sha256": sha256(hashes_path),
        "standard_sha256": sha256(STANDARD), "manifest_sha256": sha256(ROOT / "Manifest.toml"),
        "r17_failure_summary_sha256": sha256(R17_SUMMARY),
        "observations_sha256": sha256(OBSERVATIONS), "action_index_sha256": sha256(ACTION_INDEX),
        "r16_evidence_preserved": True, "gap_gate_enforced": True, "thresholds_relaxed": False,
    }
    contract_path = STAGE / "launch-contract.json"
    write_json(contract_path, contract)
    files = SOURCES + [f"{STAGE_REL}/parameter-scan.run_spec.json",
                       f"{STAGE_REL}/r18_source_hashes.sha256", f"{STAGE_REL}/launch-contract.json"]
    entries = [{"path": name, "sha256": sha256(ROOT / name), "bytes": (ROOT / name).stat().st_size}
               for name in files]
    write_json(STAGE / "server_upload_manifest.json", {
        "schema_version": 1, "target": "/home/wangjieren/code/1x5_Heisenberg_Pentamer",
        "mode": "offline_upload_only", "launch_ready": True, "last_budget": True,
        "negative_alpha_included": True, "cell_count": 1, "concurrency": 1,
        "eta_minutes": {"low": 15, "high": 35}, "remote_git_pull": False, "files": entries,
    })
    print(json.dumps({"status": "pass", "cells": 1, "eta_minutes": [15, 35],
                      "upload_files": len(entries)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
