"""Plot S^zz(q, omega) from TEBD data — publication quality."""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 12,
    "axes.labelsize": 14,
    "xtick.labelsize": 12,
    "ytick.labelsize": 12,
    "figure.dpi": 300,
})

ALPHA = -1.0
BETA = 0.5
VMAX = 1.0

csv_file = f"data/Sqw_tebd_pentamer_alpha={ALPHA}_beta={BETA}.csv"
spectrum = np.loadtxt(csv_file, delimiter=",")

q_points, omega_points = spectrum.shape
qvals = np.linspace(0, 2 * np.pi, q_points)
omegavals = np.linspace(0, 3.0, omega_points)

print(f"Spectrum shape: {spectrum.shape}")
print(f"Max intensity: {spectrum.max():.4f}")
print(f"Vmax (clip): {VMAX}")

fig, ax = plt.subplots(figsize=(7, 5))
im = ax.pcolormesh(
    qvals,
    omegavals,
    spectrum.T,
    shading="auto",
    cmap="inferno",
    norm=Normalize(vmin=0, vmax=VMAX),
    rasterized=True,
)

ax.set_xlabel(r"$q$")
ax.set_ylabel(r"$\omega / J_1$")
ax.set_xlim(0, 2 * np.pi)
ax.set_ylim(0, 3.0)
ax.set_xticks([0, np.pi / 2, np.pi, 3 * np.pi / 2, 2 * np.pi])
ax.set_xticklabels([r"$0$", r"$\pi/2$", r"$\pi$", r"$3\pi/2$", r"$2\pi$"])

cbar = fig.colorbar(im, ax=ax, pad=0.02)
cbar.set_label(r"$S^{zz}(q,\omega)$")

ax.text(
    0.02, 0.96,
    rf"$\alpha={ALPHA},\ \beta={BETA}$",
    transform=ax.transAxes,
    fontsize=11,
    va="top",
    color="white",
)

fig.tight_layout()
fig.savefig(f"figures/Sqw_tebd_alpha={ALPHA}_beta={BETA}.pdf")
fig.savefig(f"figures/Sqw_tebd_alpha={ALPHA}_beta={BETA}.png", dpi=300)
print("Saved to figures/")
plt.show()
