"""
绘制单五聚体能级图：E(alpha) 按总自旋 S 着色。
输入：data/single_pentamer_levels.csv
输出：figures/energy_levels.pdf/.png
"""

import numpy as np
import matplotlib.pyplot as plt
import csv
import os

# ─── 读取数据 ───
data = {"alpha": [], "level_index": [], "energy": [], "spin_S": []}

with open("data/single_pentamer_levels.csv", "r") as f:
    reader = csv.DictReader(f)
    for row in reader:
        data["alpha"].append(float(row["alpha"]))
        data["level_index"].append(int(row["level_index"]))
        data["energy"].append(float(row["energy"]))
        data["spin_S"].append(float(row["spin_S"]))

alpha = np.array(data["alpha"])
energy = np.array(data["energy"])
spin_S = np.array(data["spin_S"])
level_idx = np.array(data["level_index"])

alpha_vals = np.unique(alpha)
n_alpha = len(alpha_vals)

# ─── 按自旋分组重组数据 ───
spin_groups = {0.5: "S=1/2", 1.5: "S=3/2", 2.5: "S=5/2"}
colors = {0.5: "#2166AC", 1.5: "#F4A582", 2.5: "#B2182B"}

# ─── 绘图 ───
plt.rcParams.update({
    "font.family": "serif",
    "font.size": 11,
    "axes.labelsize": 13,
    "axes.titlesize": 14,
    "xtick.labelsize": 11,
    "ytick.labelsize": 11,
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})

os.makedirs("figures", exist_ok=True)

fig, ax = plt.subplots(figsize=(7, 5))

for s_val, label in spin_groups.items():
    mask = spin_S == s_val
    levels_in_group = np.unique(level_idx[mask])

    first = True
    for lv in levels_in_group:
        lv_mask = mask & (level_idx == lv)
        a = alpha[lv_mask]
        e = energy[lv_mask]
        if first:
            ax.plot(a, e, color=colors[s_val], linewidth=0.8, label=label)
            first = False
        else:
            ax.plot(a, e, color=colors[s_val], linewidth=0.8)

ax.axvline(x=0, color="gray", linestyle="--", linewidth=0.7, alpha=0.6)
ax.set_xlabel(r"$\alpha = J_2 / J_1$")
ax.set_ylabel(r"$E / J_1$")
ax.set_title(r"Energy Levels of a Single Pentamer ($2^5 = 32$ states)")
ax.legend(loc="upper left", framealpha=0.9)

plt.tight_layout()
plt.savefig("figures/energy_levels.pdf")
plt.savefig("figures/energy_levels.png")
print("已保存: figures/energy_levels.pdf")
