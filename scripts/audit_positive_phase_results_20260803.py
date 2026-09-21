"""复核正区相图的记录、尺寸差和高误差 cell。"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "results/autoresearch_v5_20260802/round19_phase_diagram_positive_mesh"
PHASE_DIR = RUN / "phase-diagram"
OBS = PHASE_DIR / "observations_merged.json"
GUARD = ROOT / "temp/positive_phase_guard_recheck_20260803.json"
MESH_CSV = PHASE_DIR / "phase-size-differences.csv"
OUT = ROOT / "results/research_progress/positive_phase_audit_20260803.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def nested(record: dict, *keys: str):
    value = record
    for key in keys:
        value = value.get(key, {}) if isinstance(value, dict) else {}
    return value


def main() -> None:
    observations = json.loads(OBS.read_text(encoding="utf-8"))
    guard = json.loads(GUARD.read_text(encoding="utf-8"))
    merged = observations["records"]
    successful = [row for row in merged if row.get("status") == "success"]
    unique_keys = {
        (row["params"].get("beta"), row["params"].get("alpha"), row["params"].get("L"))
        for row in successful
    }

    with MESH_CSV.open(encoding="utf-8", newline="") as handle:
        mesh = list(csv.DictReader(handle))
    internal_mesh = [row for row in mesh if float(row["alpha"]) > 0]

    cells = []
    for manifest in sorted((RUN / "cells").glob("*/manifest.json")):
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        error = nested(payload, "observables", "structure_factor_ratio", "error")
        if isinstance(error, (int, float)):
            cells.append(
                {
                    "cell": manifest.parent.name,
                    "path": str(manifest.relative_to(ROOT)),
                    "alpha": payload.get("params", {}).get("alpha"),
                    "beta": payload.get("params", {}).get("beta"),
                    "L": payload.get("params", {}).get("L"),
                    "error": float(error),
                    "status": payload.get("status"),
                    "accepted": nested(payload, "acceptance", "children_accepted"),
                }
            )
    cells.sort(key=lambda row: row["error"], reverse=True)

    slices = []
    for report in guard["slices"]:
        internal = report["interior_entries"]
        slices.append(
            {
                "beta": report["slice"],
                "size_pair": report["size_pair"],
                "internal_count": len(internal),
                "internal_signs": dict(Counter(item["sign"] for item in internal)),
                "edge_signs": dict(Counter(item["sign"] for item in report["edge_entries"])),
                "status": report["status"],
            }
        )

    high_error_pair = next(
        item
        for item in next(report for report in guard["slices"] if report["slice"] == 1.0)["interior_entries"]
        if item["control"] == 0.125
    )
    high_error_pair["absolute_sigma"] = abs(high_error_pair["delta"]) / high_error_pair["error"]

    result = {
        "schema_version": 1,
        "created_at": "2026-08-03",
        "scope": {"alpha_min": 0.0, "beta_min": 0.0, "negative_alpha_included": False},
        "guard": {
            "status": guard["status"],
            "sigma": guard["sigma"],
            "size_pair": [60, 80],
            "slices": slices,
        },
        "records": {
            "merged_total": len(merged),
            "merged_success": len(successful),
            "merged_unique_keys": len(unique_keys),
            "mesh_difference_rows": len(mesh),
            "internal_difference_rows": len(internal_mesh),
            "internal_difference_not_significant": sum(
                row["significant_2sigma"].lower() != "true" for row in internal_mesh
            ),
            "internal_delta_min": min(float(row["delta_R"]) for row in internal_mesh),
            "internal_delta_max": max(float(row["delta_R"]) for row in internal_mesh),
        },
        "high_error_cells": cells[:5],
        "high_error_pair_evidence": high_error_pair,
        "interpretation": "在固定正区和最终 60/80 尺寸对上，alpha>0 的全部内部尺寸差显著为负；这支持‘当前数据未见可验收内部 crossing’，但不证明热力学极限单相。cell-0051 单独保留为高误差复核对象。",
        "source_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in [OBS, GUARD, MESH_CSV]},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": guard["status"], "merged": len(merged), "internal_rows": len(internal_mesh)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
