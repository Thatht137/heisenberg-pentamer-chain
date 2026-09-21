#!/usr/bin/env python3
"""生成 Stage A R17 剩余三单元续跑批次。"""

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
STAGE_REL = f"{RUN_REL}/stage-a-beta050-calibration-r17-remaining3"
STAGE = ROOT / STAGE_REL
TEMPLATE = RUN / "stage-a-beta050-calibration-r14-remaining4/parameter-scan.run_spec.json"
SUMMARY = PHASE / "r16_practical_ingestion_summary.json"
AUDIT = PHASE / "r16_practical_ingestion_audit.json"
CALIBRATION = PHASE / "accepted_calibration_through_r16.json"
OBSERVATIONS = PHASE / "observations.json"
ACTION_INDEX = PHASE / "action_index.json"
ADJUDICATION = RUN / "fetches/stage-a-beta050-calibration-r16-a0050-L080-20260811-2140/practical_adjudication.json"
STRICT_VALIDATION = RUN / "fetches/stage-a-beta050-calibration-r16-a0050-L080-20260811-2140/validation.json"
STANDARD = ROOT / "docs/full_phase_diagram_negative_standard_20260809.md"
LAUNCHER = "scripts/autoresearch_v5/launch_negative_phase_stage_a_r17_remaining3.sh"
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
        "parameter-scan.run_spec.json", "r17_source_hashes.sha256",
        "launch-contract.json", "server_upload_manifest.json",
    )]
    if any(path.exists() for path in outputs):
        raise ValueError("R17 launch-ready 文件已存在，拒绝覆盖")
    for path in (TEMPLATE, SUMMARY, AUDIT, CALIBRATION, OBSERVATIONS,
                 ACTION_INDEX, ADJUDICATION, STRICT_VALIDATION, STANDARD, ROOT / LAUNCHER):
        if not path.is_file():
            raise FileNotFoundError(path)

    summary, audit, adjudication, strict = map(load, [SUMMARY, AUDIT, ADJUDICATION, STRICT_VALIDATION])
    expected_counts = {"controller_success_total": 14, "controller_failed_total": 0,
                       "controller_pending_total": 2, "calibration_accepted_total": 7}
    if (
        summary.get("status") != "accepted_practical_calibration"
        or summary.get("counts") != expected_counts
        or summary.get("boundary_eligible") is not False
        or summary.get("strict_failure_preserved") is not True
        or audit.get("status") != "pass_practical_calibration_only"
        or audit.get("controller_unchanged") is not True
        or adjudication.get("status") != "pass"
        or adjudication.get("boundary_eligible") is not False
        or strict.get("status") != "fail"
        or sha256(CALIBRATION) != summary["accepted_calibration"]["sha256"]
        or sha256(AUDIT) != summary["ingestion_audit"]["sha256"]
        or sha256(OBSERVATIONS) != summary["observations"]["sha256"]
        or sha256(ACTION_INDEX) != summary["action_index"]["sha256"]
    ):
        raise ValueError("R16 practical accepted-only 基线不匹配")

    observations = load(OBSERVATIONS).get("records", [])
    counts = {name: sum(row.get("status") == name for row in observations)
              for name in ("success", "failed", "pending")}
    if counts != {"success": 14, "failed": 0, "pending": 2}:
        raise ValueError(f"controller 计数异常: {counts}")

    template = load(TEMPLATE)
    cells = []
    for source in template["cells"]:
        if source["params"]["alpha"] != -0.025:
            continue
        cell = json.loads(json.dumps(source))
        cell["cell_id"] = cell["cell_id"].replace("nega-r14-", "nega-r17-")
        cell["stage"] = "A-R17-remaining3"
        cell["continued_from"] = source["cell_id"]
        cells.append(cell)
    if len(cells) != 3 or [cell["params"]["L"] for cell in cells] != [40, 60, 80]:
        raise ValueError("R17 cell 模板异常")

    code_hashes = {name: sha256(ROOT / name) for name in SOURCES}
    run_spec = {
        "schema_version": 1,
        "run_id": "pentamer-negative-phase-stage-a-r17-remaining3-20260811",
        "scope": "beta=0.5 Stage A remaining alpha=-0.025 L40/L60/L80; Fig.9 excluded",
        "controller": "local_only",
        "cells": cells,
        "settings": template["settings"],
        "provenance": {
            "negative_alpha_included": True,
            "continuation_reason": "R16实用校准接纳后补齐Stage A最后三个alpha=-0.025单元",
            "r16_practical_summary_sha256": sha256(SUMMARY),
            "r16_practical_audit_sha256": sha256(AUDIT),
            "r16_practical_adjudication_sha256": sha256(ADJUDICATION),
            "r16_strict_validation_sha256": sha256(STRICT_VALIDATION),
            "accepted_calibration_through_r16_sha256": sha256(CALIBRATION),
            "observations_sha256": sha256(OBSERVATIONS),
            "action_index_sha256": sha256(ACTION_INDEX),
            "r16_boundary_eligible": False,
            "r16_strict_failure_preserved": True,
            "r16_practical_energy_change_max": 1e-7,
            "boundary_acceptance_thresholds_relaxed": False,
            "history_evidence_preserved": True,
            "standard_sha256": sha256(STANDARD),
            "manifest_sha256": sha256(ROOT / "Manifest.toml"),
            "project_sha256": sha256(ROOT / "Project.toml"),
            "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                             capture_output=True, text=True, check=True).stdout.strip(),
            "code_sha256": code_hashes,
            "gap_gate_enforced": True,
            "exploratory_data_not_accepted": True,
        },
    }
    STAGE.mkdir(parents=True, exist_ok=True)
    spec_path = STAGE / "parameter-scan.run_spec.json"
    hashes_path = STAGE / "r17_source_hashes.sha256"
    write_json(spec_path, run_spec)
    with hashes_path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("".join(f"{digest}  {name}\n" for name, digest in code_hashes.items()))
    contract = {
        "schema_version": 1, "launch_ready": True, "cell_count": 3,
        "controller_cell_count": 2, "calibration_cell_count": 1,
        "concurrency": 1, "stop_on_first_failure": True, "offline": True,
        "eta_hours": {"low": 0.8, "high": 1.8},
        "run_spec_sha256": sha256(spec_path), "source_hashes_sha256": sha256(hashes_path),
        "standard_sha256": sha256(STANDARD), "manifest_sha256": sha256(ROOT / "Manifest.toml"),
        "r16_practical_summary_sha256": sha256(SUMMARY),
        "accepted_calibration_sha256": sha256(CALIBRATION),
        "observations_sha256": sha256(OBSERVATIONS), "action_index_sha256": sha256(ACTION_INDEX),
        "history_evidence_preserved": True, "gap_gate_enforced": True,
        "boundary_thresholds_relaxed": False,
    }
    contract_path = STAGE / "launch-contract.json"
    write_json(contract_path, contract)

    files = SOURCES + [f"{STAGE_REL}/parameter-scan.run_spec.json",
                       f"{STAGE_REL}/r17_source_hashes.sha256", f"{STAGE_REL}/launch-contract.json"]
    entries = [{"path": name, "sha256": sha256(ROOT / name), "bytes": (ROOT / name).stat().st_size}
               for name in files]
    upload = {
        "schema_version": 1, "target": "/home/wangjieren/code/1x5_Heisenberg_Pentamer",
        "mode": "offline_upload_only", "launch_ready": True, "negative_alpha_included": True,
        "stage": "A-R17-remaining3", "cell_count": 3, "controller_cell_count": 2,
        "calibration_cell_count": 1, "concurrency": 1, "stop_on_first_failure": True,
        "eta_hours": {"low": 0.8, "high": 1.8}, "remote_git_pull": False, "files": entries,
    }
    write_json(STAGE / "server_upload_manifest.json", upload)
    print(json.dumps({"status": "pass", "cells": 3, "eta_hours": [0.8, 1.8],
                      "upload_files": len(entries)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
