#!/usr/bin/env python3
"""汇总 alpha=0.14 双初态加扫结果。"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results" / "autoresearch_v2_20260729" / "round2_alpha014_refinement"
PRIOR = ROOT / "results" / "five_rounds_20260729" / "round4_validation" / "cells" / "cell-0001" / "metrics.csv"


def metrics(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["metric"]: row["value"] for row in csv.DictReader(handle)}


def checksums_valid(cell: Path) -> bool:
    for line in (cell / "checksums.sha256").read_text(encoding="utf-8").splitlines():
        expected, name = line.split("  ", 1)
        if hashlib.sha256((cell / name).read_bytes()).hexdigest() != expected:
            return False
    return True


def rel_diff(left: float, right: float) -> float:
    return abs(left - right) / max(abs(left), abs(right), 1e-15)


def main() -> None:
    rows = []
    for cell in sorted((RUN / "cells").iterdir()):
        manifest = json.loads((cell / "manifest.json").read_text(encoding="utf-8"))
        values = metrics(cell / "metrics.csv")
        rows.append({
            "cell_id": cell.name,
            "status": manifest["status"],
            "init_mode": values["init_mode"],
            "energy_density": float(values["energy_density"]),
            "variance_per_site": float(values["variance_per_site"]),
            "string_order": float(values["string_order"]),
            "center_entropy": float(values["center_entropy"]),
            "actual_maxdim": int(float(values["actual_maxdim"])),
            "max_truncation_error": float(values["max_truncation_error"]),
            "final_energy_change": float(values["final_energy_change"]),
            "algorithm_seconds": float(values["algorithm_seconds"]),
            "checksums_valid": checksums_valid(cell),
            "state_present": (cell / "state.jld2").is_file(),
        })
    with (RUN / "parameter-scan.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    first, second = rows
    prior = metrics(PRIOR)
    selected = min(rows, key=lambda row: row["variance_per_site"])
    acceptance = {
        "cells": len(rows),
        "all_success": all(row["status"] == "success" for row in rows),
        "all_checksums_valid": all(row["checksums_valid"] for row in rows),
        "all_states_present": all(row["state_present"] for row in rows),
        "max_variance_per_site": max(row["variance_per_site"] for row in rows),
        "strengthened_variance_target": 1e-9,
        "strengthened_variance_pass": max(row["variance_per_site"] for row in rows) <= 1e-9,
        "energy_density_difference": abs(first["energy_density"] - second["energy_density"]),
        "string_order_relative_difference": rel_diff(first["string_order"], second["string_order"]),
        "initial_state_pass": abs(first["energy_density"] - second["energy_density"]) <= 1e-7
        and rel_diff(first["string_order"], second["string_order"]) <= 0.02,
        "max_final_energy_change": max(row["final_energy_change"] for row in rows),
        "prior_variance_per_site": float(prior["variance_per_site"]),
        "variance_improvement_factor": float(prior["variance_per_site"])
        / max(max(row["variance_per_site"] for row in rows), 1e-30),
        "selected_cell": selected["cell_id"],
        "selected_state": str((RUN / "cells" / selected["cell_id"] / "state.jld2").relative_to(ROOT)).replace("\\", "/"),
    }
    acceptance["round_pass"] = bool(
        acceptance["all_success"]
        and acceptance["all_checksums_valid"]
        and acceptance["all_states_present"]
        and acceptance["strengthened_variance_pass"]
        and acceptance["initial_state_pass"]
    )
    (RUN / "acceptance.json").write_text(json.dumps(acceptance, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(acceptance, ensure_ascii=False))


if __name__ == "__main__":
    main()
