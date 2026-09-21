#!/usr/bin/env python3
"""合并旧三条 beta 截面与扩展网格结果。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "results" / "autoresearch_v5_20260731" / "round18_final_phase_diagram_positive_L80"
RUN = ROOT / "results" / "autoresearch_v5_20260802" / "round19_phase_diagram_positive_mesh"
OLD = BASE / "phase-diagram" / "observations_merged.json"
NEW = RUN / "phase-diagram" / "observations.json"
OUT = RUN / "phase-diagram" / "observations_merged.json"


def load(path: Path) -> list[dict[str, object]]:
    return json.loads(path.read_text(encoding="utf-8"))["records"]


def main() -> None:
    old = load(OLD)
    new = load(NEW)
    records = old + new
    keys = [(r["params"]["beta"], r["params"]["alpha"], r["params"]["L"]) for r in records]
    if len(keys) != len(set(keys)):
        raise SystemExit("observations 存在重复 (beta, alpha, L)")
    if any(r.get("status") != "success" for r in records):
        raise SystemExit("observations 含非 success 记录")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"schema_version": 1, "records": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), "old": len(old), "new": len(new), "total": len(records)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
