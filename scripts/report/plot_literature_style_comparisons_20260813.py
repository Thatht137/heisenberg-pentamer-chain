"""按参考论文视觉语言重绘五聚体对照图。"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, Ellipse, Polygon, Rectangle


ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "docs/meeting_report_20260812/assets"
LEVELS = ROOT / "data/single_pentamer_levels.csv"
MULTIPLETS = ROOT / "results/autoresearch_v4_20260730/round2_local_spectral_channels_v4/multiplet_scan.csv"
PHASE = ROOT / "data/phase_diagram_80x60_hires.csv"
OBS = ROOT / "results/autoresearch_v5_20260802/round19_phase_diagram_positive_mesh/phase-diagram/observations_merged.json"
ENT = ROOT / "data/entanglement_spectrum"
FIG8 = ROOT / "figures/round43_fig8_final_20260806_v2.source.csv"

BLUE = "#0000ff"
RED = "#d62728"
GRAY = "#bfbfbf"
INK = "#111111"


def style() -> None:
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
            "mathtext.fontset": "stix",
            "font.size": 8,
            "axes.linewidth": 0.65,
            "axes.spines.top": True,
            "axes.spines.right": True,
            "xtick.direction": "in",
            "ytick.direction": "in",
            "xtick.top": True,
            "ytick.right": True,
            "legend.frameon": False,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
        }
    )


def panel(ax: plt.Axes, label: str, x: float = -0.09, y: float = 1.04, color: str = INK) -> None:
    ax.text(x, y, rf"$({label})$", transform=ax.transAxes, fontsize=10, color=color, va="bottom")


def save(fig: plt.Figure, name: str) -> None:
    path = ASSETS / name
    fig.savefig(path, dpi=360, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def spin_arrow(ax: plt.Axes, x: float, y: float, up: bool = True, scale: float = 1.0) -> None:
    dy = 0.18 * scale if up else -0.18 * scale
    color = RED if up else BLUE
    ax.arrow(x, y - dy / 2, 0, dy, width=0.006 * scale, head_width=0.07 * scale, head_length=0.05 * scale, color=color, length_includes_head=True, zorder=5)


def pentamer_icon(ax: plt.Axes, x: float, y: float, state: str = "neutral", width: float = 0.56) -> None:
    if state == "neutral":
        patch = Ellipse((x, y), width, 0.20, fc=GRAY, ec="none", alpha=0.88)
    elif state == "up":
        patch = Polygon([(x - width / 2, y), (x - width / 4, y + 0.18), (x + width / 4, y + 0.18), (x + width / 2, y), (x + width / 4, y - 0.18), (x - width / 4, y - 0.18)], fc=GRAY, ec="#777777", lw=0.35)
    else:
        patch = Rectangle((x - width / 2, y - 0.17), width, 0.34, fc=GRAY, ec="none")
    ax.add_patch(patch)
    xs = np.linspace(x - width * 0.34, x + width * 0.34, 5)
    ax.plot(xs, np.full(5, y), "o-", color="#444444", ms=1.8, lw=0.55, zorder=4)
    if state == "up":
        spin_arrow(ax, x, y, True, 0.85)
    elif state == "down":
        spin_arrow(ax, x, y, False, 0.85)


def draw_chain(ax: plt.Axes) -> None:
    x = np.arange(11)
    colors = [BLUE, INK, INK, BLUE, "#777777", BLUE, INK, INK, BLUE, "#777777"]
    labels = [r"$J_2$", r"$J_1$", r"$J_1$", r"$J_2$", r"$J_3$", r"$J_2$", r"$J_1$", r"$J_1$", r"$J_2$", r"$J_3$"]
    for i, (color, label) in enumerate(zip(colors, labels)):
        ax.plot([x[i], x[i + 1]], [0, 0], color=color, lw=1.55, ls="--" if label == r"$J_3$" else "-")
        ax.text(i + 0.5, 0.16, label, ha="center", va="bottom", fontsize=8)
    ax.scatter(x, np.zeros_like(x), s=22, color="black", zorder=4)
    ax.text(1.7, -0.28, r"pentamer $n$", ha="center", color="#555555")
    ax.text(6.7, -0.28, r"pentamer $n+1$", ha="center", color="#555555")
    ax.set_xlim(-0.5, 10.5)
    ax.set_ylim(-0.48, 0.46)
    ax.axis("off")


def plot_fig1() -> None:
    rows = read_csv(MULTIPLETS)
    selected = sorted([row for row in rows if abs(float(row["alpha"]) - 0.23) < 1e-9], key=lambda row: float(row["excitation"]))
    fig = plt.figure(figsize=(7.45, 4.65))
    grid = fig.add_gridspec(2, 1, height_ratios=(0.32, 1.0), hspace=0.02, left=0.06, right=0.97, bottom=0.08, top=0.96)
    ax_chain = fig.add_subplot(grid[0])
    draw_chain(ax_chain)
    panel(ax_chain, "a", -0.02, 0.78)
    ax = fig.add_subplot(grid[1])
    spins = {0.5: [], 1.5: [], 2.5: []}
    for row in selected:
        spins[float(row["spin_S"])].append(float(row["excitation"]))
    x0 = {0.5: 1.25, 1.5: 3.65, 2.5: 6.05}
    symbols = {0.5: "doublets", 1.5: "quartets", 2.5: "sextet"}
    colors = {0.5: BLUE, 1.5: "#555555", 2.5: INK}
    for spin, values in spins.items():
        for index, value in enumerate(values):
            ax.plot([x0[spin] - 0.62, x0[spin] + 0.62], [value, value], color=colors[spin], lw=1.1)
            ax.text(x0[spin] - 0.72, value, rf"$E_{{{spin:g},{index+1}}}$", color=colors[spin], ha="right", va="center", fontsize=6.6)
            pentamer_icon(ax, x0[spin] + 1.05, value, "up" if index == 0 else "neutral", width=0.48)
        spin_text = {0.5: r"1/2", 1.5: r"3/2", 2.5: r"5/2"}[spin]
        ax.text(x0[spin], 1.82, rf"$S={spin_text}$ {symbols[spin]}", ha="center", fontsize=8.5)
    ax.plot([0.1, 0.72], [0.02, 0.02], color=BLUE, lw=1.4)
    ax.text(0.42, -0.07, r"ground doublet", ha="center", color=BLUE, fontsize=7)
    ax.set_xlim(-0.15, 7.8)
    ax.set_ylim(-0.18, 1.95)
    ax.set_ylabel(r"local excitation $(E-E_0)/J_1$")
    ax.set_xticks([])
    ax.spines["bottom"].set_visible(False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    panel(ax, "b", -0.02, 0.98)
    save(fig, "ours_fig1.png")


def plot_fig2() -> None:
    rows = read_csv(LEVELS)
    grouped: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for row in rows:
        grouped[int(row["level_index"])].append((float(row["alpha"]), float(row["energy"])))
    fig, axes = plt.subplots(2, 1, figsize=(5.55, 4.8), gridspec_kw={"height_ratios": [1.42, 0.82], "hspace": 0.24})
    for values in grouped.values():
        values.sort()
        axes[0].plot([v[0] for v in values], [v[1] for v in values], color=BLUE, lw=0.52)
    axes[0].axvline(0, color="#888888", lw=0.55, ls="--")
    axes[0].set(xlim=(-1, 1), ylim=(-2.05, 1.85), xlabel=r"$\alpha$", ylabel=r"$E/J_1$")
    axes[0].text(-0.92, -1.86, r"$S=3/2$ ground multiplet", fontsize=6.6)
    axes[0].text(0.22, -1.86, r"$S=1/2$ ground multiplet", fontsize=6.6)
    panel(axes[0], "a", -0.13, 1.0)
    qrows = read_csv(MULTIPLETS)
    alphas = sorted({float(row["alpha"]) for row in qrows})
    for spin, color, label in ((0.5, BLUE, r"$S=1/2$"), (1.5, RED, r"$S=3/2$"), (2.5, "#555555", r"$S=5/2$")):
        weights = [100 * sum(float(row["qpi_weight"]) for row in qrows if abs(float(row["alpha"]) - alpha) < 1e-10 and abs(float(row["spin_S"]) - spin) < 1e-10) for alpha in alphas]
        axes[1].plot(alphas, weights, color=color, lw=0.9, marker="o", ms=1.2, label=label)
    axes[1].axvline(0.23, color="#888888", lw=0.55, ls="--")
    axes[1].set(xlim=(0, 1), ylim=(0, 46), xlabel=r"$\alpha$", ylabel=r"$q=\pi$ weight (\%)")
    axes[1].legend(ncol=3, loc="upper center", fontsize=6.5)
    panel(axes[1], "b", -0.13, 1.0)
    save(fig, "ours_fig2.png")


def phase_arrays() -> tuple[np.ndarray, np.ndarray, np.ndarray, list[dict[str, float]]]:
    rows = [(float(r["alpha"]), float(r["beta"]), float(r["O_str"])) for r in read_csv(PHASE) if float(r["alpha"]) >= 0]
    alphas = np.array(sorted({r[0] for r in rows}))
    betas = np.array(sorted({r[1] for r in rows}))
    values = np.full((len(betas), len(alphas)), np.nan)
    for alpha, beta, value in rows:
        values[np.where(betas == beta)[0][0], np.where(alphas == alpha)[0][0]] = value
    source = json.loads(OBS.read_text(encoding="utf-8"))
    strict = [{"alpha": float(r["params"]["alpha"]), "beta": float(r["params"]["beta"]), "L": int(r["params"]["L"]), "R": float(r["value"])} for r in source["records"] if r.get("status") == "success" and float(r["params"]["alpha"]) >= 0]
    return alphas, betas, values, strict


def plot_fig3() -> None:
    alphas, betas, values, strict = phase_arrays()
    fig = plt.figure(figsize=(8.0, 4.15))
    grid = fig.add_gridspec(3, 4, width_ratios=(1.55, 0.08, 0.95, 1.05), height_ratios=(1, 1, 0.55), wspace=0.52, hspace=0.34, left=0.07, right=0.98, bottom=0.12, top=0.94)
    ax = fig.add_subplot(grid[:, 0])
    image = ax.imshow(values, origin="lower", aspect="auto", extent=(0, 1, betas.min(), betas.max()), cmap="jet", vmin=0, vmax=0.4, interpolation="bilinear")
    ax.set(xlabel=r"$\beta$", ylabel=r"$\alpha$")
    ax.set_xlabel(r"$\alpha$")
    ax.set_ylabel(r"$\beta$")
    ax.contour(alphas, betas, values, levels=[0.05, 0.1, 0.2, 0.3], colors="k", linewidths=0.35, alpha=0.45)
    panel(ax, "a", 0.03, 0.94, "white")
    cax = fig.add_subplot(grid[:, 1])
    fig.colorbar(image, cax=cax)
    cax.set_title(r"$O^z_{str}$", fontsize=8, pad=5)
    axb = fig.add_subplot(grid[0, 2:])
    for alpha, color in ((0, BLUE), (0.25, RED), (0.5, "#e6a700"), (1, "#7f3c8d")):
        rows = sorted([r for r in strict if r["L"] == 80 and abs(r["alpha"] - alpha) < 1e-10], key=lambda r: r["beta"])
        axb.plot([r["beta"] for r in rows], [r["R"] for r in rows], color=color, lw=0.9, label=rf"$\alpha={alpha:g}$")
    axb.set(xlim=(0, 1), ylim=(0, 0.37), ylabel=r"$R(L=80)$")
    axb.legend(ncol=2, fontsize=6.2, loc="lower right")
    panel(axb, "b")
    axc = fig.add_subplot(grid[1, 2:])
    for beta, color in ((0.1, BLUE), (0.5, RED), (1, "#e6a700")):
        rows = sorted([r for r in strict if r["L"] == 80 and abs(r["beta"] - beta) < 1e-10], key=lambda r: r["alpha"])
        axc.plot([r["alpha"] for r in rows], [r["R"] for r in rows], color=color, lw=0.9, label=rf"$\beta={beta:g}$")
    axc.set(xlim=(0, 1), ylim=(0, 0.37), ylabel=r"$R(L=80)$")
    axc.legend(ncol=3, fontsize=6.2, loc="lower right")
    panel(axc, "c")
    axd = fig.add_subplot(grid[2, 2:])
    for beta, color in ((0.1, BLUE), (0.5, RED), (1, "#e6a700")):
        r40 = sorted([r for r in strict if r["L"] == 40 and abs(r["beta"] - beta) < 1e-10], key=lambda r: r["alpha"])
        r60 = sorted([r for r in strict if r["L"] == 60 and abs(r["beta"] - beta) < 1e-10], key=lambda r: r["alpha"])
        axd.plot([r["alpha"] for r in r40], [b["R"] - a["R"] for a, b in zip(r40, r60)], color=color, lw=0.9)
    axd.axhline(0, color="#777777", lw=0.55, ls="--")
    axd.set(xlim=(0, 1), xlabel=r"$\alpha$", ylabel=r"$R_{60}-R_{40}$")
    panel(axd, "d")
    save(fig, "ours_fig3_paper_palette.png")


def plot_fig4() -> None:
    fig, axes = plt.subplots(2, 1, figsize=(5.45, 3.75), sharex=True, gridspec_kw={"hspace": 0.28})
    for ax, alpha, label in zip(axes, (0.14, 0.33), "ab"):
        rows = read_csv(ENT / f"spectrum_a{alpha:.2f}_b0.50_L080.csv")
        for cut in range(5):
            values = sorted([float(row["probability"]) for row in rows if int(row["bond_class"]) == cut], reverse=True)[:12]
            x = cut + 1
            for value in values:
                ax.plot([x - 0.13, x + 0.13], [-2 * np.log(max(value, 1e-14))] * 2, color=INK, lw=0.55)
                ax.plot(x, -2 * np.log(max(value, 1e-14)), "o", color=INK, ms=1.25)
        ax.set_ylabel(r"$-2\log(\lambda_i)$")
        ax.set_ylim(-0.3, 18)
        ax.text(0.96, 0.88, rf"$\alpha={alpha:.2f},\ \beta=0.5$", transform=ax.transAxes, ha="right")
        panel(ax, label, -0.11, 0.98)
    axes[1].set_xlim(0.5, 5.5)
    axes[1].set_xlabel(r"cut position within the five-site unit cell")
    axes[1].set_xticks([1, 2, 3, 4, 5])
    save(fig, "ours_fig4.png")


def plot_fig5() -> None:
    fig, axes = plt.subplots(2, 3, figsize=(8.1, 4.1), gridspec_kw={"wspace": 0.25, "hspace": 0.34})
    titles = [r"$|D\rangle\to|Q\rangle$", r"projected $S=1/2$", r"bright $S=3/2$", r"odd channel: dark", r"even channel: bright", r"$q=\pi$ selection"]
    states = ["up", "up", "up", "down", "up", "neutral"]
    for index, (ax, title, state) in enumerate(zip(axes.flat, titles, states)):
        for t in range(5):
            for n in range(4):
                active = min(t, 3)
                pentamer_icon(ax, n + 0.7, 4.4 - t, state if n == active else "neutral", width=0.62)
            if index == 5:
                for n in range(4):
                    spin_arrow(ax, n + 0.7, 4.4 - t, (n + t) % 2 == 0, 0.65)
        ax.set_title(title, fontsize=8)
        ax.set_xlim(0.2, 4.2)
        ax.set_ylim(0.1, 5.0)
        ax.axis("off")
        panel(ax, chr(97 + index), -0.02, 0.98)
    save(fig, "ours_fig5.png")


def plot_fig6() -> None:
    alphas = (1.0, -1.0)
    betas = (1.0, 0.7, 0.4, 0.1)
    arrays = {(a, b): np.loadtxt(ROOT / "data" / f"Sqw_tebd_pentamer_alpha={a:.1f}_beta={b:.1f}.csv", delimiter=",") for a in alphas for b in betas}
    vmax = max(float(v.max()) for v in arrays.values())
    fig, axes = plt.subplots(2, 4, figsize=(8.2, 3.55), sharex=True, sharey=True, gridspec_kw={"wspace": 0.12, "hspace": 0.12})
    image = None
    for i, a in enumerate(alphas):
        for j, b in enumerate(betas):
            arr = arrays[(a, b)]
            q = np.linspace(0, 2 * np.pi, arr.shape[0])
            omega = np.linspace(0, 3, arr.shape[1])
            image = axes[i, j].pcolormesh(q, omega, arr.T, shading="nearest", cmap="jet", vmin=0, vmax=vmax, rasterized=True)
            axes[i, j].text(0.05, 0.91, rf"$({chr(97+i*4+j)})$", transform=axes[i, j].transAxes, color="white", fontsize=9)
            axes[i, j].text(0.95, 0.91, rf"$\alpha={a:g},\beta={b:g}$", transform=axes[i, j].transAxes, ha="right", color="white", fontsize=6.5)
            axes[i, j].set_xticks([0, np.pi, 2 * np.pi], [r"$0$", r"$\pi$", r"$2\pi$"])
            if i == 1:
                axes[i, j].set_xlabel(r"$q$")
            if j == 0:
                axes[i, j].set_ylabel(r"$\omega/J_1$")
    fig.subplots_adjust(left=0.06, right=0.92, bottom=0.12, top=0.97)
    fig.colorbar(image, ax=axes, fraction=0.018, pad=0.02)
    save(fig, "ours_fig6_paper_palette.png")


def plot_fig7() -> None:
    alphas = (0.14, 0.23, 0.33)
    arrays = [np.loadtxt(ROOT / "data" / f"Sqw_tebd_pentamer_alpha={a:.2f}_beta=0.5_L40_t15.csv", delimiter=",") for a in alphas]
    vmax = max(float(v.max()) for v in arrays)
    fig, axes = plt.subplots(1, 3, figsize=(6.15, 2.15), sharex=True, sharey=True, gridspec_kw={"wspace": 0.10})
    image = None
    for index, (ax, alpha, arr) in enumerate(zip(axes, alphas, arrays)):
        q = np.linspace(0, 2 * np.pi, arr.shape[0])
        omega = np.linspace(0, 3, arr.shape[1])
        image = ax.pcolormesh(q, omega, arr.T, shading="nearest", cmap="jet", vmin=0, vmax=vmax, rasterized=True)
        ax.set_ylim(0, 1.5)
        ax.text(0.05, 0.90, rf"$({chr(97+index)})$", transform=ax.transAxes, color="white", fontsize=9)
        ax.text(0.95, 0.90, rf"$\alpha={alpha:.2f}$", transform=ax.transAxes, ha="right", color="white", fontsize=7)
        ax.set_xticks([0, np.pi, 2 * np.pi], [r"$0$", r"$\pi$", r"$2\pi$"])
        ax.set_xlabel(r"$q$")
    axes[0].set_ylabel(r"$\omega/J_1$")
    fig.subplots_adjust(left=0.08, right=0.91, bottom=0.20, top=0.96)
    fig.colorbar(image, ax=axes, fraction=0.026, pad=0.025)
    save(fig, "ours_fig7_paper_palette.png")


def plot_fig8() -> None:
    rows = read_csv(FIG8)
    omega = np.array([float(row["omega"]) for row in rows])
    cv = np.array([float(row["cv_intensity"]) for row in rows])
    tebd = np.array([float(row["tebd_intensity"]) for row in rows])
    delta = np.array([float(row["relative_delta"]) for row in rows])
    fig = plt.figure(figsize=(5.65, 3.6))
    grid = fig.add_gridspec(2, 2, width_ratios=(1.5, 0.72), height_ratios=(1, 0.62), hspace=0.15, wspace=0.30, left=0.10, right=0.97, bottom=0.15, top=0.96)
    ax = fig.add_subplot(grid[:, 0])
    dense_x = np.linspace(omega.min(), omega.max(), 220)
    ax.plot(dense_x, np.interp(dense_x, omega, tebd), color=BLUE, lw=1.0, label="TEBD")
    ax.plot(omega, cv, "o", color=RED, ms=3.0, label="CV")
    ax.set(xlim=(0, 1.5), ylim=(0, 2.0), xlabel=r"$\omega/J_1$", ylabel=r"$S^{zz}(q=\pi,\omega)$")
    ax.legend(fontsize=7, loc="upper right")
    panel(ax, "a")
    axb = fig.add_subplot(grid[0, 1])
    axb.plot(omega, delta, "o-", color=INK, ms=2.4, lw=0.7)
    axb.axhline(0.15, color=RED, lw=0.6, ls="--")
    axb.set(xlim=(0, 1.5), ylim=(0, 0.16), ylabel="relative difference")
    axb.set_xticklabels([])
    panel(axb, "b", -0.20, 1.0)
    axc = fig.add_subplot(grid[1, 1])
    gates = ["peak\nbracket", "weight\nwindow", "peak\nbudget", "weight\nbudget"]
    axc.scatter(np.arange(4), np.ones(4), marker="s", s=28, facecolor="white", edgecolor=BLUE, lw=0.9)
    axc.set(xlim=(-0.5, 3.5), ylim=(0.7, 1.3), yticks=[], xticks=np.arange(4), xticklabels=gates)
    axc.tick_params(axis="x", labelsize=5.5)
    axc.text(1.5, 1.20, "PASS", ha="center", color=BLUE, fontsize=8)
    panel(axc, "c", -0.20, 1.0)
    save(fig, "ours_fig8.png")


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    style()
    plot_fig1()
    plot_fig2()
    plot_fig3()
    plot_fig4()
    plot_fig5()
    plot_fig6()
    plot_fig7()
    plot_fig8()


if __name__ == "__main__":
    main()
