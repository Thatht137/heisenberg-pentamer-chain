#!/usr/bin/env python3
"""生成 R19 alpha=-0.025 的 L60/L80 续跑包。"""

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
STAGE_REL = f"{RUN_REL}/stage-a-beta050-calibration-r19-remaining2"
STAGE = ROOT / STAGE_REL
TEMPLATE = RUN / "stage-a-beta050-calibration-r17-remaining3/parameter-scan.run_spec.json"
R18_SUMMARY = PHASE / "r18_success_ingestion_summary.json"
R18_AUDIT = PHASE / "r18_success_ingestion_audit.json"
CALIBRATION = PHASE / "accepted_calibration_through_r16.json"
OBSERVATIONS = PHASE / "observations.json"
ACTION_INDEX = PHASE / "action_index.json"
STANDARD = ROOT / "docs/full_phase_diagram_negative_standard_20260809.md"
LAUNCHER = "scripts/autoresearch_v5/launch_negative_phase_stage_a_r19_remaining2.sh"
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
    outputs = [STAGE / name for name in (
        "parameter-scan.run_spec.json", "r19_source_hashes.sha256",
        "launch-contract.json", "server_upload_manifest.json",
    )]
    if any(path.exists() for path in outputs):
        raise FileExistsError("R19 launch-ready 文件已存在，拒绝覆盖")
    for path in (TEMPLATE, R18_SUMMARY, R18_AUDIT, CALIBRATION, OBSERVATIONS,
                 ACTION_INDEX, STANDARD, ROOT / LAUNCHER):
        if not path.is_file():
            raise FileNotFoundError(path)
    summary, audit = load(R18_SUMMARY), load(R18_AUDIT)
    expected = {"controller_success_total": 15, "controller_failed_total": 0,
                "controller_pending_total": 1, "calibration_accepted_total": 7}
    if (
        summary.get("status") != "accepted" or summary.get("counts") != expected
        or audit.get("status") != "pass" or not all(audit.get("invariants", {}).values())
        or summary.get("observations", {}).get("sha256") != sha256(OBSERVATIONS)
        or summary.get("action_index", {}).get("sha256") != sha256(ACTION_INDEX)
        or summary.get("accepted_calibration", {}).get("sha256") != sha256(CALIBRATION)
        or summary.get("thresholds_relaxed") is not False
    ):
        raise ValueError("R18 accepted-only 基线不匹配")

    template = load(TEMPLATE)
    cells = []
    for source in template["cells"]:
        if source["params"]["L"] not in (60, 80):
            continue
        cell = json.loads(json.dumps(source))
        cell["cell_id"] = cell["cell_id"].replace("nega-r17-", "nega-r19-")
        cell["stage"] = "A-R19-remaining2"
        cell["continued_from"] = source["cell_id"]
        cells.append(cell)
    if [cell["params"]["L"] for cell in cells] != [60, 80]:
        raise ValueError("R19 cell 模板异常")

    code_hashes = {name: sha256(ROOT / name) for name in SOURCES}
    run_spec = {
        "schema_version": 1,
        "run_id": "pentamer-negative-phase-stage-a-r19-remaining2-20260812",
        "scope": "beta=0.5 Stage A remaining alpha=-0.025 L60/L80; Fig.9 excluded",
        "controller": "local_only", "cells": cells, "settings": template["settings"],
        "provenance": {
            "negative_alpha_included": True,
            "continuation_reason": "R18最终128-sweep预算接纳L40后补齐L60/L80",
            "r18_success_summary_sha256": sha256(R18_SUMMARY),
            "r18_success_audit_sha256": sha256(R18_AUDIT),
            "accepted_calibration_through_r16_sha256": sha256(CALIBRATION),
            "observations_sha256": sha256(OBSERVATIONS), "action_index_sha256": sha256(ACTION_INDEX),
            "r17_failure_provenance_preserved": True, "r16_boundary_ineligible_preserved": True,
            "boundary_acceptance_thresholds_relaxed": False,
            "standard_sha256": sha256(STANDARD), "manifest_sha256": sha256(ROOT / "Manifest.toml"),
            "project_sha256": sha256(ROOT / "Project.toml"),
            "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                             capture_output=True, text=True, check=True).stdout.strip(),
            "code_sha256": code_hashes, "gap_gate_enforced": True,
        },
    }
    STAGE.mkdir(parents=True, exist_ok=True)
    spec_path = STAGE / "parameter-scan.run_spec.json"
    hashes_path = STAGE / "r19_source_hashes.sha256"
    write_json(spec_path, run_spec)
    with hashes_path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("".join(f"{digest}  {name}\n" for name, digest in code_hashes.items()))
    contract = {
        "schema_version": 1, "launch_ready": True, "cell_count": 2,
        "controller_cell_count": 1, "calibration_cell_count": 1,
        "concurrency": 1, "stop_on_first_failure": True, "offline": True,
        "eta_hours": {"low": 0.5, "high": 1.2},
        "run_spec_sha256": sha256(spec_path), "source_hashes_sha256": sha256(hashes_path),
        "standard_sha256": sha256(STANDARD), "manifest_sha256": sha256(ROOT / "Manifest.toml"),
        "r18_success_summary_sha256": sha256(R18_SUMMARY),
        "observations_sha256": sha256(OBSERVATIONS), "action_index_sha256": sha256(ACTION_INDEX),
        "history_evidence_preserved": True, "gap_gate_enforced": True,
        "boundary_thresholds_relaxed": False,
    }
    contract_path = STAGE / "launch-contract.json"
    write_json(contract_path, contract)
    files = SOURCES + [f"{STAGE_REL}/parameter-scan.run_spec.json",
                       f"{STAGE_REL}/r19_source_hashes.sha256", f"{STAGE_REL}/launch-contract.json"]
    entries = [{"path": name, "sha256": sha256(ROOT / name), "bytes": (ROOT / name).stat().st_size}
               for name in files]
    write_json(STAGE / "server_upload_manifest.json", {
        "schema_version": 1, "target": "/home/wangjieren/code/1x5_Heisenberg_Pentamer",
        "mode": "offline_upload_only", "launch_ready": True, "negative_alpha_included": True,
        "stage": "A-R19-remaining2", "cell_count": 2, "concurrency": 1,
        "stop_on_first_failure": True, "eta_hours": {"low": 0.5, "high": 1.2},
        "remote_git_pull": False, "files": entries,
    })
    print(json.dumps({"status": "pass", "cells": 2, "eta_hours": [0.5, 1.2],
                      "upload_files": len(entries)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
