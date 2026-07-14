"""绘制弦序的距离和尺寸依赖。"""

import csv
import os
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np


DATA_DIR = "data/string_order_distance/tasks"
OUTPUT_DIR = "figures"


def load_data():
    if not os.path.isdir(DATA_DIR):
        raise FileNotFoundError(f"找不到数据目录：{DATA_DIR}")

    grouped = defaultdict(list)
    for name in sorted(os.listdir(DATA_DIR)):
        if not name.endswith(".csv"):
            continue
        path = os.path.join(DATA_DIR, name)
        with open(path, newline="", encoding="utf-8") as file:
            for row in csv.DictReader(file):
                key = (float(row["alpha"]), float(row["beta"]), int(row["L"]))
                grouped[key].append(
                    (
                        int(row["distance_units"]),
                        float(row["O_mean"]),
                        float(row["O_sem"]),
                    )
                )

    if not grouped:
        raise RuntimeError(f"{DATA_DIR} 中没有 CSV 数据")

    for values in grouped.values():
        values.sort()
    return grouped


def configure_style():
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 11,
            "axes.labelsize": 12,
            "axes.titlesize": 13,
            "legend.fontsize": 9,
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
        }
    )


def plot_profiles(grouped, use_absolute=False):
    alphas = sorted({key[0] for key in grouped})
    betas = sorted({key[1] for key in grouped})
    if len(betas) != 1:
        raise ValueError("一次绘图只支持一个 beta")

    beta = betas[0]
    ncols = 2
    nrows = int(np.ceil(len(alphas) / ncols))
    fig, axes = plt.subplots(
        nrows,
        ncols,
        figsize=(10, 4.2 * nrows),
        squeeze=False,
    )

    for axis, alpha in zip(axes.flat, alphas):
        sizes = sorted(key[2] for key in grouped if key[0] == alpha)
        colors = plt.cm.viridis(np.linspace(0.15, 0.85, len(sizes)))
        for color, L in zip(colors, sizes):
            rows = grouped[(alpha, beta, L)]
            distance = np.array([row[0] for row in rows])
            values = np.array([row[1] for row in rows])
            errors = np.array([row[2] for row in rows])
            if use_absolute:
                values = np.abs(values)

            axis.errorbar(
                distance,
                values,
                yerr=errors,
                marker="o",
                markersize=4,
                linewidth=1.4,
                capsize=2,
                color=color,
                label=f"L={L}",
            )

        axis.axhline(0, color="0.6", linewidth=0.7)
        axis.set_xlabel("Distance (unit cells)")
        axis.set_ylabel(
            r"$|O_{\mathrm{str}}^z(r)|$"
            if use_absolute
            else r"$O_{\mathrm{str}}^z(r)$"
        )
        axis.set_title(rf"$\alpha={alpha:+.2f},\ \beta={beta:.2f}$")
        axis.grid(alpha=0.25)
        axis.legend()

    for axis in axes.flat[len(alphas):]:
        axis.set_visible(False)

    fig.tight_layout()
    suffix = "abs" if use_absolute else "signed"
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    basename = f"string_order_distance_b{beta:.2f}_{suffix}"
    fig.savefig(os.path.join(OUTPUT_DIR, f"{basename}.pdf"))
    fig.savefig(os.path.join(OUTPUT_DIR, f"{basename}.png"))
    plt.close(fig)
    print(f"已输出：figures/{basename}.pdf")


def main():
    configure_style()
    grouped = load_data()
    plot_profiles(grouped, use_absolute=False)
    plot_profiles(grouped, use_absolute=True)


if __name__ == "__main__":
    main()
