"""
绘制沿链纠缠熵分布（参考文献 Fig. style）。
主图：S(bond) vs bond，多条 L 曲线
插图：S vs c*log(L)/c 标度坍缩（可选）

输入：data/entanglement_profiles/profile_*.csv
输出：figures/entanglement_profile.pdf
"""

import numpy as np
import matplotlib.pyplot as plt
import csv
import os
import glob

# ─── 读取数据 ───
data_dir = "data/entanglement_profiles"
if not os.path.exists(data_dir):
    print(f"错误：目录 {data_dir} 不存在")
    print("请先运行 08_entanglement_profile.jl 计算纠缠熵分布")
    exit(1)

files = glob.glob(os.path.join(data_dir, "profile_*.csv"))
if not files:
    print(f"错误：{data_dir} 中没有 profile_*.csv 文件")
    exit(1)

print(f"找到 {len(files)} 个纠缠熵分布文件")

# 解析文件名：profile_a<alpha>_b<beta>_L<L>.csv
data = {}  # (alpha, beta, L) -> [(bond, S), ...]

for fpath in files:
    fname = os.path.basename(fpath)
    # 示例：profile_a0.2500_b0.5000_L060.csv
    parts = fname.replace("profile_a", "").replace(".csv", "").split("_b")
    alpha = float(parts[0])
    beta_L = parts[1].split("_L")
    beta = float(beta_L[0])
    L = int(beta_L[1])

    bond_S = []
    with open(fpath, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            bond_S.append((int(row['bond']), float(row['S'])))

    data[(alpha, beta, L)] = bond_S
    print(f"  读取: α={alpha:.4f}, β={beta:.2f}, L={L}")

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

# ─── 主图：S(bond) vs bond ───
def plot_entanglement_profile(alpha_target=0.25, beta_target=0.5):
    fig, ax = plt.subplots(figsize=(8, 5))

    # 筛选出匹配的 (α, β)
    keys = [k for k in data.keys() if abs(k[0] - alpha_target) < 0.01 and abs(k[1] - beta_target) < 0.01]

    if not keys:
        print(f"警告：没有找到 α≈{alpha_target}, β≈{beta_target} 的数据")
        return

    # 按 L 排序
    keys.sort(key=lambda k: k[2])

    colors = plt.cm.viridis(np.linspace(0.2, 0.9, len(keys)))

    for (alpha, beta, L), color in zip(keys, colors):
        bond_S = data[(alpha, beta, L)]
        bonds = np.array([b for b, s in bond_S])
        S_vals = np.array([s for b, s in bond_S])

        # 归一化 bond 位置（相对坐标 i/L）
        bonds_norm = bonds / L

        ax.plot(bonds, S_vals, 'o-', markersize=3, linewidth=1.5,
                color=color, label=f"L={L}")

    ax.set_xlabel(r"Bond position $i$")
    ax.set_ylabel(r"$S(i)$ (nats)")
    ax.set_title(rf"Entanglement Entropy Profile ($\alpha={alpha_target:.2f}, \beta={beta_target:.1f}$)")
    ax.legend(loc="upper right", fontsize=10)
    ax.grid(alpha=0.3)

    # 可选：添加标度坍缩插图（需要理论指导）
    # inset = ax.inset_axes([0.15, 0.5, 0.4, 0.35])
    # ... 标度坍缩代码 ...

    plt.tight_layout()
    outname = f"figures/entanglement_profile_a{alpha_target:.2f}_b{beta_target:.1f}.pdf"
    plt.savefig(outname)
    plt.savefig(outname.replace('.pdf', '.png'))
    print(f"已保存: {outname}")
    plt.close()

# ─── 执行：画几组代表性参数 ───

# 提取所有不同的 (α, β) 组合
param_sets = set((k[0], k[1]) for k in data.keys())

for alpha, beta in sorted(param_sets):
    plot_entanglement_profile(alpha, beta)

print("\n完成。")
