"""
分析 beta=0.5 五点试验性 TEBD 动力学结构因子。
"""

import csv
import os

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np


ALPHAS = (-0.50, -0.05, 0.14, 0.23, 0.33)
BETA = 0.5
TAG = "L40_t15"
OMEGA_MAX = 3.0
LOW_OMEGA_MAX = 0.2
FIGURE_STEM = "figures/Sqw_beta_half_pilot_L40_t15"
SUMMARY_PATH = "data/dsf_beta_half_pilot_L40_t15_summary.csv"


def alpha_label(alpha):
    return f"{alpha:g}"


def load_spectrum(alpha):
    path = (
        "data/Sqw_tebd_pentamer_"
        f"alpha={alpha_label(alpha)}_beta={BETA:g}_{TAG}.csv"
    )
    spectrum = np.loadtxt(path, delimiter=",")
    qvals = np.linspace(0.0, 2.0 * np.pi, spectrum.shape[0])
    omegavals = np.linspace(0.0, OMEGA_MAX, spectrum.shape[1])
    return spectrum, qvals, omegavals


def extract_metrics(alpha, spectrum, qvals, omegavals):
    low_mask = omegavals <= LOW_OMEGA_MAX
    low_map = spectrum[:, low_mask]
    low_profile = np.trapezoid(
        low_map,
        omegavals[low_mask],
        axis=1,
    )
    soft_index = np.unravel_index(np.argmax(low_map), low_map.shape)

    qpi_index = np.argmin(np.abs(qvals - np.pi))
    qpi_cut = spectrum[qpi_index, :]
    inelastic_mask = omegavals >= LOW_OMEGA_MAX
    inelastic_peak_index = np.argmax(qpi_cut[inelastic_mask])
    inelastic_peak_omega = omegavals[inelastic_mask][inelastic_peak_index]

    folded_momenta = (0.2, 0.6, 1.0, 1.4, 1.8)
    folded_weights = {}
    profile_max = max(np.max(low_profile), np.finfo(float).eps)
    for momentum in folded_momenta:
        index = np.argmin(np.abs(qvals / np.pi - momentum))
        folded_weights[f"W_q{momentum:.1f}pi_norm"] = (
            low_profile[index] / profile_max
        )

    return {
        "alpha": alpha,
        "beta": BETA,
        "L": 40,
        "tmax": 15.0,
        "omega_resolution_scale": 2.0 * np.pi / 15.0,
        "low_omega_max": LOW_OMEGA_MAX,
        "low_weight_fraction": np.sum(low_map) / np.sum(spectrum),
        "soft_q_over_pi": qvals[soft_index[0]] / np.pi,
        "soft_omega": omegavals[low_mask][soft_index[1]],
        "soft_intensity": low_map[soft_index],
        "qpi_inelastic_peak_omega": inelastic_peak_omega,
        **folded_weights,
    }, low_profile


def export_summary(rows):
    os.makedirs("data", exist_ok=True)
    with open(SUMMARY_PATH, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def plot_spectra(items):
    mpl.rcParams.update({
        "font.family": "Arial",
        "font.size": 6.5,
        "axes.labelsize": 7.5,
        "xtick.labelsize": 6.5,
        "ytick.labelsize": 6.5,
        "pdf.fonttype": 42,
        "svg.fonttype": "none",
    })

    all_values = np.concatenate([
        spectrum.ravel() for _, spectrum, _, _, _ in items
    ])
    vmax = np.quantile(all_values, 0.995)

    fig, axes = plt.subplots(
        2,
        len(items),
        figsize=(7.2, 3.45),
        sharex="col",
        sharey="row",
        gridspec_kw={"height_ratios": (2.2, 1.0)},
        layout="constrained",
    )

    image = None
    for column, (alpha, spectrum, qvals, omegavals, low_profile) in enumerate(items):
        top = axes[0, column]
        bottom = axes[1, column]

        image = top.pcolormesh(
            qvals / np.pi,
            omegavals,
            spectrum.T,
            shading="auto",
            cmap="inferno",
            vmin=0.0,
            vmax=vmax,
            rasterized=True,
        )
        top.set_ylim(0.0, 1.5)
        top.set_title(rf"$\alpha={alpha:g}$", pad=3)
        top.text(
            0.04,
            0.94,
            f"({chr(ord('a') + column)})",
            transform=top.transAxes,
            color="white",
            fontweight="bold",
            va="top",
        )

        normalized = low_profile / max(
            np.max(low_profile),
            np.finfo(float).eps,
        )
        bottom.plot(qvals / np.pi, normalized, color="#0072B2", linewidth=1.2)
        bottom.set_ylim(-0.03, 1.05)
        bottom.text(
            0.04,
            0.90,
            f"({chr(ord('f') + column)})",
            transform=bottom.transAxes,
            fontweight="bold",
            va="top",
        )
        bottom.set_xlabel(r"$q/\pi$")
        bottom.set_xticks((0.0, 0.5, 1.0, 1.5, 2.0))
        bottom.spines["top"].set_visible(False)
        bottom.spines["right"].set_visible(False)

    axes[0, 0].set_ylabel(r"$\omega/J_1$")
    axes[1, 0].set_ylabel(
        rf"$\int_0^{{{LOW_OMEGA_MAX:g}}}S^{{zz}}\,d\omega$"
        "\n(normalized)"
    )

    colorbar = fig.colorbar(
        image,
        ax=axes[0, :],
        orientation="vertical",
        fraction=0.022,
        pad=0.012,
        aspect=35,
    )
    colorbar.set_label(r"$S^{zz}(q,\omega)$")

    os.makedirs("figures", exist_ok=True)
    fig.savefig(f"{FIGURE_STEM}.pdf", bbox_inches="tight")
    fig.savefig(f"{FIGURE_STEM}.svg", bbox_inches="tight")
    fig.savefig(f"{FIGURE_STEM}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def main():
    rows = []
    items = []
    for alpha in ALPHAS:
        spectrum, qvals, omegavals = load_spectrum(alpha)
        metrics, low_profile = extract_metrics(
            alpha,
            spectrum,
            qvals,
            omegavals,
        )
        rows.append(metrics)
        items.append((alpha, spectrum, qvals, omegavals, low_profile))

    export_summary(rows)
    plot_spectra(items)
    print(f"已保存: {SUMMARY_PATH}")
    print(f"已保存: {FIGURE_STEM}.pdf/.svg/.png")


if __name__ == "__main__":
    main()
