"""比较色标设置，保持谱网格不变。"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize, PowerNorm

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 10,
    "figure.dpi": 300,
})

ALPHAS = [1.0, -1.0]
BETAS = [1.0, 0.7, 0.5, 0.4, 0.1]

CONFIGS = [
    ("A: linear, vmax=2.0, inferno", dict(vmax=2.0, cmap="inferno", norm=None)),
    ("B: linear, vmax=1.5, inferno", dict(vmax=1.5, cmap="inferno", norm=None)),
    ("C: PowerNorm(0.5), vmax=2.5, inferno", dict(vmax=2.5, cmap="inferno", norm="power0.5")),
    ("D: linear, vmax=3.0, viridis", dict(vmax=3.0, cmap="viridis", norm=None)),
]


def load_panel(alpha, beta):
    s = np.loadtxt(f"data/Sqw_tebd_pentamer_alpha={alpha}_beta={beta}.csv", delimiter=",")
    q_half = (s.shape[0] + 1) // 2
    s = s[:q_half, :]
    return s


fig, axes = plt.subplots(
    len(CONFIGS), len(BETAS),
    figsize=(2.6 * len(BETAS), 2.2 * len(CONFIGS)),
    sharex=True, sharey=True,
)

for i, (label, cfg) in enumerate(CONFIGS):
    for j, beta in enumerate(BETAS):
        ax = axes[i, j]
        alpha = ALPHAS[0]
        s = load_panel(alpha, beta)
        qh = s.shape[0]
        qv = np.linspace(0, np.pi, qh)
        ov = np.linspace(0, 3.0, s.shape[1])

        if cfg["norm"] == "power0.5":
            norm = PowerNorm(0.5, vmin=0, vmax=cfg["vmax"])
        else:
            norm = Normalize(vmin=0, vmax=cfg["vmax"])

        ax.pcolormesh(qv, ov, s.T, shading="auto", cmap=cfg["cmap"], norm=norm, rasterized=True)
        ax.set_xlim(0, np.pi)
        ax.set_ylim(0, 3.0)
        if j == 0:
            ax.set_ylabel(label + "\n" + r"$\omega/J_1$")
        if i == 0:
            ax.set_title(rf"$\beta={beta}$")
        if i == len(CONFIGS) - 1:
            ax.set_xlabel(r"$q$")
            ax.set_xticks([0, np.pi / 2, np.pi])
            ax.set_xticklabels([r"$0$", r"$\pi/2$", r"$\pi$"])

fig.suptitle(r"Config comparison, $\alpha=1.0$ row", fontsize=12)
fig.tight_layout(rect=(0, 0, 1, 0.96))
fig.savefig("figures/_map_tuning_compare_raw.png", dpi=300)
fig.savefig("figures/_map_tuning_compare_raw.pdf")
print("Saved figures/_map_tuning_compare_raw.{png,pdf}")
