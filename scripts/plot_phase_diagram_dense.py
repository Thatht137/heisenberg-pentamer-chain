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
from matplotlib.colors import TwoSlopeNorm, LogNorm
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

# 默认显示全部数据，可选标记 α≈0 数值敏感区
SHOW_ALPHA_ZERO_BAND = os.getenv("SHOW_ALPHA_ZERO_BAND", "0") == "1"
ALPHA_ZERO_HALF_WIDTH = 0.1


def nan_aware_smooth(arr, sigma):
    """忽略缺失点进行高斯平滑。"""
    valid = np.isfinite(arr).astype(float)
    data = np.nan_to_num(arr)
    num = gaussian_filter(data, sigma=sigma, mode="nearest")
    den = gaussian_filter(valid, sigma=sigma, mode="nearest")
    return np.divide(num, den, out=np.full_like(num, np.nan), where=den > 1e-6)


# signed 图侧重整体趋势，absolute 图保留更多细节
O_smooth_signed = nan_aware_smooth(O_str, sigma=1.5)
O_smooth_abs = nan_aware_smooth(np.abs(O_str), sigma=0.8)


def mark_alpha_zero_band(ax):
    """用斜线标记数值敏感区。"""
    if SHOW_ALPHA_ZERO_BAND:
        ax.axhspan(
            -ALPHA_ZERO_HALF_WIDTH,
            ALPHA_ZERO_HALF_WIDTH,
            facecolor="white",
            edgecolor="white",
            alpha=0.18,
            hatch="///",
            linewidth=0,
            zorder=3,
        )

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

vmax = np.nanmax(np.abs(O_smooth_signed))  # 用真实最大值，signed 图重点是两相对比
norm = TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax)

im = ax.pcolormesh(
    beta_vals, alpha_vals, O_smooth_signed,
    cmap="RdBu_r", norm=norm, shading="auto", rasterized=True,
)
mark_alpha_zero_band(ax)

cbar = fig.colorbar(im, ax=ax, pad=0.02)
cbar.set_label(r"$O_{\mathrm{str}}^z$", fontsize=13)

ax.set_xlabel(r"$\beta = J_3 / J_1$")
ax.set_ylabel(r"$\alpha = J_2 / J_1$")
ax.set_title(rf"String Order Parameter — Pentamer Chain ({n_alpha}×{n_beta})")

plt.tight_layout()
plt.savefig("figures/phase_diagram_dense_signed.pdf")
plt.savefig("figures/phase_diagram_dense_signed.png")
print("图1: figures/phase_diagram_dense_signed.pdf")

# ─── 图2：绝对值（log 色标展开 ~1 个数量级的动态范围）───
fig2, ax2 = plt.subplots(figsize=(7, 5))

# 数据范围约 0.01–0.15，约一个数量级；用 log 色标让上下两区的内部结构都可见
finite = O_smooth_abs[np.isfinite(O_smooth_abs) & (O_smooth_abs > 0)]
vmin_abs = max(np.nanpercentile(finite, 2), 1e-3)
vmax_abs = np.nanpercentile(finite, 99.5)
print(f"|O_str| log 色标范围: [{vmin_abs:.4f}, {vmax_abs:.4f}]")

im2 = ax2.pcolormesh(
    beta_vals, alpha_vals, O_smooth_abs,
    cmap="inferno", shading="auto", rasterized=True,
    norm=LogNorm(vmin=vmin_abs, vmax=vmax_abs),
)
mark_alpha_zero_band(ax2)

cbar2 = fig2.colorbar(im2, ax=ax2, pad=0.02)
cbar2.set_label(r"$|O_{\mathrm{str}}^z|$", fontsize=13)

ax2.set_xlabel(r"$\beta = J_3 / J_1$")
ax2.set_ylabel(r"$\alpha = J_2 / J_1$")
ax2.set_title(rf"$|O_{{\mathrm{{str}}}}^z|$ — Pentamer Chain ({n_alpha}×{n_beta})")

plt.tight_layout()
plt.savefig("figures/phase_diagram_dense.pdf")
plt.savefig("figures/phase_diagram_dense.png")
print("图2: figures/phase_diagram_dense.pdf")

# ─── 图3：|dO_str/dα| 导数热力图（凸显 α≈±0.2 的过渡特征）───
# LSM 约束下五聚体没有 Haldane 相，O_str 本身相图无锐利结构。
# 但 dO_str/dα 在 α≈±0.2 处有尖峰（见 dOstr_dalpha.png 切片），
# 把它整张相图都画出来才能看到"边界"。
fig3, ax3 = plt.subplots(figsize=(7, 5))

# 用屏蔽感知平滑后的 signed 数据（带符号才能正确求导）
# 沿 α 方向求数值导数；屏蔽行附近的导数会因 NaN 边界不可靠，单独标记
dOda = np.full_like(O_smooth_signed, np.nan)
for j in range(n_beta):
    col = O_smooth_signed[:, j]
    valid = np.isfinite(col)
    if valid.sum() >= 3:
        # 在每个连续有效段内独立求梯度
        idx = np.where(valid)[0]
        # 找连续段
        splits = np.where(np.diff(idx) > 1)[0] + 1
        for seg in np.split(idx, splits):
            if len(seg) >= 3:
                dOda[seg, j] = np.gradient(col[seg], alpha_vals[seg])

dOda_abs = np.abs(dOda)

finite_d = dOda_abs[np.isfinite(dOda_abs) & (dOda_abs > 0)]
vmin_d = max(np.nanpercentile(finite_d, 5), 1e-3)
vmax_d = np.nanpercentile(finite_d, 99)
print(f"|dO/dα| 色标范围: [{vmin_d:.4f}, {vmax_d:.4f}]")

im3 = ax3.pcolormesh(
    beta_vals, alpha_vals, dOda_abs,
    cmap="inferno", shading="auto", rasterized=True,
    norm=LogNorm(vmin=vmin_d, vmax=vmax_d),
)
mark_alpha_zero_band(ax3)

cbar3 = fig3.colorbar(im3, ax=ax3, pad=0.02)
cbar3.set_label(r"$|dO_{\mathrm{str}}^z / d\alpha|$", fontsize=13)

ax3.set_xlabel(r"$\beta = J_3 / J_1$")
ax3.set_ylabel(r"$\alpha = J_2 / J_1$")
ax3.set_title(rf"$|dO_{{\mathrm{{str}}}}^z / d\alpha|$ — Pentamer Chain ({n_alpha}×{n_beta})")

plt.tight_layout()
plt.savefig("figures/phase_diagram_derivative.pdf")
plt.savefig("figures/phase_diagram_derivative.png")
print("图3: figures/phase_diagram_derivative.pdf")
