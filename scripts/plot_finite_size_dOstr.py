"""
绘制 dO_str/dα vs α 的有限尺寸标度（对应文献 Fig. 3d 扩展版）。
输入：data/finite_size/finite_size_all.csv
输出：figures/dOstr_dalpha_vs_L.pdf, figures/peak_alpha_vs_invL.pdf
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import savgol_filter
import csv
import os

def compute_derivative(alphas, ostrs):
    """计算 dO/dα，对密集区平滑，疏区直接求导。"""
    deriv = np.zeros_like(alphas)

    # 分正负两侧处理
    for sign in [-1, 1]:
        if sign == 1:
            mask = (alphas > 0.1) & (alphas < 0.4)
        else:
            mask = (alphas < -0.1) & (alphas > -0.4)

        if not np.any(mask):
            continue

        idx = np.where(mask)[0]
        a_sub = alphas[idx]
        o_sub = ostrs[idx]

        # 密集区 (0.15-0.35) 用 Savitzky-Golay 平滑
        dense_mask = (np.abs(a_sub) >= 0.15) & (np.abs(a_sub) <= 0.35)
        if np.sum(dense_mask) > 10:
            win = min(11, np.sum(dense_mask) - 1)
            if win >= 5 and win % 2 == 1:
                o_smooth = savgol_filter(o_sub, win, 3)
                deriv[idx] = np.gradient(o_smooth, a_sub)
            else:
                deriv[idx] = np.gradient(o_sub, a_sub)
        else:
            deriv[idx] = np.gradient(o_sub, a_sub)

    return deriv

# ─── 读取数据 ───
src_file = "data/finite_size/finite_size_all.csv"
if not os.path.exists(src_file):
    raise FileNotFoundError(f"找不到数据文件: {src_file}")

print(f"读取: {src_file}")

data = {}  # (beta, L) -> [(alpha, O_str), ...]

with open(src_file, "r") as f:
    reader = csv.DictReader(f)
    for row in reader:
        alpha = float(row["alpha"])
        beta = float(row["beta"])
        L = int(row["L"])
        O_str = float(row["O_str"])

        key = (beta, L)
        if key not in data:
            data[key] = []
        data[key].append((alpha, O_str))

# 排序
for key in data:
    data[key].sort()

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

# ─── 主图：dO/dα vs α（多 L 叠加）───
def plot_derivative_vs_L(beta_target=0.5):
    fig, ax = plt.subplots(figsize=(8, 5))

    L_vals = [40, 60, 80, 100]
    colors = plt.cm.viridis(np.linspace(0.2, 0.9, len(L_vals)))

    for L, color in zip(L_vals, colors):
        key = (beta_target, L)
        if key not in data:
            continue

        pairs = data[key]
        alphas = np.array([p[0] for p in pairs])
        ostrs = np.array([p[1] for p in pairs])

        # 屏蔽 |α| ≤ 0.1
        keep = np.abs(alphas) > 0.1
        alphas = alphas[keep]
        ostrs = ostrs[keep]

        if len(alphas) < 5:
            continue

        deriv = compute_derivative(alphas, ostrs)

        ax.plot(alphas, deriv, "-", linewidth=2, color=color,
                label=f"L={L}")

    ax.set_xlabel(r"$\alpha = J_2 / J_1$")
    ax.set_ylabel(r"$dO_{\mathrm{str}}^z / d\alpha$")
    ax.set_title(rf"Derivative of String Order vs System Size ($\beta={beta_target}$)")
    ax.legend(loc="best", fontsize=10)
    ax.axhline(y=0, color="gray", linestyle="--", linewidth=0.5)
    ax.axvline(x=0, color="gray", linestyle="--", linewidth=0.5)
    ax.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig("figures/dOstr_dalpha_vs_L.pdf")
    plt.savefig("figures/dOstr_dalpha_vs_L.png")
    print("已保存: figures/dOstr_dalpha_vs_L.pdf")
    plt.close()

# ─── FSS 外推：α* vs 1/L ───
def plot_peak_vs_invL(beta_target=0.5):
    L_vals = [40, 60, 80, 100]

    peak_alpha_pos = []
    peak_alpha_neg = []
    invL = []

    for L in L_vals:
        key = (beta_target, L)
        if key not in data:
            continue

        pairs = data[key]
        alphas = np.array([p[0] for p in pairs])
        ostrs = np.array([p[1] for p in pairs])

        keep = np.abs(alphas) > 0.1
        alphas = alphas[keep]
        ostrs = ostrs[keep]

        if len(alphas) < 5:
            continue

        deriv = compute_derivative(alphas, ostrs)

        # 正侧峰
        pos_mask = (alphas > 0.1) & (alphas < 0.4)
        if np.any(pos_mask):
            idx_max = np.argmax(np.abs(deriv[pos_mask]))
            alpha_peak_pos = alphas[pos_mask][idx_max]
            peak_alpha_pos.append(alpha_peak_pos)
        else:
            peak_alpha_pos.append(np.nan)

        # 负侧峰
        neg_mask = (alphas < -0.1) & (alphas > -0.4)
        if np.any(neg_mask):
            idx_max = np.argmax(np.abs(deriv[neg_mask]))
            alpha_peak_neg = alphas[neg_mask][idx_max]
            peak_alpha_neg.append(alpha_peak_neg)
        else:
            peak_alpha_neg.append(np.nan)

        invL.append(1.0 / L)

    invL = np.array(invL)
    peak_alpha_pos = np.array(peak_alpha_pos)
    peak_alpha_neg = np.array(peak_alpha_neg)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # 正侧
    valid = ~np.isnan(peak_alpha_pos)
    if np.sum(valid) >= 2:
        ax1.plot(invL[valid], peak_alpha_pos[valid], "o-", markersize=8, label="Data")
        coef = np.polyfit(invL[valid], peak_alpha_pos[valid], 1)
        fit_line = np.poly1d(coef)
        invL_fit = np.linspace(0, np.max(invL[valid]), 100)
        ax1.plot(invL_fit, fit_line(invL_fit), "--", color="red",
                 label=f"Fit: α*={coef[1]:.4f} + {coef[0]:.2f}/L")
        ax1.axhline(y=coef[1], color="gray", linestyle=":", linewidth=1)
        ax1.text(0.95, 0.05, f"α*(L→∞) ≈ {coef[1]:.4f}",
                 transform=ax1.transAxes, ha="right", va="bottom",
                 fontsize=10, bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5))

    ax1.set_xlabel(r"$1/L$")
    ax1.set_ylabel(r"$\alpha^*_+$ (peak of $|dO/d\alpha|$)")
    ax1.set_title(r"FSS: Positive $\alpha$ Side")
    ax1.legend(loc="best")
    ax1.grid(alpha=0.3)

    # 负侧
    valid = ~np.isnan(peak_alpha_neg)
    if np.sum(valid) >= 2:
        ax2.plot(invL[valid], peak_alpha_neg[valid], "o-", markersize=8, label="Data")
        coef = np.polyfit(invL[valid], peak_alpha_neg[valid], 1)
        fit_line = np.poly1d(coef)
        invL_fit = np.linspace(0, np.max(invL[valid]), 100)
        ax2.plot(invL_fit, fit_line(invL_fit), "--", color="red",
                 label=f"Fit: α*={coef[1]:.4f} + {coef[0]:.2f}/L")
        ax2.axhline(y=coef[1], color="gray", linestyle=":", linewidth=1)
        ax2.text(0.95, 0.95, f"α*(L→∞) ≈ {coef[1]:.4f}",
                 transform=ax2.transAxes, ha="right", va="top",
                 fontsize=10, bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5))

    ax2.set_xlabel(r"$1/L$")
    ax2.set_ylabel(r"$\alpha^*_-$ (peak of $|dO/d\alpha|$)")
    ax2.set_title(r"FSS: Negative $\alpha$ Side")
    ax2.legend(loc="best")
    ax2.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig("figures/peak_alpha_vs_invL.pdf")
    plt.savefig("figures/peak_alpha_vs_invL.png")
    print("已保存: figures/peak_alpha_vs_invL.pdf")
    plt.close()

# ─── 执行 ───
plot_derivative_vs_L(beta_target=0.5)
plot_peak_vs_invL(beta_target=0.5)

print("\n完成。")
