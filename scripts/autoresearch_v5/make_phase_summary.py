#!/usr/bin/env python3
"""生成正区相图扫描的尺寸差汇总和图。"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results" / "autoresearch_v5_20260731" / "round18_final_phase_diagram_positive_L80"
OBS = RUN / "phase-diagram" / "observations_merged.json"
OUT_CSV = RUN / "phase-diagram" / "phase-size-differences.csv"
OUT_PNG = ROOT / "results" / "research_progress" / "positive_phase_size_promotion_20260802.png"


def main() -> None:
    records = json.loads(OBS.read_text(encoding="utf-8"))["records"]
    index = {(r["params"]["beta"], r["params"]["alpha"], r["params"]["L"]): r for r in records}
    rows = []
    for beta in sorted({key[0] for key in index}):
        alphas = sorted({key[1] for key in index if key[0] == beta})
        for alpha in alphas:
            for low, high in ((40, 60), (60, 80)):
                left = index[(beta, alpha, low)]
                right = index[(beta, alpha, high)]
                rows.append({
                    "beta": beta,
                    "alpha": alpha,
                    "size_pair": f"{low}-{high}",
                    "delta_R": right["value"] - left["value"],
                    "error": (float(left["error"]) ** 2 + float(right["error"]) ** 2) ** 0.5,
                    "low_value": left["value"],
                    "high_value": right["value"],
                })
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    fig, axes = plt.subplots(3, 2, figsize=(10.5, 8.0), sharex=True, sharey=False)
    colors = {"40-60": "#1769aa", "60-80": "#d97706"}
    for row_index, beta in enumerate(sorted({row["beta"] for row in rows})):
        for col_index, pair in enumerate(("40-60", "60-80")):
            axis = axes[row_index, col_index]
            subset = [row for row in rows if row["beta"] == beta and row["size_pair"] == pair]
            xs = [row["alpha"] for row in subset]
            ys = [row["delta_R"] for row in subset]
            errors = [row["error"] for row in subset]
            axis.axhline(0.0, color="#444444", linewidth=0.8)
            axis.errorbar(xs, ys, yerr=errors, marker="o", color=colors[pair], linewidth=1.8, capsize=3)
            axis.set_title(f"beta={beta:g}, L={pair}")
            axis.grid(alpha=0.2)
            if col_index == 0:
                axis.set_ylabel("Delta R")
            if row_index == 2:
                axis.set_xlabel("alpha")
    fig.suptitle("1x5 Heisenberg: finite-size structure-factor ratio differences")
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=180)
    print(json.dumps({"csv": str(OUT_CSV), "figure": str(OUT_PNG), "rows": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
