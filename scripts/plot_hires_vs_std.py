"""一次性对比 std 80x60 vs hires 80x60 在 α∈{-1.0, -0.5, 1.0} 上的切片。
判断 hires (maxdim=1000) 是否比 std (maxdim=400) 平滑。
"""
import csv
from collections import defaultdict
import matplotlib.pyplot as plt
import numpy as np

ALPHAS = [-1.0, -0.5, 1.0]

def load(path):
    """返回 {alpha: [(beta, O_str), ...]} 按 beta 排序。"""
    by_a = defaultdict(list)
    with open(path) as f:
        r = csv.DictReader(f)
        for row in r:
            a = float(row["alpha"])
            b = float(row["beta"])
            o = float(row["O_str"])
            by_a[round(a, 4)].append((b, o))
    for a in by_a:
        by_a[a].sort()
    return by_a

std = load("data/phase_diagram_80x60.csv")
hi = load("data/phase_diagram_80x60_hires.csv")

fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), sharey=False)
for ax, a_target in zip(axes, ALPHAS):
    # 找到最接近的 α
    a_std = min(std.keys(), key=lambda x: abs(x - a_target))
    a_hi = min(hi.keys(), key=lambda x: abs(x - a_target))

    bs, os_ = zip(*std[a_std])
    ax.plot(bs, os_, "o-", markersize=3, lw=1.0, color="tab:blue",
            label=f"std (maxdim=400), α={a_std:.2f}")

    bs, os_ = zip(*hi[a_hi])
    ax.plot(bs, os_, "s-", markersize=3, lw=1.0, color="tab:red",
            label=f"hires (maxdim=1000), α={a_hi:.2f}")

    ax.set_xlabel(r"$\beta = J_3/J_1$")
    ax.set_ylabel(r"$O_{\rm str}$")
    ax.set_title(rf"$\alpha = {a_target:.1f}$")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)

plt.tight_layout()
plt.savefig("figures/hires_vs_std_compare.png", dpi=200)
plt.savefig("figures/hires_vs_std_compare.pdf")
print("写入 figures/hires_vs_std_compare.{png,pdf}")
