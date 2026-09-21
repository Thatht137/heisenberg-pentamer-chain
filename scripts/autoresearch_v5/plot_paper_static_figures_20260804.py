#!/usr/bin/env python3
"""基于既有数据生成论文静态 Fig.1--5。"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

import plot_model_excitation_mechanism as mechanism
import plot_reference_aligned_figures_20260803 as reference12


ROOT = Path(__file__).resolve().parents[2]
FIGURES = ROOT / "figures"
REPORT = ROOT / "results" / "research_progress"
DATE = "20260804"
STEMS = {
    "Fig. 1": f"paper_fig1_model_local_multiplets_{DATE}",
    "Fig. 2": f"paper_fig2_level_flow_qpi_filter_{DATE}",
    "Fig. 3": f"paper_fig3_positive_groundstate_diagnostics_{DATE}",
    "Fig. 4": f"paper_fig4_entanglement_spectrum_{DATE}",
    "Fig. 5": f"paper_fig5_effective_chain_selection_rules_{DATE}",
}
PHASE_SOURCE = ROOT / "results/autoresearch_v5_20260802/round19_phase_diagram_positive_mesh/phase-diagram/observations_merged.json"
ENTANGLEMENT = ROOT / "data/entanglement_spectrum"
ENT_ANALYSIS = ROOT / "results/autoresearch_v4_20260730/round1_entanglement_scaling/analysis"

BLUE = "#235789"
TEAL = "#2A9D8F"
ORANGE = "#D98C2B"
RED = "#B23A48"
GRAY = "#666666"
LIGHT_TEAL = "#E8F5F2"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def style() -> None:
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "font.size": 7,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "legend.frameon": False,
        "axes.labelpad": 2.5,
        "xtick.major.width": 0.7,
        "ytick.major.width": 0.7,
    })


def panel(ax: plt.Axes, label: str, x: float = -0.10, y: float = 1.04) -> None:
    ax.text(x, y, label, transform=ax.transAxes, fontsize=9, fontweight="bold", va="bottom")


def save_bundle(fig: plt.Figure, stem: str) -> list[Path]:
    base = FIGURES / stem
    outputs = []
    for suffix in (".svg", ".pdf", ".png", ".tiff"):
        path = base.with_suffix(suffix)
        kwargs: dict[str, object] = {"bbox_inches": "tight"}
        if suffix == ".png":
            kwargs["dpi"] = 450
        if suffix == ".tiff":
            kwargs.update(dpi=600, pil_kwargs={"compression": "tiff_lzw"})
        fig.savefig(path, **kwargs)
        outputs.append(path)
    plt.close(fig)
    return outputs


def write_sidecar(figure: str, inputs: list[Path], outputs: list[Path], conclusion: str, boundary: str) -> Path:
    sidecar = FIGURES / f"{STEMS[figure]}.sources.json"
    payload = {
        "schema_version": 1,
        "figure": figure,
        "backend": "Python/matplotlib",
        "core_conclusion": conclusion,
        "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True},
        "boundary": boundary,
        "source_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in inputs},
        "outputs": {str(path.relative_to(ROOT)): sha256(path) for path in outputs},
    }
    sidecar.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return sidecar


def draw_fig1(rows: list[dict[str, float | str]]) -> tuple[list[Path], list[Path]]:
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.75), gridspec_kw={"width_ratios": [1.55, 1.0]})
    reference12.draw_chain(axes[0])
    selected = sorted(
        [row for row in rows if abs(float(row["alpha"]) - reference12.ALPHA_REP) < 1e-9],
        key=lambda row: float(row["excitation"]),
    )
    for row in selected:
        spin = float(row["spin"])
        y = float(row["excitation"])
        axes[1].plot([0.08, 0.74], [y, y], color=reference12.COLORS[spin], lw=1.6)
        if float(row["qpi_weight"]) > 1e-5:
            axes[1].scatter(0.42, y, s=22 + 80 * min(float(row["qpi_weight"]), 0.35), facecolor="white", edgecolor=TEAL, linewidth=0.8, zorder=3)
    axes[1].set(xlim=(0, 1), ylim=(-0.05, max(float(row["excitation"]) for row in selected) * 1.06), ylabel=r"local excitation $(E-E_0)/J_1$")
    axes[1].set_xticks([])
    axes[1].set_title(r"single pentamer, $\alpha=0.23$", loc="left", fontsize=8)
    axes[1].text(0.04, 0.90, r"circle area $\propto$ $q=\pi$ weight", transform=axes[1].transAxes, va="top", fontsize=6.2, color=GRAY)
    panel(axes[0], "a", -0.02)
    panel(axes[1], "b")
    handles = [Line2D([], [], color=reference12.COLORS[s], lw=2, label=reference12.LABELS[s]) for s in (0.5, 1.5, 2.5)]
    axes[1].legend(handles=handles, ncol=1, loc="center right", fontsize=6.2)
    fig.subplots_adjust(left=0.04, right=0.98, bottom=0.13, top=0.95, wspace=0.22)
    outputs = save_bundle(fig, STEMS["Fig. 1"])
    sidecar = write_sidecar(
        "Fig. 1", [reference12.MULTIPLETS], outputs,
        "A five-spin unit cell retains a low-energy spin-1/2 doublet and supports an antiferromagnetic projected chain.",
        "Local multiplets and first-order projection only; no finite-beta branch assignment.",
    )
    return outputs, [sidecar]


def draw_fig2(rows: list[dict[str, float | str]]) -> tuple[list[Path], list[Path]]:
    by_alpha: dict[float, list[dict[str, float | str]]] = defaultdict(list)
    for row in rows:
        by_alpha[float(row["alpha"])].append(row)
    alphas = np.array(sorted(by_alpha))
    ground = {a: min(float(row["energy"]) for row in by_alpha[a]) for a in alphas}
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.75), gridspec_kw={"width_ratios": [1.08, 1.0]})
    for branch in sorted({str(row["branch"]) for row in rows}):
        records = [next(row for row in by_alpha[a] if row["branch"] == branch) for a in alphas]
        spin = float(records[0]["spin"])
        axes[0].plot(alphas, [float(row["energy"]) - ground[a] for a, row in zip(alphas, records)], color=reference12.COLORS[spin], lw=0.9)
    axes[0].set(xlabel=r"intracell coupling $\alpha=J_2/J_1$", ylabel=r"multiplet gap $(E-E_0)/J_1$", xlim=(0, 1))
    axes[0].text(0.03, 0.96, "5 doublets · 4 quartets · 1 sextet", transform=axes[0].transAxes, va="top", fontsize=6.4)
    weights: dict[float, dict[float, float]] = defaultdict(lambda: defaultdict(float))
    for a in alphas:
        for row in by_alpha[a]:
            weights[float(row["spin"])][a] += float(row["qpi_weight"])
    for spin in (0.5, 1.5, 2.5):
        axes[1].plot(alphas, [100 * weights[spin][a] for a in alphas], color=reference12.COLORS[spin], lw=1.7, label=reference12.LABELS[spin])
    axes[1].axvline(reference12.ALPHA_REP, color="#777777", ls="--", lw=0.8)
    axes[1].set(xlabel=r"intracell coupling $\alpha=J_2/J_1$", ylabel=r"$q=\pi$ spectral weight (%)", xlim=(0, 1), ylim=(0, None))
    axes[1].legend(ncol=3, loc="upper center", fontsize=6.1)
    axes[1].text(reference12.ALPHA_REP + 0.03, 0.82 * axes[1].get_ylim()[1], r"$\alpha=0.23$", fontsize=6.2, color=GRAY)
    panel(axes[0], "a")
    panel(axes[1], "b")
    fig.subplots_adjust(left=0.08, right=0.98, bottom=0.17, top=0.94, wspace=0.28)
    outputs = save_bundle(fig, STEMS["Fig. 2"])
    sidecar = write_sidecar(
        "Fig. 2", [reference12.MULTIPLETS], outputs,
        "Reflection parity at q=pi suppresses the lowest doublet while quartets dominate the local inelastic channel.",
        "Isolated-pentamer ED selection rule; branch propagation requires production dynamics.",
    )
    return outputs, [sidecar]


def phase_rows() -> list[dict[str, float]]:
    data = json.loads(PHASE_SOURCE.read_text(encoding="utf-8"))
    return [{"alpha": float(r["params"]["alpha"]), "beta": float(r["params"]["beta"]), "L": float(r["params"]["L"]), "R": float(r["value"])} for r in data["records"] if r.get("status") == "success" and float(r["params"]["alpha"]) >= 0]


def draw_fig3() -> tuple[list[Path], list[Path]]:
    rows = phase_rows()
    alphas = np.array(sorted({row["alpha"] for row in rows}))
    betas = np.array(sorted({row["beta"] for row in rows}))
    def values(size: int) -> np.ndarray:
        return np.array([[next(r["R"] for r in rows if r["L"] == size and r["alpha"] == a and r["beta"] == b) for a in alphas] for b in betas])
    r40, r60, r80 = values(40), values(60), values(80)
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 4.65), gridspec_kw={"hspace": 0.36, "wspace": 0.30})
    image = axes[0, 0].imshow(r80, origin="lower", aspect="auto", extent=[alphas.min() - 0.0625, alphas.max() + 0.0625, betas.min() - 0.05, betas.max() + 0.05], cmap="YlGnBu", vmin=0, vmax=max(r80.max(), 0.4))
    axes[0, 0].set(xlabel=r"$\alpha=J_2/J_1$", ylabel=r"$\beta=J_3/J_1$")
    axes[0, 0].set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    axes[0, 0].set_yticks([0.1, 0.5, 1.0])
    fig.colorbar(image, ax=axes[0, 0], fraction=0.046, pad=0.04, label=r"$R$")
    for a, color in zip((0.0, 0.25, 0.5, 1.0), (BLUE, TEAL, ORANGE, GRAY)):
        idx = int(np.where(alphas == a)[0][0])
        axes[0, 1].plot(betas, r80[:, idx], "o-", ms=2.8, lw=1.2, color=color, label=fr"$\alpha={a:g}$")
    axes[0, 1].set(xlabel=r"$\beta$", ylabel=r"$R(L=80)$")
    axes[0, 1].legend(fontsize=6.1, ncol=2)
    for b, color in zip((0.1, 0.5, 1.0), (BLUE, TEAL, ORANGE)):
        idx = int(np.where(betas == b)[0][0])
        axes[1, 0].plot(alphas, r80[idx], "o-", ms=2.8, lw=1.2, color=color, label=fr"$\beta={b:g}$")
        axes[1, 1].plot(alphas, r60[idx] - r40[idx], "o-", ms=2.8, lw=1.2, color=color, label=fr"$\beta={b:g}$")
    axes[1, 0].set(xlabel=r"$\alpha$", ylabel=r"$R(L=80)$")
    axes[1, 0].legend(fontsize=6.1)
    axes[1, 1].axhline(0, color="#777777", lw=0.8, ls="--")
    axes[1, 1].set(xlabel=r"$\alpha$", ylabel=r"$R_{60}-R_{40}$")
    axes[1, 1].legend(fontsize=6.1)
    axes[1, 1].text(0.03, 0.94, "finite-size diagnostic; no phase boundary", transform=axes[1, 1].transAxes, va="top", fontsize=6.1, color=GRAY, bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.78, "pad": 1.5})
    for ax, label in zip(axes.flat, "abcd"):
        panel(ax, label)
    fig.subplots_adjust(left=0.08, right=0.97, bottom=0.10, top=0.96, wspace=0.38)
    outputs = save_bundle(fig, STEMS["Fig. 3"])
    sidecar = write_sidecar(
        "Fig. 3", [PHASE_SOURCE], outputs,
        "The positive-coupling mesh is smooth within finite-size resolution and shows no accepted crossing bracket.",
        "Finite-size R diagnostics only; no thermodynamic phase boundary or phase name is claimed.",
    )
    return outputs, [sidecar]


def load_spectrum(alpha: float) -> tuple[Path, dict[int, list[tuple[float, float]]]]:
    path = ENTANGLEMENT / f"spectrum_a{alpha:.2f}_b0.50_L080.csv"
    grouped: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for row in read_csv(path):
        grouped[int(row["bond_class"])].append((float(row["level"]), float(row["entanglement_energy"])))
    return path, grouped


def draw_fig4() -> tuple[list[Path], list[Path]]:
    alphas = (0.14, 0.33)
    loaded = {a: load_spectrum(a) for a in alphas}
    estimators = read_csv(ENT_ANALYSIS / "calibrated_estimators.csv")
    fig = plt.figure(figsize=(7.2, 4.8))
    grid = fig.add_gridspec(3, 5, height_ratios=(1.0, 1.0, 0.72), hspace=0.30, wspace=0.14, left=0.075, right=0.985, bottom=0.11, top=0.95)
    for row_idx, alpha in enumerate(alphas):
        for cut in range(5):
            ax = fig.add_subplot(grid[row_idx, cut])
            values = np.asarray(loaded[alpha][1][cut], dtype=float)
            ax.scatter(values[:, 0], values[:, 1] - values[0, 1], s=14, color=BLUE, edgecolor="white", linewidth=0.25)
            ax.set_xlim(0.4, max(values[:, 0]) + 0.6)
            ax.set_ylim(bottom=-0.08)
            ax.grid(alpha=0.15, linewidth=0.4)
            ax.set_xticks([1, 4, 8])
            if row_idx == 0:
                ax.set_title(f"cut {cut + 1}", fontsize=7)
            if cut == 0:
                ax.set_ylabel(fr"$\alpha={alpha:.2f}$" + "\n" + r"$\xi_i-\xi_1$")
            else:
                ax.set_yticklabels([])
            if row_idx == 1:
                ax.set_xlabel("level")
            else:
                ax.set_xticklabels([])
    hero = fig.add_subplot(grid[2, :])
    labels = ["midchain\nN=8–24", "midchain\nN=12–24", "profile\nN=24"]
    ratios = np.array([float(row["ratio"]) for row in estimators])
    x = np.arange(len(ratios))
    hero.bar(x, ratios, width=0.58, color=[BLUE, TEAL, ORANGE])
    hero.axhline(1.0, color="#333333", ls="--", lw=0.9)
    hero.fill_between([-0.6, 2.6], 0.90, 1.10, color="#F0F0F0", zorder=-1)
    hero.set(xlim=(-0.6, 2.6), ylim=(0.98, 1.045), ylabel=r"pentamer / $c=1$ oracle")
    hero.set_xticks(x, labels)
    for xpos, value in zip(x, ratios):
        hero.text(xpos, value + 0.0015, f"{value:.3f}", ha="center", va="bottom", fontsize=6.3)
    hero.text(2.55, 1.002, "matched-size calibration", ha="right", va="bottom", fontsize=6.2, color=GRAY)
    panel(fig.axes[0], "a", -0.34)
    panel(fig.axes[5], "b", -0.34)
    panel(hero, "c", -0.035)
    outputs = save_bundle(fig, STEMS["Fig. 4"])
    inputs = [loaded[a][0] for a in alphas] + [ENT_ANALYSIS / "calibrated_estimators.csv", ENT_ANALYSIS / "claim_summary.json"]
    sidecar = write_sidecar(
        "Fig. 4", inputs, outputs,
        "The five inequivalent cuts retain structured entanglement spectra while matched-size estimators agree with the c=1 oracle within 3.31%.",
        "The calibrated comparison is supported; raw absolute log-L fits fail their quality gate and are not used as a thermodynamic estimate.",
    )
    return outputs, [sidecar]


def draw_fig5() -> tuple[list[Path], list[Path]]:
    projection_path = mechanism.PROJECTION_DIR / "projection_scan.csv"
    multiplet_path = mechanism.SPECTRAL_DIR / "multiplet_scan.csv"
    folded_path = mechanism.SPECTRAL_DIR / "folded_transition_weights.csv"
    projection = read_csv(projection_path)
    multiplets = read_csv(multiplet_path)
    folded = read_csv(folded_path)
    rep = min(projection, key=lambda row: abs(float(row["alpha"]) - mechanism.ALPHA_REP))
    coefficients = np.array([float(rep[f"c{i}"]) for i in range(1, 6)])
    alpha = np.array([float(row["alpha"]) for row in projection])
    jeff = np.array([float(row["jeff_over_beta"]) for row in projection])
    levels = [row for row in multiplets if abs(float(row["alpha"]) - mechanism.ALPHA_REP) < 1e-12]
    level_index = {row["branch"]: row for row in levels}
    dark, bright = level_index["S0.5_r-_1"], level_index["S1.5_r+_1"]
    dark_curve = mechanism.branch_rows(folded, "S0.5_r-_1")
    bright_curve = mechanism.branch_rows(folded, "S1.5_r+_1")
    fractions = mechanism.qpi_channel_fractions(multiplets)

    fig = plt.figure(figsize=(7.2, 6.0))
    grid = fig.add_gridspec(3, 6, height_ratios=(1.08, 1.0, 1.0), hspace=0.42, wspace=0.70, left=0.07, right=0.985, bottom=0.08, top=0.97)
    ax_model = fig.add_subplot(grid[0, :])
    ax_coeff = fig.add_subplot(grid[1, :3])
    ax_jeff = fig.add_subplot(grid[1, 3:])
    ax_levels = fig.add_subplot(grid[2, :2])
    ax_q = fig.add_subplot(grid[2, 2:4])
    ax_fraction = fig.add_subplot(grid[2, 4:])
    mechanism.draw_model_panel(ax_model)
    ax_model.texts[-1].remove()
    panel(ax_model, "a", -0.01, 0.98)

    sites = np.arange(1, 6)
    ax_coeff.axhline(0, color="#888888", lw=0.7)
    ax_coeff.bar(sites, coefficients, width=0.68, color=[BLUE if v >= 0 else ORANGE for v in coefficients])
    ax_coeff.set(xlim=(0.35, 5.65), ylim=(-0.36, 0.77), xlabel="site $i$", ylabel=r"projection coefficient $c_i$")
    ax_coeff.set_xticks(sites)
    panel(ax_coeff, "b")

    ax_jeff.fill_between(alpha, 0, jeff, color=LIGHT_TEAL)
    ax_jeff.plot(alpha, jeff, color=TEAL, lw=1.7)
    for target in (0.14, 0.23, 0.33):
        idx = int(np.argmin(abs(alpha - target)))
        ax_jeff.plot(alpha[idx], jeff[idx], "o", color=RED, ms=3.6)
    ax_jeff.set(xlim=(0, 1), ylim=(-0.015, max(jeff) * 1.12), xlabel=r"intracell coupling $\alpha$", ylabel=r"$J_{\rm eff}/\beta=c_1c_5$")
    ax_jeff.text(0.98, 0.92, "positive at all 100 ED points", transform=ax_jeff.transAxes, ha="right", color=TEAL, fontsize=6.2)
    panel(ax_jeff, "c")

    dark_y, bright_y = float(dark["excitation"]), float(bright["excitation"])
    for y, color, text in ((0, BLUE, r"ground $S=1/2,+$"), (dark_y, GRAY, r"$S=1/2,-$"), (bright_y, TEAL, r"$S=3/2,+$")):
        ax_levels.plot([0.08, 0.60], [y, y], color=color, lw=2)
        ax_levels.text(0.64, y, text, va="center", fontsize=5.8, color=color)
    ax_levels.annotate("dark", xy=(0.24, dark_y), xytext=(0.24, 0.04), ha="center", color=GRAY, arrowprops={"arrowstyle": "-|>", "color": GRAY, "ls": "--"})
    ax_levels.annotate("bright", xy=(0.48, bright_y), xytext=(0.48, 0.04), ha="center", color=TEAL, arrowprops={"arrowstyle": "-|>", "color": TEAL})
    ax_levels.set(xlim=(0, 1.12), ylim=(-0.025, 0.285), ylabel=r"excitation / $J_1$")
    ax_levels.set_xticks([])
    panel(ax_levels, "d", -0.16)

    q_dark = np.array([float(row["q_over_pi"]) for row in dark_curve])
    w_dark = np.array([float(row["weight"]) for row in dark_curve])
    q_bright = np.array([float(row["q_over_pi"]) for row in bright_curve])
    w_bright = np.array([float(row["weight"]) for row in bright_curve])
    ax_q.plot(q_bright, w_bright, "o-", color=TEAL, ms=3.5, lw=1.4, label=r"even $S=3/2$")
    ax_q.plot(q_dark, w_dark, "s-", color=GRAY, ms=3.2, lw=1.2, label=r"odd $S=1/2$")
    ax_q.plot(1, 0, "x", color=RED, ms=5)
    ax_q.set(xlim=(0.15, 1.85), ylim=(-0.012, max(w_bright) * 1.16), xlabel=r"momentum $q/\pi$", ylabel="transition weight")
    ax_q.legend(fontsize=5.8, loc="upper left")
    panel(ax_q, "e", -0.16)

    fraction_alphas = np.array(sorted(fractions))
    quartet = np.array([fractions[a].get(1.5, 0) for a in fraction_alphas]) * 100
    doublet = np.array([fractions[a].get(0.5, 0) for a in fraction_alphas]) * 100
    ax_fraction.fill_between(fraction_alphas, 0, quartet, color=LIGHT_TEAL)
    ax_fraction.plot(fraction_alphas, quartet, color=TEAL, lw=1.7, label=r"$S=3/2$")
    ax_fraction.plot(fraction_alphas, doublet, color=BLUE, lw=1.3, label=r"$S=1/2$")
    ax_fraction.set(xlim=(0, 1), ylim=(-2, 103), xlabel=r"intracell coupling $\alpha$", ylabel=r"inelastic $q=\pi$ weight (%)")
    ax_fraction.legend(fontsize=5.8, loc="center right")
    panel(ax_fraction, "f", -0.16)

    outputs = save_bundle(fig, STEMS["Fig. 5"])
    sidecar = write_sidecar(
        "Fig. 5", [projection_path, multiplet_path, folded_path], outputs,
        "The projected antiferromagnetic chain carries low-energy propagation while reflection parity filters local multiplet channels at q=pi.",
        "Mechanism and isolated-cell weights only; no unvalidated quasiparticle name is introduced.",
    )
    return outputs, [sidecar]


def main() -> None:
    style()
    FIGURES.mkdir(parents=True, exist_ok=True)
    rows = reference12.load_rows()
    generated: dict[str, dict[str, object]] = {}
    for figure, builder in (("Fig. 1", lambda: draw_fig1(rows)), ("Fig. 2", lambda: draw_fig2(rows)), ("Fig. 3", draw_fig3), ("Fig. 4", draw_fig4), ("Fig. 5", draw_fig5)):
        outputs, sidecars = builder()
        generated[figure] = {
            "stem": STEMS[figure],
            "outputs": {path.suffix.lstrip("."): {"path": str(path.relative_to(ROOT)), "sha256": sha256(path), "bytes": path.stat().st_size} for path in outputs},
            "sidecar": str(sidecars[0].relative_to(ROOT)),
        }
    manifest = {
        "schema_version": 1,
        "created_at": "2026-08-04",
        "backend": "Python/matplotlib",
        "status": "pass",
        "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True},
        "figures": generated,
        "boundary": "Fig.1--5 are manuscript-ready static or explicitly bounded finite-size figures; Fig.6--8 remain dynamic non-production assets.",
    }
    path = REPORT / "paper_static_figures_manifest_20260804.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
