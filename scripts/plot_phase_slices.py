"""
绘制弦序参量 1D 切片和数值导数（对应文献 Fig. 3b/c/d）。
输入：data/phase_diagram_dense.csv（优先）或 data/phase_diagram.csv（fallback）
输出：figures/Ostr_vs_beta.pdf, figures/Ostr_vs_alpha.pdf, figures/dOstr_dalpha.pdf
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import savgol_filter
import csv
import os

# ─── 读取数据 ───
dense_file = "data/phase_diagram_dense.csv"
fallback_file = "data/phase_diagram.csv"

if os.path.exists(dense_file):
    src_file = dense_file
    col_alpha, col_beta, col_ostr = "alpha", "beta", "O_str"
else:
    src_file = fallback_file
    col_alpha, col_beta, col_ostr = "alpha (J2/J1)", "beta (J3/J1)", "O_string"

print(f"读取: {src_file}")

alpha_list = []
beta_list = []
data_dict = {}

with open(src_file, "r") as f:
    reader = csv.DictReader(f)
    for row in reader:
        a = float(row[col_alpha])
        b = float(row[col_beta])
        o = float(row[col_ostr])
        if a not in alpha_list:
            alpha_list.append(a)
        if b not in beta_list:
            beta_list.append(b)
        data_dict[(a, b)] = o

alpha_vals = np.array(sorted(alpha_list))
beta_vals = np.array(sorted(beta_list))

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

# ─── 图1: O_str vs beta（固定 alpha）─── Fig. 3b
fig1, ax1 = plt.subplots(figsize=(7, 5))

alpha_select = [-1.0, -0.5, 0.1, 0.5, 1.0]
for a_target in alpha_select:
    a = min(alpha_vals, key=lambda x: abs(x - a_target))
    betas = []
    ostrs = []
    for b in beta_vals:
        if (a, b) in data_dict:
            betas.append(b)
            ostrs.append(data_dict[(a, b)])
    if betas:
        ax1.plot(betas, ostrs, "o-", markersize=3,
                 label=rf"$\alpha={a:.2f}$")

ax1.set_xlabel(r"$\beta = J_3 / J_1$")
ax1.set_ylabel(r"$O_{\mathrm{str}}^z$")
ax1.set_title(r"String Order vs $\beta$ (fixed $\alpha$)")
ax1.legend(loc="best", fontsize=10)
ax1.axhline(y=0, color="gray", linestyle="--", linewidth=0.5)

plt.tight_layout()
plt.savefig("figures/Ostr_vs_beta.pdf")
plt.savefig("figures/Ostr_vs_beta.png")
print("图1: figures/Ostr_vs_beta.pdf")
plt.close()

# ─── 图2: O_str vs alpha（固定 beta）─── Fig. 3c
fig2, ax2 = plt.subplots(figsize=(7, 5))

beta_select = [0.1, 0.5, 1.0]
for b_target in beta_select:
    b = min(beta_vals, key=lambda x: abs(x - b_target))
    alphas = []
    ostrs = []
    for a in alpha_vals:
        if (a, b) in data_dict:
            alphas.append(a)
            ostrs.append(data_dict[(a, b)])
    if alphas:
        ax2.plot(alphas, ostrs, "o-", markersize=3,
                 label=rf"$\beta={b:.2f}$")

ax2.set_xlabel(r"$\alpha = J_2 / J_1$")
ax2.set_ylabel(r"$O_{\mathrm{str}}^z$")
ax2.set_title(r"String Order vs $\alpha$ (fixed $\beta$)")
ax2.legend(loc="best", fontsize=10)
ax2.axhline(y=0, color="gray", linestyle="--", linewidth=0.5)
ax2.axvline(x=0, color="gray", linestyle="--", linewidth=0.5)

plt.tight_layout()
plt.savefig("figures/Ostr_vs_alpha.pdf")
plt.savefig("figures/Ostr_vs_alpha.png")
print("图2: figures/Ostr_vs_alpha.pdf")
plt.close()

# ─── 图3: dO_str/d(alpha)（固定 beta）─── Fig. 3d
fig3, ax3 = plt.subplots(figsize=(7, 5))

for b_target in beta_select:
    b = min(beta_vals, key=lambda x: abs(x - b_target))
    alphas = []
    ostrs = []
    for a in alpha_vals:
        if (a, b) in data_dict:
            alphas.append(a)
            ostrs.append(data_dict[(a, b)])

    if len(alphas) < 5:
        continue

    alphas = np.array(alphas)
    ostrs = np.array(ostrs)

    # Savitzky-Golay 平滑后求导（窗口取奇数，不超过数据长度）
    win = min(7, len(ostrs) - 1)
    if win % 2 == 0:
        win -= 1
    if win >= 3:
        ostrs_smooth = savgol_filter(ostrs, win, 2)
        deriv = np.gradient(ostrs_smooth, alphas)
    else:
        deriv = np.gradient(ostrs, alphas)

    ax3.plot(alphas, deriv, "-", linewidth=1.5,
             label=rf"$\beta={b:.2f}$")

ax3.set_xlabel(r"$\alpha = J_2 / J_1$")
ax3.set_ylabel(r"$dO_{\mathrm{str}}^z / d\alpha$")
ax3.set_title(r"Derivative of String Order Parameter")
ax3.legend(loc="best", fontsize=10)
ax3.axhline(y=0, color="gray", linestyle="--", linewidth=0.5)
ax3.axvline(x=0, color="gray", linestyle="--", linewidth=0.5)

plt.tight_layout()
plt.savefig("figures/dOstr_dalpha.pdf")
plt.savefig("figures/dOstr_dalpha.png")
print("图3: figures/dOstr_dalpha.pdf")
plt.close()

print("\n完成。")
