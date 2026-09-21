#!/usr/bin/env python3
"""合并 L=80 成功 cell，并保留历史失败目录。"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "results" / "autoresearch_v5_20260731"
SOURCE_SPEC = BASE / "round18_phase_diagram_positive_L80" / "parameter-scan.run_spec.json"
DEST = BASE / "round18_final_phase_diagram_positive_L80"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def checksums_valid(cell: Path) -> bool:
    checksum = cell / "checksums.sha256"
    if not checksum.is_file():
        return False
    for line in checksum.read_text(encoding="utf-8").splitlines():
        expected, name = line.split("  ", 1)
        target = cell / name
        if not target.is_file() or sha256(target) != expected:
            return False
    return True


def manifest_ok(cell: Path) -> bool:
    manifest = json.loads((cell / "manifest.json").read_text(encoding="utf-8"))
    return manifest.get("status") == "success" and manifest.get("accepted") is True


def main() -> None:
    if DEST.exists():
        raise SystemExit(f"拒绝覆盖已有 final run: {DEST}")
    sources = []
    old_cells = BASE / "round18_phase_diagram_positive_L80" / "cells"
    for number in range(1, 12):
        cell_id = f"l80-cell-{number:04d}"
        sources.append((old_cells / cell_id, cell_id))
    sources.extend([
        (BASE / "round18b_phase_diagram_positive_L80_recovery" / "cells" / "l80-cell-0012-r64", "l80-cell-0012-r64"),
        (BASE / "round18b_phase_diagram_positive_L80_recovery" / "cells" / "l80-cell-0013", "l80-cell-0013"),
        (BASE / "round18b_phase_diagram_positive_L80_recovery" / "cells" / "l80-cell-0014", "l80-cell-0014"),
        (BASE / "round18d_phase_diagram_positive_L80_retry0015_final" / "cells" / "l80-cell-0015-final", "l80-cell-0015-final"),
    ])
    for source, _ in sources:
        if not source.is_dir() or not checksums_valid(source) or not manifest_ok(source):
            raise SystemExit(f"cell 未通过本地合并校验: {source}")

    spec = json.loads(SOURCE_SPEC.read_text(encoding="utf-8"))
    spec["run_id"] = "pentamer-positive-phase-diagram-20260802-L80-final"
    spec["scope"] = "alpha>=0,beta>=0; L=80 final promotion; Fig.9 excluded"
    spec["final_sources"] = [str(source.relative_to(ROOT)).replace("\\", "/") for source, _ in sources]
    id_map = {"l80-cell-0012": "l80-cell-0012-r64", "l80-cell-0015": "l80-cell-0015-final"}
    for cell in spec["cells"]:
        cell["cell_id"] = id_map.get(cell["cell_id"], cell["cell_id"])
        if cell["cell_id"] in {"l80-cell-0012-r64", "l80-cell-0015-final"}:
            cell["budget"] = 64
    spec["provenance"]["recovery_code_revision"] = "final-three-sweep-truncation-gate-20260802"

    (DEST / "cells").mkdir(parents=True)
    for source, cell_id in sources:
        shutil.copytree(source, DEST / "cells" / cell_id)
    (DEST / "parameter-scan.run_spec.json").write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (DEST / "run.json").write_text(
        json.dumps({
            "schema_version": 1,
            "run_id": spec["run_id"],
            "cell_count": len(sources),
            "accepted": True,
            "negative_alpha_excluded": True,
            "source_runs": ["round18_phase_diagram_positive", "round18b_phase_diagram_positive_L80_recovery", "round18d_phase_diagram_positive_L80_retry0015_final"],
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"run": str(DEST), "cells": len(sources)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
