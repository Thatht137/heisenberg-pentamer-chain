"""无覆盖组装最终六-cell handoff 输入目录。"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULTS = (ROOT / "results").resolve()


FIXED_SOURCES = {
    "fullq-uniform-dt025": ROOT / "results/autoresearch_v5_20260807/minimal_fullq_fetch_20260807_1630/fullq-uniform-dt025",
    "fullq-uniform-dt0125": ROOT / "results/autoresearch_v5_20260807/minimal_fullq_fetch_20260807_2030/fullq-uniform-dt0125",
    "fullq-weak-eta020-dt025": ROOT / "results/autoresearch_v5_20260807/minimal_fullq_fetch_eta020_20260808_0045/fullq-weak-eta020-dt025",
    "fullq-weak-eta020-dt0125": ROOT / "results/autoresearch_v5_20260807/minimal_fullq_fetch_eta020_20260808_1145/fullq-weak-eta020-dt0125",
}


def under_results(path: Path) -> Path:
    resolved = path.resolve()
    resolved.relative_to(RESULTS)
    return resolved


def resolve_sources() -> dict[str, Path]:
    """固定旧目录加上最新 agreement 回传目录。"""
    sources = dict(FIXED_SOURCES)
    root = ROOT / "results/autoresearch_v5_20260807"
    for cell_id in ("fullq-agreement-eta020-dt025", "fullq-agreement-eta020-dt0125"):
        candidates = sorted(root.glob(f"minimal_fullq_fetch_eta020_*/{cell_id}"))
        if not candidates:
            sources[cell_id] = root / f"missing/{cell_id}"
        else:
            sources[cell_id] = candidates[-1]
    return sources


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default="results/autoresearch_v5_20260807/minimal_fullq_final_campaign_eta020",
    )
    args = parser.parse_args()
    output = under_results(ROOT / args.output_dir)
    if output.exists():
        raise SystemExit(f"拒绝覆盖已有 staging 目录: {output}")
    sources = resolve_sources()
    missing = [name for name, source in sources.items() if not source.is_dir()]
    if missing:
        raise SystemExit("尚缺少 cell: " + ", ".join(missing))
    output.mkdir(parents=True)
    records = []
    for name, source in sources.items():
        target = output / name
        shutil.copytree(source, target, copy_function=shutil.copy2)
        records.append({"cell_id": name, "source": str(source), "staged": str(target)})
    (output / "staging_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "scope": "0<=alpha,beta<=1；排除负 alpha 与 Fig.9",
                "non_overwriting": True,
                "cells": records,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "pass", "output": str(output), "cells": len(records)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
