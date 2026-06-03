"""
绘制五聚体链弦序参量相图（论文风格）。
输入：data/phase_diagram.jld2
输出：figures/phase_diagram.pdf, data/phase_diagram.csv
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import csv
import sys

# ─── 读取 JLD2 数据（通过 Julia 导出的 CSV 中转） ───
# 直接硬编码从 Julia 读出的数据

alpha_vals = np.array([-1.0, -0.8, -0.6, -0.4, -0.2, 0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
beta_vals = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])

# O_str[i_beta, i_alpha]
data_raw = [
    # beta=0.1
    [0.06935, 0.05572, 0.06135, 0.08379, 0.08130, 0.25000, 0.03367, 0.02572, 0.02034, 0.01499, 0.01119],
    # beta=0.2
    [0.09605, 0.11137, 0.05933, 0.13100, 0.03144, 0.25000, 0.04569, 0.03172, 0.02531, 0.02056, 0.01651],
    # beta=0.3
    [0.10041, 0.11140, 0.12788, 0.11132, 0.13974, 0.25000, 0.05411, 0.03759, 0.02914, 0.02344, 0.01877],
    # beta=0.4
    [0.11549, 0.12524, 0.13342, 0.14299, 0.11478, 0.25000, 0.05840, 0.04322, 0.03292, 0.02628, 0.02105],
    # beta=0.5
    [0.12156, 0.12714, 0.14008, 0.11919, 0.09269, -0.25000, 0.05490, 0.04811, 0.03670, 0.02909, 0.02333],
    # beta=0.6
    [0.12963, 0.13257, 0.13706, 0.15304, 0.19830, 0.25000, 0.06117, 0.05200, 0.04037, 0.03190, 0.02560],
    # beta=0.7
    [0.12717, 0.13052, 0.06910, 0.07790, 0.05506, -0.25000, 0.05761, 0.05494, 0.04381, 0.03469, 0.02786],
    # beta=0.8
    [0.13326, 0.13934, 0.11696, 0.04605, 0.11376, 0.24992, 0.02818, 0.05711, 0.04690, 0.03743, 0.03010],
    # beta=0.9
    [0.13610, 0.14200, 0.16322, 0.16764, 0.16476, 0.24996, 0.11405, 0.05873, 0.04958, 0.04008, 0.03233],
    # beta=1.0
    [0.13670, 0.13846, 0.12638, 0.11480, -0.13469, -0.25000, 0.08580, 0.05992, 0.05185, 0.04258, 0.03454],
]

O_str = np.array(data_raw)

# ─── 导出 CSV 数据表 ───
import os
os.makedirs("data", exist_ok=True)
os.makedirs("figures", exist_ok=True)

with open("data/phase_diagram.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["alpha (J2/J1)", "beta (J3/J1)", "O_string"])
    for i, beta in enumerate(beta_vals):
        for j, alpha in enumerate(alpha_vals):
            writer.writerow([f"{alpha:.2f}", f"{beta:.2f}", f"{O_str[i, j]:.6f}"])

print("CSV 已保存: data/phase_diagram.csv")

# ─── 绘制热力图（论文风格） ───
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

# ─── 图1：带符号的弦序参量（发散色图） ───
fig, ax = plt.subplots(figsize=(7, 5))

vmax = np.max(np.abs(O_str))
norm = TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax)

im = ax.pcolormesh(
    alpha_vals, beta_vals, O_str,
    cmap="RdBu_r",
    norm=norm,
    shading="nearest",
)

cbar = fig.colorbar(im, ax=ax, pad=0.02)
cbar.set_label(r"$O_{\mathrm{str}}$", fontsize=13)

ax.set_xlabel(r"$\alpha = J_2 / J_1$")
ax.set_ylabel(r"$\beta = J_3 / J_1$")
ax.set_title(r"String Order Parameter — Pentamer Chain ($N_{\mathrm{unit}}=12$)")
ax.axvline(x=0, color="k", linestyle="--", linewidth=0.8, alpha=0.5)
ax.set_xticks(alpha_vals)
ax.set_yticks(beta_vals)

plt.tight_layout()
plt.savefig("figures/phase_diagram_signed.pdf")
plt.savefig("figures/phase_diagram_signed.png")
print("图1已保存: figures/phase_diagram_signed.pdf")

# ─── 图2：|O_str|（绝对值，适合看相边界） ───
fig2, ax2 = plt.subplots(figsize=(7, 5))

O_abs = np.abs(O_str)

im2 = ax2.pcolormesh(
    alpha_vals, beta_vals, O_abs,
    cmap="inferno",
    shading="nearest",
    vmin=0, vmax=0.25,
)

cbar2 = fig2.colorbar(im2, ax=ax2, pad=0.02)
cbar2.set_label(r"$|O_{\mathrm{str}}|$", fontsize=13)

ax2.set_xlabel(r"$\alpha = J_2 / J_1$")
ax2.set_ylabel(r"$\beta = J_3 / J_1$")
ax2.set_title(r"$|O_{\mathrm{str}}|$ Phase Diagram — Pentamer Chain ($N_{\mathrm{unit}}=12$)")
ax2.axvline(x=0, color="w", linestyle="--", linewidth=0.8, alpha=0.7)
ax2.set_xticks(alpha_vals)
ax2.set_yticks(beta_vals)

plt.tight_layout()
plt.savefig("figures/phase_diagram.pdf")
plt.savefig("figures/phase_diagram.png")
print("图2已保存: figures/phase_diagram.pdf")
plt.show()
