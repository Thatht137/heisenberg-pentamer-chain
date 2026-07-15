"""汇总 alpha≈0 负侧的多初态结果。"""

import csv
import glob
import os

import matplotlib.pyplot as plt
import numpy as np


def main():
    records = []
    for path in glob.glob("data/near_zero_multistart/tasks/near_*.csv"):
        rows = list(csv.DictReader(open(path, encoding="utf-8")))
        magnetization = np.asarray(
            [float(row["Sz"]) for row in rows]
        )
        records.append(
            {
                "alpha": float(rows[0]["alpha"]),
                "initial_mode": rows[0]["initial_mode"],
                "energy": float(rows[0]["energy"]),
                "edge_weight_10": (
                    np.sum(magnetization[:10])
                    + np.sum(magnetization[-10:])
                ),
                "edge_asymmetry_10": (
                    np.sum(magnetization[:10])
                    - np.sum(magnetization[-10:])
                ),
            }
        )
    if not records:
        raise RuntimeError("没有找到多初态数据")

    alphas = sorted({row["alpha"] for row in records})
    modes = ["center", "left", "right"]
    summary = []
    best_summary = []
    for alpha in alphas:
        group = [row for row in records if row["alpha"] == alpha]
        minimum = min(row["energy"] for row in group)
        for row in group:
            row["energy_above_min"] = row["energy"] - minimum
            summary.append(row)
        best = min(group, key=lambda row: row["energy"])
        left = next(
            row for row in group if row["initial_mode"] == "left"
        )
        right = next(
            row for row in group if row["initial_mode"] == "right"
        )
        best_summary.append(
            {
                "alpha": alpha,
                "best_mode": best["initial_mode"],
                "best_energy": best["energy"],
                "energy_spread": (
                    max(row["energy"] for row in group) - minimum
                ),
                "left_right_energy_difference": abs(
                    left["energy"] - right["energy"]
                ),
                "best_edge_weight_10": best["edge_weight_10"],
                "best_edge_asymmetry_10": best["edge_asymmetry_10"],
            }
        )

    fig, axes = plt.subplots(3, 1, figsize=(7.5, 10), sharex=True)
    for mode in modes:
        rows = sorted(
            [
                row
                for row in summary
                if row["initial_mode"] == mode
            ],
            key=lambda row: row["alpha"],
        )
        alpha = [row["alpha"] for row in rows]
        axes[0].semilogy(
            alpha,
            np.maximum(
                [row["energy_above_min"] for row in rows],
                1e-14,
            ),
            marker="o",
            label=mode,
        )
        axes[1].plot(
            alpha,
            [row["edge_weight_10"] for row in rows],
            marker="o",
            label=mode,
        )
        axes[2].plot(
            alpha,
            [row["edge_asymmetry_10"] for row in rows],
            marker="o",
            label=mode,
        )

    axes[0].set_ylabel(r"$E-E_{\min}$")
    axes[1].set_ylabel("Ten-site edge weight")
    axes[2].set_ylabel("Left-right asymmetry")
    axes[2].set_xlabel(r"$\alpha$")
    for axis in axes:
        axis.grid(alpha=0.25)
        axis.legend(fontsize=8)
    fig.tight_layout()
    os.makedirs("figures", exist_ok=True)
    fig.savefig("figures/near_zero_multistart_b0.5_L60.pdf")
    fig.savefig("figures/near_zero_multistart_b0.5_L60.png", dpi=220)
    plt.close(fig)

    with open(
        "data/near_zero_multistart/summary_b0.5_L60.csv",
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        fieldnames = [
            "alpha",
            "initial_mode",
            "energy",
            "energy_above_min",
            "edge_weight_10",
            "edge_asymmetry_10",
        ]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(
            [{key: row[key] for key in fieldnames} for row in summary]
        )
    with open(
        "data/near_zero_multistart/best_summary_b0.5_L60.csv",
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=best_summary[0].keys(),
        )
        writer.writeheader()
        writer.writerows(best_summary)
    print("已输出近零点多初态诊断。")


if __name__ == "__main__":
    main()
