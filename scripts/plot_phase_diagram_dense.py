"""
绘制加密相图热力图（论文风格）。
输入：data/phase_diagram_dense.csv
输出：figures/phase_diagram_dense_signed.pdf/.png, figures/phase_diagram_dense.pdf/.png
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from scipy.interpolate import RectBivariateSpline
import csv
import os

# ─── 读取数据 ───
alpha_list = []
beta_list = []
data_dict = {}

with open("data/phase_diagram_dense.csv", "r") as f:
    reader = csv.DictReader(f)
    for row in reader:
        a = float(row["alpha"])
        b = float(row["beta"])
        o = float(row["O_str"])
        if a not in alpha_list:
            alpha_list.append(a)
        if b not in beta_list:
            beta_list.append(b)
        data_dict[(a, b)] = o

alpha_vals = np.array(sorted(alpha_list))
beta_vals = np.array(sorted(beta_list))

O_str = np.zeros((len(alpha_vals), len(beta_vals)))
for i, a in enumerate(alpha_vals):
    for j, b in enumerate(beta_vals):
        O_str[i, j] = data_dict.get((a, b), np.nan)

# ─── 插值 ───
n_fine = 300
alpha_fine = np.linspace(alpha_vals[0], alpha_vals[-1], n_fine)
beta_fine = np.linspace(beta_vals[0], beta_vals[-1], n_fine)

mask = ~np.isnan(O_str)
spline = RectBivariateSpline(alpha_vals, beta_vals, np.nan_to_num(O_str), kx=3, ky=3)
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

os.makedirs("figures", exist_ok=True)

# ─── 图1：带符号 ───
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
plt.savefig("figures/phase_diagram_dense_signed.pdf")
plt.savefig("figures/phase_diagram_dense_signed.png")
print("图1: figures/phase_diagram_dense_signed.pdf")

# ─── 图2：绝对值 ───
fig2, ax2 = plt.subplots(figsize=(7, 5))

O_abs = np.abs(O_fine)

im2 = ax2.imshow(
    O_abs, origin="lower", aspect="auto",
    extent=[beta_fine[0], beta_fine[-1], alpha_fine[0], alpha_fine[-1]],
    cmap="inferno", interpolation="bicubic",
    vmin=0, vmax=0.25,
)

cbar2 = fig2.colorbar(im2, ax=ax2, pad=0.02)
cbar2.set_label(r"$|O_{\mathrm{str}}^z|$", fontsize=13)

ax2.set_xlabel(r"$\beta = J_3 / J_1$")
ax2.set_ylabel(r"$\alpha = J_2 / J_1$")
ax2.set_title(r"$|O_{\mathrm{str}}^z|$ — Pentamer Chain ($N_{\mathrm{unit}}=12$)")

plt.tight_layout()
plt.savefig("figures/phase_diagram_dense.pdf")
plt.savefig("figures/phase_diagram_dense.png")
print("图2: figures/phase_diagram_dense.pdf")
