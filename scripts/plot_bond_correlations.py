"""绘制键关联及左右不对称性。"""

import csv
import glob
import os
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np


TYPE_ORDER = ["J2_left", "J1_left", "J1_right", "J2_right", "J3"]
INDEPENDENT_TYPES = ["J2", "J1", "J3"]


def load_data():
    data = {}
    for path in glob.glob("data/bond_correlations/bond_*.csv"):
        rows = list(csv.DictReader(open(path, newline="", encoding="utf-8")))
        alpha = float(rows[0]["alpha"])
        data[alpha] = rows
    return data


def bulk_average(rows):
    grouped = defaultdict(list)
    for row in rows:
        bond = int(row["bond"])
        if 15 <= bond <= 85:
            grouped[row["bond_type"]].append(float(row["SdotS"]))
    return {key: np.mean(values) for key, values in grouped.items()}


def summarize(averages):
    summary = []
    for alpha in sorted(averages):
        values = averages[alpha]
        summary.append(
            {
                "alpha": alpha,
                "J2": 0.5 * (
                    values["J2_left"] + values["J2_right"]
                ),
                "J1": 0.5 * (
                    values["J1_left"] + values["J1_right"]
                ),
                "J3": values["J3"],
                "dimer_J1": (
                    values["J1_left"] - values["J1_right"]
                ),
                "dimer_J2": (
                    values["J2_left"] - values["J2_right"]
                ),
            }
        )
    return summary


def save_summary(summary):
    path = "data/bond_correlations/bulk_summary_b0.5_L100.csv"
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=summary[0].keys())
        writer.writeheader()
        writer.writerows(summary)


def plot_data(data):
    fig, (axis_profile, axis_average, axis_dimer) = plt.subplots(
        1, 3, figsize=(15.5, 4.8)
    )
    colors = plt.cm.viridis(np.linspace(0.1, 0.9, len(data)))

    averages = {}
    for color, (alpha, rows) in zip(colors, sorted(data.items())):
        bonds = np.asarray([int(row["bond"]) for row in rows])
        values = np.asarray([float(row["SdotS"]) for row in rows])
        axis_profile.plot(
            bonds,
            values,
            linewidth=1,
            color=color,
            label=rf"$\alpha={alpha:.2f}$",
        )
        averages[alpha] = bulk_average(rows)

    summary = summarize(averages)
    save_summary(summary)
    alpha = np.asarray([row["alpha"] for row in summary])

    for bond_type in INDEPENDENT_TYPES:
        values = np.asarray([row[bond_type] for row in summary])
        axis_average.plot(
            alpha,
            values,
            marker="o",
            linewidth=1.4,
            label=bond_type,
        )

    axis_profile.set_xlabel("Bond")
    axis_profile.set_ylabel(r"$\langle\mathbf{S}_i\cdot\mathbf{S}_{i+1}\rangle$")
    axis_profile.set_title("Bond-correlation profiles")
    axis_profile.grid(alpha=0.25)
    axis_profile.legend(fontsize=9)

    axis_average.set_xlabel(r"$\alpha=J_2/J_1$")
    axis_average.set_ylabel("Bulk bond correlation")
    axis_average.set_title("Independent bond classes")
    axis_average.grid(alpha=0.25)
    axis_average.legend(fontsize=8)

    for key, label in [
        ("dimer_J1", r"$|\Delta J_1|$"),
        ("dimer_J2", r"$|\Delta J_2|$"),
    ]:
        values = np.abs([row[key] for row in summary])
        axis_dimer.semilogy(alpha, values, marker="o", label=label)
    axis_dimer.set_xlabel(r"$\alpha=J_2/J_1$")
    axis_dimer.set_ylabel("Left-right asymmetry")
    axis_dimer.set_title("Dimerization diagnostic")
    axis_dimer.grid(alpha=0.25)
    axis_dimer.legend(fontsize=9)

    fig.tight_layout()
    os.makedirs("figures", exist_ok=True)
    fig.savefig("figures/bond_correlations_b0.5_L100.pdf")
    fig.savefig("figures/bond_correlations_b0.5_L100.png")
    plt.close(fig)
    print("已输出键关联图与体区汇总。")


def main():
    data = load_data()
    if not data:
        raise RuntimeError("没有找到键关联数据")
    plot_data(data)


if __name__ == "__main__":
    main()
