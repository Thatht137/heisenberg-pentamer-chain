"""绘制自旋能隙的有限尺寸标度。"""

import csv
import glob
import math
import os
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np


DEFAULT_ALPHAS = (0.10, 0.20, 0.25, 0.30, 0.40, 0.50)


def selected_alphas():
    text = os.environ.get("PENTAMER_GAP_PLOT_ALPHAS")
    if not text:
        return set(DEFAULT_ALPHAS)
    return {float(value.strip()) for value in text.split(",")}


def load_data():
    grouped = defaultdict(list)
    allowed = selected_alphas()
    for path in glob.glob("data/spin_gap/tasks/*.csv"):
        with open(path, newline="", encoding="utf-8") as file:
            row = next(csv.DictReader(file))
        alpha = float(row["alpha"])
        if alpha not in allowed:
            continue
        grouped[alpha].append(
            (int(row["L"]), float(row["spin_gap"]))
        )

    for values in grouped.values():
        values.sort()
    return grouped


def fit_gap(values):
    sizes = np.asarray([row[0] for row in values], dtype=float)
    gaps = np.asarray([row[1] for row in values])
    coefficients = np.polyfit(1.0 / sizes, gaps, 1)
    return coefficients[1], coefficients


def write_results(grouped):
    output = "data/spin_gap/spin_gap_extrapolation_b0.5.csv"
    os.makedirs(os.path.dirname(output), exist_ok=True)
    with open(output, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["alpha", "gap_infinite", "n_sizes"])
        for alpha, values in sorted(grouped.items()):
            if len(values) >= 3:
                gap_infinite, _ = fit_gap(values)
                writer.writerow(
                    [f"{alpha:.6f}", f"{gap_infinite:.10f}", len(values)]
                )
    print(f"已输出：{output}")


def plot_data(grouped):
    alphas = sorted(grouped)
    ncols = min(4, len(alphas))
    nrows = math.ceil(len(alphas) / ncols)
    fig, axes = plt.subplots(
        nrows,
        ncols,
        figsize=(3.8 * ncols, 3.3 * nrows),
        squeeze=False,
    )

    for axis, alpha in zip(axes.flat, alphas):
        values = grouped[alpha]
        sizes = np.asarray([row[0] for row in values], dtype=float)
        gaps = np.asarray([row[1] for row in values])
        inverse = 1.0 / sizes
        axis.plot(inverse, gaps, "o", color="tab:blue")

        if len(values) >= 3:
            gap_infinite, coefficients = fit_gap(values)
            grid = np.linspace(0, inverse.max(), 100)
            axis.plot(
                grid,
                np.polyval(coefficients, grid),
                "--",
                color="tab:red",
            )
            axis.text(
                0.05,
                0.92,
                rf"$\Delta_\infty={gap_infinite:.4f}$",
                transform=axis.transAxes,
                va="top",
            )

        axis.axhline(0, color="0.6", linewidth=0.8)
        axis.set_xlabel(r"$1/L$")
        axis.set_ylabel(r"$\Delta_s$")
        axis.set_title(rf"$\alpha={alpha:.2f}$")
        axis.grid(alpha=0.25)

    for axis in axes.flat[len(alphas):]:
        axis.set_visible(False)

    fig.suptitle(r"Spin-gap scaling at $\beta=0.5$")
    fig.tight_layout()
    os.makedirs("figures", exist_ok=True)
    fig.savefig("figures/spin_gap_scaling_b0.5.pdf")
    fig.savefig("figures/spin_gap_scaling_b0.5.png")
    plt.close(fig)
    print("已输出：figures/spin_gap_scaling_b0.5.pdf")


def main():
    grouped = load_data()
    if not grouped:
        raise RuntimeError("没有找到自旋能隙数据")
    write_results(grouped)
    plot_data(grouped)


if __name__ == "__main__":
    main()
