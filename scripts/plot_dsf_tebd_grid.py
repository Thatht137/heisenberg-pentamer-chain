"""批量画 10 组 DSF：2 行（α=1.0, -1.0）× 5 列（β 从大到小），对照文献 Fig. 6 风格。
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from scipy.ndimage import gaussian_filter

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 11,
    "axes.labelsize": 12,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "figure.dpi": 300,
})

ALPHAS = [1.0, -1.0]
BETAS = [1.0, 0.7, 0.5, 0.4, 0.1]  # 从大到小，匹配文献 Fig. 6 演化方向
VMAX = 1.0  # 与文献 0-1.1 接近
SMOOTH_SIGMA = (3.0, 10.0)  # (sigma_q, sigma_omega) 像素：q 方向轻平滑保留色散，ω 方向重平滑模拟 broadening；标量或 0 也可

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

        # 强制 inversion symmetry: S(q) = S(2π-q)。
        # 五聚体单胞基态是 S=1/2 doublet，开边界留边缘自由度 + TEBD 截断误差累积，
        # 使 [π,2π] 半区有数值噪声。镜像平均消除不对称，保持全 [0,2π] 范围。
        spectrum = 0.5 * (spectrum + spectrum[::-1, :])

        # 频域高斯平滑（各向异性）：spectrum.shape = (q, ω)，sigma 同维度
        if SMOOTH_SIGMA and (np.asarray(SMOOTH_SIGMA) > 0).any():
            spectrum = gaussian_filter(spectrum, sigma=SMOOTH_SIGMA)

        last_im = ax.pcolormesh(
            qvals, omegavals, spectrum.T,
            shading="auto", cmap="jet",
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

fig.savefig("figures/Sqw_tebd_grid_sym.pdf")
fig.savefig("figures/Sqw_tebd_grid_sym.png", dpi=300)
print("Saved figures/Sqw_tebd_grid_sym.{pdf,png}")
