"""绘制边缘磁化并汇总边缘权重。"""

import csv
import glob
import os
import re

import matplotlib.pyplot as plt
import numpy as np


FILE_PATTERN = re.compile(r"edge_a(-?[0-9.]+)_b[0-9.]+_L([0-9]+)")


def load_profiles():
    profiles = {}
    for path in glob.glob("data/edge_magnetization/tasks/edge_*.csv"):
        match = FILE_PATTERN.search(os.path.basename(path))
        if not match:
            continue
        alpha = float(match.group(1))
        length = int(match.group(2))
        rows = list(csv.DictReader(open(path, encoding="utf-8")))
        magnetization = np.asarray(
            [float(row["Sz"]) for row in rows]
        )
        profiles[(alpha, length)] = magnetization
    return profiles


def main():
    profiles = load_profiles()
    if not profiles:
        raise RuntimeError("没有找到边缘磁化数据")

    alphas = sorted({key[0] for key in profiles})
    lengths = sorted({key[1] for key in profiles})
    largest_length = max(lengths)
    fig, axes = plt.subplots(
        len(alphas),
        2,
        figsize=(11, 2.8 * len(alphas)),
    )
    summary = []

    for row_index, alpha in enumerate(alphas):
        profile_axis = axes[row_index, 0]
        cumulative_axis = axes[row_index, 1]
        magnetization = profiles[(alpha, largest_length)]
        sites = np.arange(1, largest_length + 1)
        profile_axis.plot(sites, magnetization, linewidth=1)
        profile_axis.set_title(
            rf"$\alpha={alpha:.2f}$, $L={largest_length}$"
        )
        profile_axis.set_ylabel(r"$\langle S_i^z\rangle$")
        profile_axis.grid(alpha=0.25)

        distance = np.arange(1, largest_length // 2 + 1)
        left = np.cumsum(magnetization)[: largest_length // 2]
        right = np.cumsum(magnetization[::-1])[: largest_length // 2]
        cumulative_axis.plot(distance, left, label="left")
        cumulative_axis.plot(distance, right, "--", label="right")
        cumulative_axis.axhline(0.5, color="black", linewidth=0.8)
        cumulative_axis.set_title("Cumulative edge magnetization")
        cumulative_axis.grid(alpha=0.25)
        cumulative_axis.legend(fontsize=8)

        for length in lengths:
            values = profiles[(alpha, length)]
            edge_5 = np.sum(values[:5]) + np.sum(values[-5:])
            edge_10 = np.sum(values[:10]) + np.sum(values[-10:])
            absolute_sum = np.sum(np.abs(values))
            inverse_participation = (
                np.sum(values**2) / absolute_sum**2
            )
            summary.append(
                {
                    "alpha": alpha,
                    "L": length,
                    "total_Sz": np.sum(values),
                    "edge_weight_5": edge_5,
                    "edge_weight_10": edge_10,
                    "inverse_participation": inverse_participation,
                }
            )

    axes[-1, 0].set_xlabel("Site")
    axes[-1, 1].set_xlabel("Distance from edge")
    fig.tight_layout()
    os.makedirs("figures", exist_ok=True)
    fig.savefig("figures/edge_magnetization_b0.5.pdf")
    fig.savefig("figures/edge_magnetization_b0.5.png", dpi=220)
    plt.close(fig)

    with open(
        "data/edge_magnetization/edge_summary_b0.5.csv",
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(file, fieldnames=summary[0].keys())
        writer.writeheader()
        writer.writerows(summary)

    extrapolation = []
    scaling_figure, scaling_axis = plt.subplots(figsize=(7.2, 4.8))
    for alpha in alphas:
        rows = [row for row in summary if row["alpha"] == alpha]
        inverse_length = np.asarray([1 / row["L"] for row in rows])
        edge_weight = np.asarray(
            [row["edge_weight_10"] for row in rows]
        )
        coefficients = np.polyfit(inverse_length, edge_weight, 1)
        prediction = np.polyval(coefficients, inverse_length)
        rms = np.sqrt(np.mean((edge_weight - prediction) ** 2))
        power_coefficients = np.polyfit(
            np.log([row["L"] for row in rows]),
            np.log(edge_weight),
            1,
        )
        power_prediction = np.polyval(
            power_coefficients,
            np.log([row["L"] for row in rows]),
        )
        power_rms = np.sqrt(
            np.mean(
                (
                    np.log(edge_weight) - power_prediction
                )
                ** 2
            )
        )
        extrapolation.append(
            {
                "alpha": alpha,
                "edge_weight_10_infinite": coefficients[1],
                "slope": coefficients[0],
                "fit_rms": rms,
                "edge_decay_exponent": -power_coefficients[0],
                "power_fit_rms": power_rms,
            }
        )
        order = np.argsort(inverse_length)
        scaling_axis.plot(
            inverse_length[order],
            edge_weight[order],
            marker="o",
            label=(
                rf"$\alpha={alpha:.2f}$, "
                rf"$\gamma={-power_coefficients[0]:.2f}$"
            ),
        )
    scaling_axis.set_xlabel(r"$1/L$")
    scaling_axis.set_ylabel("Ten-site edge weight")
    scaling_axis.set_title("Edge-weight finite-size scaling")
    scaling_axis.grid(alpha=0.25)
    scaling_axis.legend()
    scaling_figure.tight_layout()
    scaling_figure.savefig("figures/edge_weight_scaling_b0.5.pdf")
    scaling_figure.savefig(
        "figures/edge_weight_scaling_b0.5.png",
        dpi=220,
    )
    plt.close(scaling_figure)

    with open(
        "data/edge_magnetization/edge_extrapolation_b0.5.csv",
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=extrapolation[0].keys(),
        )
        writer.writeheader()
        writer.writerows(extrapolation)
    print("已输出边缘磁化图与汇总表。")


if __name__ == "__main__":
    main()
