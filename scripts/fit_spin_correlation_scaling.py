"""拟合多尺寸实空间自旋关联。"""

import csv
import glob
import os
import re

import matplotlib.pyplot as plt
import numpy as np


FILE_PATTERN = re.compile(r"corr_a([0-9.]+)_b([0-9.]+)_L([0-9]+)")


def load_profiles():
    profiles = {}
    for path in glob.glob("data/spin_correlations/tasks/corr_*.csv"):
        match = FILE_PATTERN.search(os.path.basename(path))
        if not match:
            continue
        alpha = float(match.group(1))
        length = int(match.group(3))
        rows = list(csv.DictReader(open(path, encoding="utf-8")))
        distance = np.asarray([int(row["distance"]) for row in rows])
        staggered = np.asarray(
            [float(row["staggered"]) for row in rows]
        )
        profiles[(alpha, length)] = (distance, staggered)
    return profiles


def fit_profile(distance, staggered, length):
    mask = (
        (distance >= 4)
        & (distance <= length // 3)
        & (staggered > 0)
    )
    selected_distance = distance[mask]
    selected_values = staggered[mask]
    coefficients, covariance = np.polyfit(
        np.log(selected_distance),
        np.log(selected_values),
        1,
        cov=True,
    )
    exponent = -coefficients[0]
    exponent_error = np.sqrt(covariance[0, 0])
    prediction = np.polyval(
        coefficients,
        np.log(selected_distance),
    )
    residual = np.log(selected_values) - prediction
    power_rms_log = np.sqrt(np.mean(residual**2))

    exponential = np.polyfit(
        selected_distance,
        np.log(selected_values),
        1,
    )
    exponential_prediction = np.polyval(
        exponential,
        selected_distance,
    )
    exponential_residual = (
        np.log(selected_values) - exponential_prediction
    )
    exponential_rms_log = np.sqrt(
        np.mean(exponential_residual**2)
    )
    return (
        exponent,
        exponent_error,
        power_rms_log,
        exponential_rms_log,
    )


def main():
    profiles = load_profiles()
    if not profiles:
        raise RuntimeError("没有找到实空间关联数据")

    alphas = sorted({key[0] for key in profiles})
    lengths = sorted({key[1] for key in profiles})
    colors = plt.cm.viridis(np.linspace(0.1, 0.9, len(lengths)))
    fig, axes = plt.subplots(1, len(alphas), figsize=(15, 4.6))
    summary = []

    for axis, alpha in zip(axes, alphas):
        for color, length in zip(colors, lengths):
            distance, staggered = profiles[(alpha, length)]
            (
                exponent,
                error,
                power_rms_log,
                exponential_rms_log,
            ) = fit_profile(
                distance,
                staggered,
                length,
            )
            summary.append(
                {
                    "alpha": alpha,
                    "L": length,
                    "eta": exponent,
                    "eta_error": error,
                    "power_rms_log": power_rms_log,
                    "exponential_rms_log": exponential_rms_log,
                    "rms_ratio_exp_over_power": (
                        exponential_rms_log / power_rms_log
                    ),
                }
            )
            mask = staggered > 0
            axis.loglog(
                distance[mask],
                staggered[mask],
                marker="o",
                markersize=3,
                linewidth=1,
                color=color,
                label=rf"$L={length}$, $\eta={exponent:.2f}$",
            )
        axis.set_title(rf"$\alpha={alpha:.2f}$")
        axis.set_xlabel(r"$r$")
        axis.grid(alpha=0.25)
        axis.legend(fontsize=8)
    axes[0].set_ylabel(r"$(-1)^r C(r)$")
    fig.tight_layout()

    os.makedirs("figures", exist_ok=True)
    fig.savefig("figures/spin_correlation_scaling_b0.5.pdf")
    fig.savefig("figures/spin_correlation_scaling_b0.5.png", dpi=240)
    plt.close(fig)

    with open(
        "data/spin_correlations/power_law_fits_b0.5.csv",
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(file, fieldnames=summary[0].keys())
        writer.writeheader()
        writer.writerows(summary)
    print("已输出关联标度图与幂律拟合表。")


if __name__ == "__main__":
    main()
