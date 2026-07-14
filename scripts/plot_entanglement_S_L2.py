"""
绘制链中央纠缠熵 S(L/2) vs α（多 L 叠加）。
输入：data/finite_size/finite_size_all.csv
输出：figures/S_L2_vs_alpha.pdf
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

data = {}  # (beta, L) -> [(alpha, S_L2), ...]

with open(src_file, "r") as f:
    reader = csv.DictReader(f)
    for row in reader:
        alpha = float(row["alpha"])
        beta = float(row["beta"])
        L = int(row["L"])
        S_L2 = float(row["S_L2"])

        key = (beta, L)
        if key not in data:
            data[key] = []
        data[key].append((alpha, S_L2))

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

# ─── 主图：S(L/2) vs α ───
def plot_entropy_vs_alpha(beta_target=0.5):
    fig, ax = plt.subplots(figsize=(8, 5))

    L_vals = [40, 60, 80, 100]
    colors = plt.cm.viridis(np.linspace(0.2, 0.9, len(L_vals)))

    for L, color in zip(L_vals, colors):
        key = (beta_target, L)
        if key not in data:
            continue

        pairs = data[key]
        alphas = np.array([p[0] for p in pairs])
        S_vals = np.array([p[1] for p in pairs])

        # 屏蔽 |α| ≤ 0.1
        keep = np.abs(alphas) > 0.1
        alphas = alphas[keep]
        S_vals = S_vals[keep]

        if len(alphas) < 3:
            continue

        ax.plot(alphas, S_vals, "o-", markersize=3, linewidth=1.5,
                color=color, label=f"L={L}")

    ax.set_xlabel(r"$\alpha = J_2 / J_1$")
    ax.set_ylabel(r"$S(L/2)$ (nats)")
    ax.set_title(rf"Entanglement Entropy vs $\alpha$ ($\beta={beta_target}$)")
    ax.legend(loc="best", fontsize=10)
    ax.axvline(x=0, color="gray", linestyle="--", linewidth=0.5)
    ax.grid(alpha=0.3)

    # c=1 参考线标注（α=1, β=1 时 S ≈ (1/6)log(L)）
    if beta_target == 1.0:
        c_over_6 = 1.0 / 6.0
        L_ref = np.array([40, 60, 80, 100])
        S_ref = c_over_6 * np.log(L_ref)
        ax.plot([1.0]*len(L_ref), S_ref, "x", markersize=8, color="red",
                label="c=1 reference")

    plt.tight_layout()
    plt.savefig(f"figures/S_L2_vs_alpha_b{beta_target:.1f}.pdf")
    plt.savefig(f"figures/S_L2_vs_alpha_b{beta_target:.1f}.png")
    print(f"已保存: figures/S_L2_vs_alpha_b{beta_target:.1f}.pdf")
    plt.close()

# ─── 执行 ───
plot_entropy_vs_alpha(beta_target=0.5)

# 如果有 β=1.0 数据也绘制
if any(key[0] == 1.0 for key in data.keys()):
    plot_entropy_vs_alpha(beta_target=1.0)

print("\n完成。")
