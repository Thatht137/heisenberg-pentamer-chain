"""
绘制加密相图热力图（论文风格）。
优先读取 data/phase_diagram_80x60.csv（新加密数据），fallback 到 data/phase_diagram_dense.csv。
输出：figures/phase_diagram_dense_signed.pdf/.png, figures/phase_diagram_dense.pdf/.png

绘图策略：
- 直接 pcolormesh 显示原始网格，不做插值（避免样条伪影）
- signed 图用对称色标，absolute 图用 inferno
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from scipy.ndimage import gaussian_filter
import csv
import os

# ─── 选择数据源（优先 80x60）───
candidates = [
    "data/phase_diagram_80x60_hires.csv",
    "data/phase_diagram_80x60.csv",
    "data/phase_diagram_dense.csv",
]
src_file = next((p for p in candidates if os.path.exists(p)), None)
if src_file is None:
    raise FileNotFoundError(f"找不到相图数据：{candidates}")
print(f"读取: {src_file}")

# ─── 读取数据 ───
alpha_list = []
beta_list = []
data_dict = {}

with open(src_file, "r") as f:
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

n_alpha, n_beta = len(alpha_vals), len(beta_vals)
print(f"网格: {n_alpha} × {n_beta} = {n_alpha * n_beta} 点")

# ─── 高斯平滑去噪（不做插值放大）───
# sigma 用网格点单位。signed 用更大的 sigma 抑制 α≈0 退化点的符号翻转噪声；
# absolute 用较小 sigma 保留细节。
O_smooth_signed = gaussian_filter(np.nan_to_num(O_str), sigma=1.5, mode="nearest")
O_smooth_abs = gaussian_filter(np.abs(np.nan_to_num(O_str)), sigma=0.8, mode="nearest")

# ─── 屏蔽 α≈0 退化带 ───
# 五聚体在 α=0 时局部 8 重简并（trimer S=1/2 × 2 free spins），
# DMRG 随机收敛导致 O_str 符号和大小都不稳定。物理上是真实的退化，绘图中屏蔽掉。
ALPHA_MASK_HALF_WIDTH = 0.1
mask_alpha = np.abs(alpha_vals) <= ALPHA_MASK_HALF_WIDTH
O_smooth_signed[mask_alpha, :] = np.nan
O_smooth_abs[mask_alpha, :] = np.nan
print(f"屏蔽 α∈[-{ALPHA_MASK_HALF_WIDTH}, {ALPHA_MASK_HALF_WIDTH}] 的退化带（{mask_alpha.sum()} 个 α 点）")

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

vmax = np.percentile(np.abs(O_smooth_signed), 95)  # 95 分位避免极端噪声拉爆色标
norm = TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax)

im = ax.pcolormesh(
    beta_vals, alpha_vals, O_smooth_signed,
    cmap="RdBu_r", norm=norm, shading="auto", rasterized=True,
)

cbar = fig.colorbar(im, ax=ax, pad=0.02)
cbar.set_label(r"$O_{\mathrm{str}}^z$", fontsize=13)

ax.set_xlabel(r"$\beta = J_3 / J_1$")
ax.set_ylabel(r"$\alpha = J_2 / J_1$")
ax.set_title(rf"String Order Parameter — Pentamer Chain ({n_alpha}×{n_beta})")

plt.tight_layout()
plt.savefig("figures/phase_diagram_dense_signed.pdf")
plt.savefig("figures/phase_diagram_dense_signed.png")
print("图1: figures/phase_diagram_dense_signed.pdf")

# ─── 图2：绝对值 ───
fig2, ax2 = plt.subplots(figsize=(7, 5))

vmax_abs = np.percentile(O_smooth_abs, 95)

im2 = ax2.pcolormesh(
    beta_vals, alpha_vals, O_smooth_abs,
    cmap="inferno", shading="auto", rasterized=True,
    vmin=0, vmax=vmax_abs,
)

cbar2 = fig2.colorbar(im2, ax=ax2, pad=0.02)
cbar2.set_label(r"$|O_{\mathrm{str}}^z|$", fontsize=13)

ax2.set_xlabel(r"$\beta = J_3 / J_1$")
ax2.set_ylabel(r"$\alpha = J_2 / J_1$")
ax2.set_title(rf"$|O_{{\mathrm{{str}}}}^z|$ — Pentamer Chain ({n_alpha}×{n_beta})")

plt.tight_layout()
plt.savefig("figures/phase_diagram_dense.pdf")
plt.savefig("figures/phase_diagram_dense.png")
print("图2: figures/phase_diagram_dense.pdf")
