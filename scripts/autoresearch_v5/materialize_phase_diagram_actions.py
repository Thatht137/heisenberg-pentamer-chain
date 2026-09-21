#!/usr/bin/env python3
"""把 phase controller 报告中的 action 固化为可审计文件。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results" / "autoresearch_v5_20260731" / "round17_phase_diagram_positive"
PHASE = RUN / "phase-diagram"


def action_id(spec: dict[str, object]) -> str:
    encoded = json.dumps(spec, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return "act-" + hashlib.sha256(encoded).hexdigest()[:20]


def main() -> None:
    report = json.loads((PHASE / "report.json").read_text(encoding="utf-8"))
    if report.get("status") != "ACTION_REQUIRED":
        raise SystemExit(f"当前报告不是 ACTION_REQUIRED: {report.get('status')}")
    action_dir = PHASE / "action_specs"
    action_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for item in report["actions"]:
        spec = item["spec"]
        identifier = action_id(spec)
        path = action_dir / f"{identifier}.json"
        path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        rows.append({
            "action_id": identifier,
            "spec_path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "reason": item["reason"],
            "params": spec["params"],
            "budget": spec["budget"],
            "state": "PLANNED_INPUT_ONLY",
        })
    index = {
        "schema_version": 1,
        "report_checked_at": report["checked_at"],
        "count": len(rows),
        "server_submission": "blocked_until_user_confirms_first_stage",
        "actions": rows,
    }
    (PHASE / "action_index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"count": len(rows), "directory": str(action_dir)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
