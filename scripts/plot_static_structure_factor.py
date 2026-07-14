"""绘制候选中间区域的静态结构因子。"""

import csv
import glob
import os

import matplotlib.pyplot as plt
import numpy as np


def main():
    paths = sorted(glob.glob("data/static_structure_factor/Sq_*.csv"))
    if not paths:
        raise RuntimeError("没有找到静态结构因子数据")

    peak_rows = []
    fig, axis = plt.subplots(figsize=(7.2, 4.8))
    for path in paths:
        rows = list(csv.DictReader(open(path, encoding="utf-8")))
        alpha = float(rows[0]["alpha"])
        q = np.asarray([float(row["q"]) for row in rows])
        structure_factor = np.asarray(
            [float(row["Sq"]) for row in rows]
        )
        interior = slice(1, -1)
        peak_index = np.argmax(structure_factor[interior]) + 1
        peak_rows.append(
            {
                "alpha": alpha,
                "q_peak": q[peak_index],
                "q_peak_over_pi": q[peak_index] / np.pi,
                "Sq_peak": structure_factor[peak_index],
            }
        )
        axis.plot(
            q / np.pi,
            structure_factor,
            label=rf"$\alpha={alpha:.2f}$",
        )

    axis.set_xlabel(r"$q/\pi$")
    axis.set_ylabel(r"$S(q)$")
    axis.set_title("Static spin structure factor")
    axis.grid(alpha=0.25)
    axis.legend()
    fig.tight_layout()

    os.makedirs("figures", exist_ok=True)
    fig.savefig("figures/static_structure_factor_b0.5_L100.pdf")
    fig.savefig("figures/static_structure_factor_b0.5_L100.png", dpi=240)
    plt.close(fig)

    with open(
        "data/static_structure_factor/peak_summary_b0.5_L100.csv",
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(file, fieldnames=peak_rows[0].keys())
        writer.writeheader()
        writer.writerows(peak_rows)
    print("已输出静态结构因子图与峰位汇总。")


if __name__ == "__main__":
    main()
