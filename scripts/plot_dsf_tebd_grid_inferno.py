"""批量画 10 组 DSF：2 行（α=1.0, -1.0）× 5 列（β 从大到小），inferno 配色 + 无平滑版本。
直接显示保存的网格，不平滑、不做镜像平均。
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 11,
    "axes.labelsize": 12,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "figure.dpi": 300,
})

ALPHAS = [1.0, -1.0]
BETAS = [1.0, 0.7, 0.5, 0.4, 0.1]
VMAX = 0.6  # 统一上限 0.6 保留色散对比度；α=-1.0 底部低能强带饱和是物理预期

fig, axes = plt.subplots(
    len(ALPHAS), len(BETAS),
    figsize=(3.0 * len(BETAS), 2.6 * len(ALPHAS)),
    sharex=True, sharey=True,
)

last_im = None
for i, alpha in enumerate(ALPHAS):
    for j, beta in enumerate(BETAS):
        ax = axes[i, j]
        csv_file = f"data/Sqw_tebd_pentamer_alpha={alpha}_beta={beta}.csv"
        try:
            spectrum = np.loadtxt(csv_file, delimiter=",")
        except OSError:
            ax.text(0.5, 0.5, "missing", transform=ax.transAxes,
                    ha="center", va="center", color="red")
            ax.set_title(rf"$\alpha={alpha}, \beta={beta}$", fontsize=10)
            continue

        q_points, omega_points = spectrum.shape
        qvals = np.linspace(0, 2 * np.pi, q_points)
        omegavals = np.linspace(0, 3.0, omega_points)

        last_im = ax.pcolormesh(
            qvals, omegavals, spectrum.T,
            shading="auto", cmap="inferno",
            norm=Normalize(vmin=0, vmax=VMAX),
            rasterized=True,
        )

        if i == len(ALPHAS) - 1:
            ax.set_xlabel(r"$q$")
            ax.set_xticks([0, np.pi / 2, np.pi, 3 * np.pi / 2, 2 * np.pi])
            ax.set_xticklabels([r"$0$", r"$\pi/2$", r"$\pi$", r"$3\pi/2$", r"$2\pi$"])
        if j == 0:
            ax.set_ylabel(rf"$\alpha={alpha}$" + "\n" + r"$\omega / J_1$")
        if i == 0:
            ax.set_title(rf"$\beta={beta}$", fontsize=11)

        ax.text(
            0.04, 0.94, rf"$({chr(ord('a')+i*len(BETAS)+j)})\ \alpha={alpha},\beta={beta}$",
            transform=ax.transAxes, fontsize=9, va="top", color="white",
        )

        ax.set_xlim(0, 2 * np.pi)
        ax.set_ylim(0, 3.0)

fig.tight_layout(rect=(0, 0, 0.94, 1))
if last_im is not None:
    cax = fig.add_axes([0.95, 0.15, 0.012, 0.7])
    cbar = fig.colorbar(last_im, cax=cax)
    cbar.set_label(r"$S^{zz}(q,\omega)$ (mapped)")

fig.savefig("figures/Sqw_tebd_grid_inferno_raw.pdf")
fig.savefig("figures/Sqw_tebd_grid_inferno_raw.png", dpi=300)
print("Saved figures/Sqw_tebd_grid_inferno_raw.{pdf,png}")
