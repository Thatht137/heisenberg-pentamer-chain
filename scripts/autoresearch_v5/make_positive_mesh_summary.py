#!/usr/bin/env python3
"""生成扩展正区网格的尺寸差表和图。"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results" / "autoresearch_v5_20260802" / "round19_phase_diagram_positive_mesh"
OBS = RUN / "phase-diagram" / "observations_merged.json"
OUT_CSV = RUN / "phase-diagram" / "phase-size-differences.csv"
OUT_JSON = RUN / "phase-diagram" / "mesh-summary.json"
OUT_PNG = ROOT / "results" / "research_progress" / "positive_phase_mesh_size_differences_20260802.png"


def main() -> None:
    records = json.loads(OBS.read_text(encoding="utf-8"))["records"]
    index = {(r["params"]["beta"], r["params"]["alpha"], r["params"]["L"]): r for r in records}
    betas = sorted({key[0] for key in index})
    alphas = sorted({key[1] for key in index})
    rows = []
    for beta in betas:
        for alpha in alphas:
            for low, high in ((40, 60), (60, 80)):
                left = index[(beta, alpha, low)]
                right = index[(beta, alpha, high)]
                error = math.hypot(float(left["error"]), float(right["error"]))
                delta = float(right["value"]) - float(left["value"])
                rows.append({
                    "beta": beta,
                    "alpha": alpha,
                    "size_pair": f"{low}-{high}",
                    "delta_R": delta,
                    "error": error,
                    "significant_2sigma": abs(delta) > 2.0 * error,
                })
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "schema_version": 1,
        "betas": betas,
        "alphas": alphas,
        "sizes": [40, 60, 80],
        "record_count": len(records),
        "rows": len(rows),
        "negative_alpha_excluded": True,
    }
    OUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    fig, axes = plt.subplots(len(betas), 2, figsize=(10.5, max(8.0, 2.4 * len(betas))), sharex=True)
    if len(betas) == 1:
        axes = [axes]
    colors = {"40-60": "#1769aa", "60-80": "#d97706"}
    for row_index, beta in enumerate(betas):
        for col_index, pair in enumerate(("40-60", "60-80")):
            axis = axes[row_index][col_index]
            subset = [row for row in rows if row["beta"] == beta and row["size_pair"] == pair]
            axis.axhline(0.0, color="#444444", linewidth=0.8)
            axis.errorbar(
                [row["alpha"] for row in subset],
                [row["delta_R"] for row in subset],
                yerr=[row["error"] for row in subset],
                marker="o", color=colors[pair], linewidth=1.5, capsize=3,
            )
            axis.set_title(f"beta={beta:g}, L={pair}")
            axis.grid(alpha=0.2)
            if col_index == 0:
                axis.set_ylabel("Delta R")
            if row_index == len(betas) - 1:
                axis.set_xlabel("alpha")
    fig.suptitle("1x5 Heisenberg: positive-region mesh finite-size differences")
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=180)
    print(json.dumps({"csv": str(OUT_CSV), "figure": str(OUT_PNG), "records": len(records)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
