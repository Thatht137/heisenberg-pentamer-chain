#!/usr/bin/env python3
"""登记负 alpha 阶段 A 的持久执行回执。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results" / "autoresearch_v5_20260809" / "round44_phase_diagram_full_alpha"
SPEC = RUN / "stage-a-beta050-calibration" / "parameter-scan.run_spec.json"
OBSERVATIONS = RUN / "phase-diagram-v2" / "observations.json"
RECEIPT = RUN / "stage-a-beta050-calibration" / "submission-receipt.json"


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", required=True)
    args = parser.parse_args()
    run_spec = read_json(SPEC)
    records = []
    for cell in run_spec["cells"]:
        if not cell.get("controller_action_id"):
            continue
        params = cell["params"]
        records.append({
            "params": {"alpha": params["alpha"], "beta": params["beta"], "L": params["L"]},
            "status": "pending",
            "budget": cell["budget"],
            "receipt": args.receipt,
            "artifact": f"stage-a-beta050-calibration/cells/{cell['cell_id']}/manifest.json",
        })
    write_json(OBSERVATIONS, {"schema_version": 1, "records": records})
    write_json(RECEIPT, {
        "schema_version": 1,
        "status": "submitted",
        "receipt": args.receipt,
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "run_id": run_spec["run_id"],
        "cells": len(run_spec["cells"]),
        "controller_records": len(records),
        "estimated_hours": [5, 8],
    })
    print(json.dumps({"receipt": args.receipt, "pending": len(records)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
