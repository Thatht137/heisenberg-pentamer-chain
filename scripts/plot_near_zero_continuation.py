"""分析近零点双分支参数连续 DMRG。"""

import csv
import os

import matplotlib.pyplot as plt
import numpy as np


def main():
    path = "data/near_zero_continuation/profiles_b0.50_L060.csv"
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    grouped = {}
    for row in rows:
        key = (float(row["alpha"]), row["branch"])
        grouped.setdefault(key, []).append(row)

    alphas = sorted({key[0] for key in grouped})
    summary = []
    for alpha in alphas:
        left_rows = grouped[(alpha, "left")]
        right_rows = grouped[(alpha, "right")]
        left_profile = np.asarray(
            [float(row["Sz"]) for row in left_rows]
        )
        right_profile = np.asarray(
            [float(row["Sz"]) for row in right_rows]
        )
        left_energy = float(left_rows[0]["energy"])
        right_energy = float(right_rows[0]["energy"])
        reflected_difference = left_profile - right_profile[::-1]
        summary.append(
            {
                "alpha": alpha,
                "left_energy": left_energy,
                "right_energy": right_energy,
                "energy_difference": left_energy - right_energy,
                "reflection_rms": np.sqrt(
                    np.mean(reflected_difference**2)
                ),
                "left_edge_weight_10": (
                    np.sum(left_profile[:10])
                    + np.sum(left_profile[-10:])
                ),
                "right_edge_weight_10": (
                    np.sum(right_profile[:10])
                    + np.sum(right_profile[-10:])
                ),
                "left_asymmetry_10": (
                    np.sum(left_profile[:10])
                    - np.sum(left_profile[-10:])
                ),
                "right_asymmetry_10": (
                    np.sum(right_profile[:10])
                    - np.sum(right_profile[-10:])
                ),
            }
        )

    alpha = np.asarray([row["alpha"] for row in summary])
    fig, axes = plt.subplots(3, 1, figsize=(7.5, 9.5), sharex=True)
    axes[0].semilogy(
        alpha,
        np.maximum(
            np.abs([row["energy_difference"] for row in summary]),
            1e-14,
        ),
        marker="o",
    )
    axes[1].semilogy(
        alpha,
        [row["reflection_rms"] for row in summary],
        marker="o",
    )
    axes[2].plot(
        alpha,
        [row["left_edge_weight_10"] for row in summary],
        marker="o",
        label="left branch",
    )
    axes[2].plot(
        alpha,
        [row["right_edge_weight_10"] for row in summary],
        marker="o",
        label="right branch",
    )
    axes[0].set_ylabel(r"$|E_L-E_R|$")
    axes[1].set_ylabel("Reflection RMS")
    axes[2].set_ylabel("Ten-site edge weight")
    axes[2].set_xlabel(r"$\alpha$")
    axes[2].legend()
    for axis in axes:
        axis.grid(alpha=0.25)
    fig.tight_layout()

    os.makedirs("figures", exist_ok=True)
    fig.savefig("figures/near_zero_continuation_b0.5_L60.pdf")
    fig.savefig(
        "figures/near_zero_continuation_b0.5_L60.png",
        dpi=220,
    )
    plt.close(fig)

    output = "data/near_zero_continuation/summary_b0.5_L60.csv"
    with open(output, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=summary[0].keys())
        writer.writeheader()
        writer.writerows(summary)
    print("已输出连续 DMRG 诊断。")


if __name__ == "__main__":
    main()
