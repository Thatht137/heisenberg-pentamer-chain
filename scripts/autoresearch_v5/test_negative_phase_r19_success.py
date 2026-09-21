#!/usr/bin/env python3
"""测试 R18→R19 完整接入链且不污染正式状态。"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from ingest_negative_phase_r6 import sha256


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha"
PHASE = RUN / "phase-diagram-v2"
R18_SPEC = RUN / "stage-a-beta050-calibration-r18-a0025-L040/parameter-scan.run_spec.json"
BASE = RUN / "fetches/stage-a-beta050-calibration-r11-a0050-L040-20260811-1133"
PYTHON = ROOT / ".venv/Scripts/python.exe"
R18_SCRIPT = ROOT / "scripts/autoresearch_v5/ingest_negative_phase_r18_success.py"
R19_SCRIPT = ROOT / "scripts/autoresearch_v5/ingest_negative_phase_r19_success.py"
ACTION = "act-4503b7acb169c6a5092f"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def restore_r17_baseline(phase: Path) -> None:
    """从正式 R18 记录还原可重复的 R17 测试基线。"""
    observations = json.loads((phase / "observations.json").read_text(encoding="utf-8"))
    target = next(row for row in observations["records"] if row.get("controller_action_id") == ACTION)
    previous = target["r17_failure_provenance"]["previous_failed_observation"]
    observations["records"] = [previous if row is target else row for row in observations["records"]]
    write_json(phase / "observations.json", observations)

    actions = json.loads((phase / "action_index.json").read_text(encoding="utf-8"))
    action = next(row for row in actions["actions"] if row.get("action_id") == ACTION)
    action.pop("accepted_observation_budget", None)
    action.pop("r18_retry_handoff", None)
    action.pop("r17_failure_provenance", None)
    action.update({
        "observation_status": "failed", "accepted": False,
        "artifact": previous["artifact"], "r17_failure_handoff": True,
        "retry_recommendation": {"next_budget": 128, "thresholds_relaxed": False},
    })
    write_json(phase / "action_index.json", actions)


def fake_cell(fetch: Path, cell_id: str, length: int, budget: int) -> None:
    manifest = json.loads((BASE / "nega-r11-a0050-b0500-L040/manifest.json").read_text(encoding="utf-8"))
    manifest.update({"cell_id": cell_id, "params": {"alpha": -0.025, "beta": 0.5,
                                                       "L": length, "n_units": length // 5}})
    manifest["settings"]["budget"] = budget
    manifest["settings"]["nsweeps"] = budget
    write_json(fetch / cell_id / "manifest.json", manifest)
    validation = json.loads((BASE / "validation/nega-r11-a0050-b0500-L040.json").read_text(encoding="utf-8"))
    validation.update({"cell_id": cell_id, "run_dir": str(fetch / cell_id)})
    write_json(fetch / "validation" / f"{cell_id}.json", validation)
    receipt = json.loads((BASE / "receipts/nega-r11-a0050-b0500-L040.json").read_text(encoding="utf-8"))
    receipt.update({"cell_id": cell_id, "destination": str(fetch / cell_id)})
    write_json(fetch / "receipts" / f"{cell_id}.json", receipt)


def run_ingest(script: Path, fetch: Path, spec: Path, phase: Path) -> None:
    result = subprocess.run([str(PYTHON), str(script), "--fetch-dir", str(fetch),
                             "--run-spec", str(spec), "--phase-dir", str(phase)],
                            cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout)


def main() -> int:
    names = ("observations.json", "action_index.json", "r17_failure_ingestion_summary.json",
             "r17_failure_ingestion_audit.json", "accepted_calibration_through_r16.json")
    canonical = {name: sha256(PHASE / name) for name in names}
    with tempfile.TemporaryDirectory(prefix="r19-success-test-", dir=ROOT / "results") as name:
        temp = Path(name)
        phase = temp / "phase"
        phase.mkdir()
        for file_name in names:
            shutil.copy2(PHASE / file_name, phase / file_name)
        restore_r17_baseline(phase)

        fetch18 = temp / "fetch18"
        fake_cell(fetch18, "nega-r18-a0025-b0500-L040", 40, 128)
        write_json(fetch18 / "validation/summary.json", {
            "schema_version": 1, "counts": {"pass": 1, "fail": 0},
            "cells": [{"cell_id": "nega-r18-a0025-b0500-L040", "status": "pass"}],
        })
        run_ingest(R18_SCRIPT, fetch18, R18_SPEC, phase)

        stage19 = temp / "stage19"
        spec19 = stage19 / "parameter-scan.run_spec.json"
        write_json(spec19, {
            "schema_version": 1,
            "run_id": "pentamer-negative-phase-stage-a-r19-remaining2-20260812",
            "provenance": {
                "r18_success_summary_sha256": sha256(phase / "r18_success_ingestion_summary.json"),
                "r18_success_audit_sha256": sha256(phase / "r18_success_ingestion_audit.json"),
                "accepted_calibration_through_r16_sha256": sha256(phase / "accepted_calibration_through_r16.json"),
                "observations_sha256": sha256(phase / "observations.json"),
                "action_index_sha256": sha256(phase / "action_index.json"),
                "boundary_acceptance_thresholds_relaxed": False,
            },
        })
        write_json(stage19 / "launch-contract.json", {
            "schema_version": 1, "run_spec_sha256": sha256(spec19), "cell_count": 2,
            "concurrency": 1, "boundary_thresholds_relaxed": False,
        })
        fetch19 = temp / "fetch19"
        for length in (60, 80):
            fake_cell(fetch19, f"nega-r19-a0025-b0500-L{length:03d}", length, 64)
        write_json(fetch19 / "validation/summary.json", {
            "schema_version": 1, "counts": {"pass": 2, "fail": 0},
            "cells": [{"cell_id": f"nega-r19-a0025-b0500-L{length:03d}", "status": "pass"}
                      for length in (60, 80)],
        })
        run_ingest(R19_SCRIPT, fetch19, spec19, phase)
        summary = json.loads((phase / "r19_success_ingestion_summary.json").read_text(encoding="utf-8"))
        expected = {"controller_success_total": 16, "controller_failed_total": 0,
                    "controller_pending_total": 0, "calibration_accepted_total": 8}
        if summary.get("status") != "accepted_stage_a_complete" or summary.get("counts") != expected:
            raise ValueError("R19 合成终态计数异常")

    if any(sha256(PHASE / file_name) != digest for file_name, digest in canonical.items()):
        raise ValueError("测试污染了正式状态")
    print(json.dumps({"status": "pass", "final_counts": expected,
                      "canonical_unchanged": True}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
