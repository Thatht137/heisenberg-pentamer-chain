"""
绘制五聚体链弦序参量相图（论文风格，插值平滑版）。
输入：data/phase_diagram.csv
输出：figures/phase_diagram_smooth.pdf/.png, figures/phase_diagram_smooth_signed.pdf/.png
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from scipy.interpolate import RectBivariateSpline
import csv

# ─── 读取 CSV 数据 ───
alpha_vals = []
beta_vals = []
data_dict = {}

with open("data/phase_diagram.csv", "r") as f:
    reader = csv.DictReader(f)
    for row in reader:
        a = float(row["alpha (J2/J1)"])
        b = float(row["beta (J3/J1)"])
        o = float(row["O_string"])
        if a not in alpha_vals:
            alpha_vals.append(a)
        if b not in beta_vals:
            beta_vals.append(b)
        data_dict[(a, b)] = o

alpha_vals = np.array(sorted(alpha_vals))
beta_vals = np.array(sorted(beta_vals))

O_str = np.zeros((len(beta_vals), len(alpha_vals)))
for i, b in enumerate(beta_vals):
    for j, a in enumerate(alpha_vals):
        O_str[i, j] = data_dict[(a, b)]

# ─── 插值到细网格 ───
# 注意：横轴 beta，纵轴 alpha（与文献一致）
# O_str 原始形状为 [len(beta), len(alpha)]，转置为 [len(alpha), len(beta)]
n_fine = 200
alpha_fine = np.linspace(alpha_vals[0], alpha_vals[-1], n_fine)
beta_fine = np.linspace(beta_vals[0], beta_vals[-1], n_fine)

spline = RectBivariateSpline(alpha_vals, beta_vals, O_str.T, kx=3, ky=3)
O_fine = spline(alpha_fine, beta_fine)

# ─── 绘图样式 ───
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

import os
os.makedirs("figures", exist_ok=True)

# ─── 图1：带符号（发散色图） ───
fig, ax = plt.subplots(figsize=(7, 5))

vmax = np.max(np.abs(O_fine))
norm = TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax)

im = ax.imshow(
    O_fine, origin="lower", aspect="auto",
    extent=[beta_fine[0], beta_fine[-1], alpha_fine[0], alpha_fine[-1]],
    cmap="RdBu_r", norm=norm, interpolation="bicubic",
)

cbar = fig.colorbar(im, ax=ax, pad=0.02)
cbar.set_label(r"$O_{\mathrm{str}}^z$", fontsize=13)

ax.set_xlabel(r"$\beta = J_3 / J_1$")
ax.set_ylabel(r"$\alpha = J_2 / J_1$")
ax.set_title(r"String Order Parameter — Pentamer Chain ($N_{\mathrm{unit}}=12$)")

plt.tight_layout()
plt.savefig("figures/phase_diagram_smooth_signed.pdf")
plt.savefig("figures/phase_diagram_smooth_signed.png")
print("图1已保存: figures/phase_diagram_smooth_signed.pdf")

# ─── 图2：绝对值（适合看相边界） ───
fig2, ax2 = plt.subplots(figsize=(7, 5))

O_abs_fine = np.abs(O_fine)

im2 = ax2.imshow(
    O_abs_fine, origin="lower", aspect="auto",
    extent=[beta_fine[0], beta_fine[-1], alpha_fine[0], alpha_fine[-1]],
    cmap="inferno", interpolation="bicubic",
    vmin=0, vmax=0.25,
)

cbar2 = fig2.colorbar(im2, ax=ax2, pad=0.02)
cbar2.set_label(r"$|O_{\mathrm{str}}^z|$", fontsize=13)

ax2.set_xlabel(r"$\beta = J_3 / J_1$")
ax2.set_ylabel(r"$\alpha = J_2 / J_1$")
ax2.set_title(r"$|O_{\mathrm{str}}^z|$ Phase Diagram — Pentamer Chain ($N_{\mathrm{unit}}=12$)")

plt.tight_layout()
plt.savefig("figures/phase_diagram_smooth.pdf")
plt.savefig("figures/phase_diagram_smooth.png")
print("图2已保存: figures/phase_diagram_smooth.pdf")

print("\n完成。")
