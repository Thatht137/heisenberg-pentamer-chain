"""绘制五种中心切口的纠缠谱。"""

import csv
import glob
import os

import matplotlib.pyplot as plt
import numpy as np


def load_data():
    data = {}
    for path in glob.glob("data/entanglement_spectrum/spectrum_*.csv"):
        rows = list(csv.DictReader(open(path, encoding="utf-8")))
        alpha = float(rows[0]["alpha"])
        grouped = {}
        for row in rows:
            bond_class = int(row["bond_class"])
            grouped.setdefault(bond_class, []).append(
                float(row["entanglement_energy"])
            )
        data[alpha] = grouped
    return data


def plot_quantum_numbers():
    selected = {}
    for path in glob.glob("data/entanglement_spectrum/spectrum_*.csv"):
        rows = list(csv.DictReader(open(path, encoding="utf-8")))
        if "schmidt_sz" not in rows[0]:
            continue
        alpha = float(rows[0]["alpha"])
        if alpha not in (-0.50, 0.14):
            continue
        selected[alpha] = rows
    if len(selected) != 2:
        return

    fig, axes = plt.subplots(
        2,
        2,
        figsize=(9, 7),
        sharey="row",
        constrained_layout=True,
    )
    scatter = None
    for row_index, alpha in enumerate(sorted(selected)):
        rows = selected[alpha]
        for column_index, bond_class in enumerate([0, 1]):
            filtered = [
                row
                for row in rows
                if int(row["bond_class"]) == bond_class
            ]
            energy = np.asarray(
                [float(row["entanglement_energy"]) for row in filtered]
            )
            schmidt_sz = np.asarray(
                [float(row["schmidt_sz"]) for row in filtered]
            )
            scatter = axes[row_index, column_index].scatter(
                np.arange(1, len(energy) + 1),
                energy - energy[0],
                c=schmidt_sz,
                cmap="coolwarm",
                vmin=-2,
                vmax=2,
                s=36,
            )
            axes[row_index, column_index].set_title(
                rf"$\alpha={alpha:.2f}$, cut={bond_class}"
            )
            axes[row_index, column_index].grid(alpha=0.25)
            axes[row_index, column_index].set_xlabel("Level")
        axes[row_index, 0].set_ylabel(r"$\xi_i-\xi_1$")
    fig.colorbar(
        scatter,
        ax=axes.ravel().tolist(),
        label=r"Schmidt $S^z$",
        fraction=0.03,
        pad=0.03,
    )
    fig.savefig("figures/entanglement_spectrum_qn_b0.5_L80.pdf")
    fig.savefig(
        "figures/entanglement_spectrum_qn_b0.5_L80.png",
        dpi=220,
    )
    plt.close(fig)


def main():
    data = load_data()
    if not data:
        raise RuntimeError("没有找到纠缠谱数据")

    alphas = sorted(data)
    fig, axes = plt.subplots(
        len(alphas),
        5,
        figsize=(14, 2.8 * len(alphas)),
        sharey="row",
    )
    if len(alphas) == 1:
        axes = np.asarray([axes])
    summary = []

    for row_index, alpha in enumerate(alphas):
        for bond_class in range(5):
            axis = axes[row_index, bond_class]
            levels = np.asarray(data[alpha][bond_class])
            axis.scatter(
                np.arange(1, len(levels) + 1),
                levels - levels[0],
                s=18,
            )
            axis.set_title(
                rf"$\alpha={alpha:.2f}$, cut={bond_class}"
            )
            axis.set_xlabel("Level")
            axis.grid(alpha=0.25)
            summary.append(
                {
                    "alpha": alpha,
                    "bond_class": bond_class,
                    "delta_12": levels[1] - levels[0],
                    "delta_34": levels[3] - levels[2],
                    "delta_23": levels[2] - levels[1],
                }
            )
        axes[row_index, 0].set_ylabel(
            r"$\xi_i-\xi_1$"
        )

    fig.tight_layout()
    os.makedirs("figures", exist_ok=True)
    fig.savefig("figures/entanglement_spectrum_b0.5_L80.pdf")
    fig.savefig("figures/entanglement_spectrum_b0.5_L80.png", dpi=220)
    plt.close(fig)

    with open(
        "data/entanglement_spectrum/splitting_summary_b0.5_L80.csv",
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(file, fieldnames=summary[0].keys())
        writer.writeheader()
        writer.writerows(summary)
    plot_quantum_numbers()
    print("已输出五切口纠缠谱。")


if __name__ == "__main__":
    main()
