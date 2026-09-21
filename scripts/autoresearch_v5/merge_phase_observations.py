#!/usr/bin/env python3
"""合并首段与 L=80 observations，不改写历史 controller 状态。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "results" / "autoresearch_v5_20260731"
INITIAL = BASE / "round17_phase_diagram_positive" / "phase-diagram" / "observations.json"
PROMOTED = BASE / "round18_final_phase_diagram_positive_L80" / "phase-diagram" / "observations.json"
OUTPUT_DIR = BASE / "round18_final_phase_diagram_positive_L80" / "phase-diagram"


def main() -> None:
    initial = json.loads(INITIAL.read_text(encoding="utf-8"))
    promoted = json.loads(PROMOTED.read_text(encoding="utf-8"))
    records = list(initial["records"]) + list(promoted["records"])
    keys = [(r["params"].get("beta"), r["params"]["alpha"], r["params"]["L"]) for r in records]
    if len(keys) != len(set(keys)):
        raise SystemExit("observations 存在重复 (beta, alpha, L)")
    output = {"schema_version": 1, "records": records}
    target = OUTPUT_DIR / "observations_merged.json"
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(target), "records": len(records)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
