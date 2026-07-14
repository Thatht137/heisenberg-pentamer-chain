"""
绘制 S(L/2) vs log(L) 标度图（中心荷拟合）。
输入：data/finite_size/finite_size_all.csv
输出：figures/S_L2_vs_logL.pdf
"""

import numpy as np
import matplotlib.pyplot as plt
import csv
import os

# ─── 读取数据 ───
src_file = "data/finite_size/finite_size_all.csv"
if not os.path.exists(src_file):
    raise FileNotFoundError(f"找不到数据文件: {src_file}")

print(f"读取: {src_file}")

data = {}  # (beta, alpha) -> [(L, S_L2), ...]

with open(src_file, "r") as f:
    reader = csv.DictReader(f)
    for row in reader:
        alpha = float(row["alpha"])
        beta = float(row["beta"])
        L = int(row["L"])
        S_L2 = float(row["S_L2"])

        key = (beta, alpha)
        if key not in data:
            data[key] = []
        data[key].append((L, S_L2))

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

# ─── 主图：S vs log(L)，多个 α 面板 ───
def plot_entropy_scaling(beta_target=0.5, alpha_vals=[0.25, 1.0, -0.25]):
    fig, axes = plt.subplots(1, len(alpha_vals), figsize=(14, 4.5), sharey=True)

    if len(alpha_vals) == 1:
        axes = [axes]

    for ax, alpha_target in zip(axes, alpha_vals):
        # 找最接近的 alpha
        available = [k for k in data.keys() if k[0] == beta_target]
        if not available:
            continue

        alphas_in_data = [k[1] for k in available]
        alpha_actual = min(alphas_in_data, key=lambda a: abs(a - alpha_target))

        key = (beta_target, alpha_actual)
        if key not in data or len(data[key]) < 3:
            continue

        pairs = data[key]
        L_vals = np.array([p[0] for p in pairs])
        S_vals = np.array([p[1] for p in pairs])

        log_L = np.log(L_vals)

        ax.plot(log_L, S_vals, "o", markersize=8, label="Data")

        # 线性拟合 S = (c/6) * log(L) + const
        coef = np.polyfit(log_L, S_vals, 1)
        fit_line = np.poly1d(coef)
        log_L_fit = np.linspace(log_L.min(), log_L.max(), 100)
        ax.plot(log_L_fit, fit_line(log_L_fit), "--", color="red",
                label=f"Fit: slope={coef[0]:.4f}")

        c_est = coef[0] * 6.0
        ax.text(0.05, 0.95, f"c ≈ {c_est:.3f}",
                transform=ax.transAxes, ha="left", va="top",
                fontsize=11, bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5))

        ax.set_xlabel(r"$\ln(L)$")
        if ax == axes[0]:
            ax.set_ylabel(r"$S(L/2)$ (nats)")
        ax.set_title(rf"$\alpha={alpha_actual:.2f}$")
        ax.legend(loc="lower right", fontsize=9)
        ax.grid(alpha=0.3)

    fig.suptitle(rf"Entanglement Entropy Scaling ($\beta={beta_target}$)", fontsize=14)
    plt.tight_layout()
    plt.savefig(f"figures/S_L2_vs_logL_b{beta_target:.1f}.pdf")
    plt.savefig(f"figures/S_L2_vs_logL_b{beta_target:.1f}.png")
    print(f"已保存: figures/S_L2_vs_logL_b{beta_target:.1f}.pdf")
    plt.close()

# ─── 执行 ───
plot_entropy_scaling(beta_target=0.5, alpha_vals=[0.25, 1.0, -0.25])

# 如果有 β=1.0 数据也绘制
if any(key[0] == 1.0 for key in data.keys()):
    plot_entropy_scaling(beta_target=1.0, alpha_vals=[0.25, 1.0, -0.25])

print("\n完成。")
