"""
提取单五聚体最低总自旋多重态并绘图。
"""

import csv
import os
from collections import defaultdict

import matplotlib as mpl
import matplotlib.pyplot as plt


INPUT_PATH = "data/single_pentamer_levels.csv"
OUTPUT_PATH = "data/single_pentamer_low_energy_summary.csv"
FIGURE_STEM = "figures/single_pentamer_low_energy_multiplets"
SPINS = (0.5, 1.5, 2.5)


def load_lowest_energies():
    grouped = defaultdict(lambda: {spin: float("inf") for spin in SPINS})
    with open(INPUT_PATH, newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            alpha = float(row["alpha"])
            spin = float(row["spin_S"])
            energy = float(row["energy"])
            if spin in grouped[alpha]:
                grouped[alpha][spin] = min(grouped[alpha][spin], energy)
    return grouped


def export_summary(grouped):
    rows = []
    for alpha in sorted(grouped):
        energies = grouped[alpha]
        ground_energy = min(energies.values())
        ground_spins = [
            spin for spin, energy in energies.items()
            if abs(energy - ground_energy) < 1e-8
        ]
        rows.append({
            "alpha": alpha,
            "E0": ground_energy,
            "ground_spins": "|".join(f"{spin:.1f}" for spin in ground_spins),
            **{
                f"gap_S{spin:.1f}": energies[spin] - ground_energy
                for spin in SPINS
            },
        })

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as file:
        fieldnames = [
            "alpha", "E0", "ground_spins",
            "gap_S0.5", "gap_S1.5", "gap_S2.5",
        ]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def plot_summary(rows):
    mpl.rcParams.update({
        "font.family": "Arial",
        "font.size": 7,
        "axes.labelsize": 8,
        "legend.fontsize": 7,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "pdf.fonttype": 42,
        "svg.fonttype": "none",
    })

    colors = {
        0.5: "#0072B2",
        1.5: "#D55E00",
        2.5: "#6B6B6B",
    }
    labels = {
        0.5: r"$S=1/2$",
        1.5: r"$S=3/2$",
        2.5: r"$S=5/2$",
    }
    alphas = [row["alpha"] for row in rows]

    fig, ax = plt.subplots(figsize=(3.55, 2.75))
    for spin in SPINS:
        gaps = [row[f"gap_S{spin:.1f}"] for row in rows]
        ax.plot(
            alphas,
            gaps,
            color=colors[spin],
            linewidth=1.5,
            label=labels[spin],
        )

    ax.axvline(0.0, color="black", linewidth=0.8, linestyle="--")
    ax.text(
        0.02,
        0.96,
        r"$\alpha=0$: $S=1/2$ and $S=3/2$ ground multiplets",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=6.5,
    )
    ax.set_xlabel(r"$\alpha=J_2/J_1$")
    ax.set_ylabel(r"$E_S-E_0$ ($J_1$)")
    ax.set_xlim(min(alphas), max(alphas))
    ax.set_ylim(bottom=-0.02)
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.16))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(direction="out", length=3)
    fig.tight_layout()

    os.makedirs("figures", exist_ok=True)
    fig.savefig(f"{FIGURE_STEM}.pdf", bbox_inches="tight")
    fig.savefig(f"{FIGURE_STEM}.svg", bbox_inches="tight")
    fig.savefig(f"{FIGURE_STEM}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def main():
    grouped = load_lowest_energies()
    rows = export_summary(grouped)
    plot_summary(rows)
    print(f"已保存: {OUTPUT_PATH}")
    print(f"已保存: {FIGURE_STEM}.pdf/.svg/.png")


if __name__ == "__main__":
    main()
