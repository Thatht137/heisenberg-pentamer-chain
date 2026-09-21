#!/usr/bin/env python3
"""测试 R18 成功接入不会污染正式状态。"""

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
SPEC = RUN / "stage-a-beta050-calibration-r18-a0025-L040/parameter-scan.run_spec.json"
BASE = RUN / "fetches/stage-a-beta050-calibration-r11-a0050-L040-20260811-1133"
SCRIPT = ROOT / "scripts/autoresearch_v5/ingest_negative_phase_r18_success.py"
CELL = "nega-r18-a0025-b0500-L040"
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


def main() -> int:
    canonical = {name: sha256(PHASE / name) for name in (
        "observations.json", "action_index.json", "r17_failure_ingestion_summary.json",
        "r17_failure_ingestion_audit.json", "accepted_calibration_through_r16.json",
    )}
    with tempfile.TemporaryDirectory(prefix="r18-success-test-", dir=ROOT / "results") as name:
        temp = Path(name)
        phase = temp / "phase"
        fetch = temp / "fetch"
        phase.mkdir()
        for file_name in canonical:
            shutil.copy2(PHASE / file_name, phase / file_name)
        restore_r17_baseline(phase)

        validation = json.loads((BASE / "validation/nega-r11-a0050-b0500-L040.json").read_text(encoding="utf-8"))
        validation.update({"cell_id": CELL, "run_dir": str(fetch / CELL), "run_spec": str(SPEC)})
        write_json(fetch / "validation" / f"{CELL}.json", validation)
        write_json(fetch / "validation/summary.json", {
            "schema_version": 1, "counts": {"pass": 1, "fail": 0},
            "cells": [{"cell_id": CELL, "status": "pass"}],
        })

        receipt = json.loads((BASE / "receipts/nega-r11-a0050-b0500-L040.json").read_text(encoding="utf-8"))
        receipt.update({"cell_id": CELL, "destination": str(fetch / CELL)})
        write_json(fetch / "receipts" / f"{CELL}.json", receipt)

        manifest = json.loads((BASE / "nega-r11-a0050-b0500-L040/manifest.json").read_text(encoding="utf-8"))
        manifest.update({"cell_id": CELL, "params": {"alpha": -0.025, "beta": 0.5, "L": 40, "n_units": 8}})
        write_json(fetch / CELL / "manifest.json", manifest)

        result = subprocess.run([
            str(ROOT / ".venv/Scripts/python.exe"), str(SCRIPT),
            "--fetch-dir", str(fetch), "--run-spec", str(SPEC), "--phase-dir", str(phase),
        ], cwd=ROOT, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr or result.stdout)
        summary = json.loads((phase / "r18_success_ingestion_summary.json").read_text(encoding="utf-8"))
        if summary.get("status") != "accepted" or summary.get("counts") != {
            "controller_success_total": 15, "controller_failed_total": 0,
            "controller_pending_total": 1, "calibration_accepted_total": 7,
        }:
            raise ValueError("R18 合成成功接入结果异常")

    if any(sha256(PHASE / file_name) != digest for file_name, digest in canonical.items()):
        raise ValueError("测试污染了正式状态")
    print(json.dumps({"status": "pass", "canonical_unchanged": True}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
