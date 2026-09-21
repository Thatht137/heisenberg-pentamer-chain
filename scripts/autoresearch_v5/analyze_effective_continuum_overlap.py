#!/usr/bin/env python3
"""分析有效链连续谱与局域四重态的能量重叠边界。"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
PROJECTION = ROOT / "results" / "autoresearch_v3_20260729" / "round1_doublet_projection" / "representative.csv"
MULTIPLETS = ROOT / "results" / "autoresearch_v4_20260730" / "round2_local_spectral_channels_v4" / "representative_summary.csv"
OUTDIR = ROOT / "results" / "autoresearch_v5_20260730" / "round5_effective_continuum_overlap"
FIGURE_BASE = ROOT / "figures" / "effective_continuum_overlap_20260730"
ALPHAS = (0.14, 0.23, 0.33)
CONTROLLED_G_MAX = 0.65


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_index(path: Path, key: str = "alpha") -> dict[float, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return {round(float(row[key]), 12): row for row in csv.DictReader(handle)}


def build_rows() -> list[dict[str, float]]:
    projection = read_index(PROJECTION)
    multiplets = read_index(MULTIPLETS)
    rows: list[dict[str, float]] = []
    for alpha in ALPHAS:
        p = projection[alpha]
        m = multiplets[alpha]
        doublet_gap = float(m["lowest_excited_doublet"])
        quartet_gap = float(m["lowest_quartet"])
        jeff_per_beta = float(p["jeff_over_beta"])
        beta_embed = quartet_gap / (math.pi * jeff_per_beta)
        g_embed = beta_embed / doublet_gap
        rows.append({
            "alpha": alpha,
            "doublet_gap": doublet_gap,
            "quartet_gap": quartet_gap,
            "jeff_per_beta": jeff_per_beta,
            "controlled_g_max": CONTROLLED_G_MAX,
            "controlled_beta_max": CONTROLLED_G_MAX * doublet_gap,
            "upper_to_quartet_at_controlled_edge": (
                math.pi * jeff_per_beta * CONTROLLED_G_MAX * doublet_gap / quartet_gap
            ),
            "formal_beta_embed": beta_embed,
            "formal_g_embed": g_embed,
            "g_at_beta_005": 0.05 / doublet_gap,
            "g_at_beta_05": 0.5 / doublet_gap,
        })
    return rows


def write_csv(path: Path, rows: list[dict[str, float]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot(rows: list[dict[str, float]]) -> list[Path]:
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans", "Liberation Sans"]
    plt.rcParams["svg.fonttype"] = "none"
    plt.rcParams["pdf.fonttype"] = 42
    plt.rcParams["font.size"] = 7
    plt.rcParams["axes.linewidth"] = 0.8
    plt.rcParams["axes.spines.right"] = False
    plt.rcParams["axes.spines.top"] = False
    plt.rcParams["legend.frameon"] = False

    colors = ["#0F4D92", "#42949E", "#9A4D8E"]
    fig = plt.figure(figsize=(7.2, 3.8), constrained_layout=True)
    grid = fig.add_gridspec(1, 2, width_ratios=(1.65, 1.0))
    ax_ratio = fig.add_subplot(grid[0, 0])
    ax_scale = fig.add_subplot(grid[0, 1])

    g_values = np.linspace(0.0, 1.30, 300)
    ax_ratio.axvspan(0.0, CONTROLLED_G_MAX, color="#DDF3DE", alpha=0.75, zorder=0)
    ax_ratio.axhline(1.0, color="#4D4D4D", lw=1.0, ls="--")
    for row, color in zip(rows, colors):
        slope = math.pi * row["jeff_per_beta"] * row["doublet_gap"] / row["quartet_gap"]
        ratio = slope * g_values
        ax_ratio.plot(
            g_values,
            ratio,
            color=color,
            lw=1.8,
            label=rf"$\alpha={row['alpha']:.2f}$",
        )
        ax_ratio.plot(row["formal_g_embed"], 1.0, marker="o", ms=4.5, color=color)
    ax_ratio.text(0.025, 0.94, "empirical controlled region", transform=ax_ratio.transAxes,
                  color="#2E6E3E", fontsize=6.5, va="top")
    ax_ratio.text(1.28, 1.015, "formal overlap", color="#4D4D4D", ha="right", va="bottom")
    ax_ratio.set_xlim(0.0, 1.30)
    ax_ratio.set_ylim(0.0, 1.16)
    ax_ratio.set_xlabel(r"$g=\beta/\Delta_{1/2}$")
    ax_ratio.set_ylabel(r"$\pi J_{\mathrm{eff}}/\Delta_{3/2}$ at $q=\pi$")
    ax_ratio.legend(loc="lower right", fontsize=6.2, handlelength=1.8)
    ax_ratio.text(-0.12, 1.03, "a", transform=ax_ratio.transAxes, fontsize=9,
                  fontweight="bold", va="bottom")

    x = np.arange(len(rows), dtype=float)
    g_embed = [row["formal_g_embed"] for row in rows]
    g_005 = [row["g_at_beta_005"] for row in rows]
    g_05 = [row["g_at_beta_05"] for row in rows]
    ax_scale.axhspan(0.08, CONTROLLED_G_MAX, color="#DDF3DE", alpha=0.75, zorder=0)
    ax_scale.axhline(CONTROLLED_G_MAX, color="#2E6E3E", lw=1.1, ls="--",
                     label=r"controlled ceiling $g=0.65$")
    ax_scale.plot(x, g_embed, color="#E28E2C", marker="o", ms=4.5, lw=1.2,
                  label="formal quartet overlap")
    ax_scale.plot(x, g_005, color="#0F4D92", marker="s", ms=4.2, lw=1.2,
                  label=r"$\beta=0.05$")
    ax_scale.plot(x, g_05, color="#B64342", marker="^", ms=4.5, lw=1.2,
                  label=r"$\beta=0.5$")
    ax_scale.set_yscale("log")
    ax_scale.set_ylim(0.08, 7.0)
    ax_scale.set_xticks(x, [f"{row['alpha']:.2f}" for row in rows])
    ax_scale.set_xlabel(r"$\alpha$")
    ax_scale.set_ylabel(r"coupling ratio $g$")
    ax_scale.legend(loc="upper right", fontsize=6.2, handlelength=1.8)
    ax_scale.text(-0.19, 1.03, "b", transform=ax_scale.transAxes, fontsize=9,
                  fontweight="bold", va="bottom")

    outputs: list[Path] = []
    for suffix in (".svg", ".pdf", ".png", ".tiff"):
        path = FIGURE_BASE.with_suffix(suffix)
        kwargs: dict[str, object] = {"bbox_inches": "tight"}
        if suffix in {".png", ".tiff"}:
            kwargs["dpi"] = 600
        if suffix == ".tiff":
            kwargs["pil_kwargs"] = {"compression": "tiff_lzw"}
        fig.savefig(path, **kwargs)
        outputs.append(path)
    plt.close(fig)
    return outputs


def main() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    FIGURE_BASE.parent.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    csv_path = OUTDIR / "continuum_overlap.csv"
    write_csv(csv_path, rows)
    figure_paths = plot(rows)

    checks = {
        "positive_jeff": all(row["jeff_per_beta"] > 0 for row in rows),
        "controlled_quartet_separated": all(
            row["upper_to_quartet_at_controlled_edge"] < 1 for row in rows
        ),
        "formal_overlap_outside_controlled_region": all(
            row["formal_g_embed"] > CONTROLLED_G_MAX for row in rows
        ),
        "beta_005_inside_controlled_region": all(
            row["g_at_beta_005"] <= CONTROLLED_G_MAX for row in rows
        ),
        "beta_05_outside_controlled_region": all(
            row["g_at_beta_05"] > CONTROLLED_G_MAX for row in rows
        ),
    }
    summary = {
        "tag": "Controlled separation; uncontrolled formal overlap"
        if all(checks.values()) else "Check failed",
        "formula": {
            "lower_two_spinon": "omega_L(q)=pi*J_eff/2*abs(sin(q))",
            "upper_two_spinon": "omega_U(q)=pi*J_eff*abs(sin(q/2))",
            "formal_embedding_at_q_pi": "beta_embed=Delta_3/2/(pi*(J_eff/beta))",
        },
        "convention": "spin-1/2 S operators; H_eff=J_eff sum T_n dot T_(n+1)",
        "oracle_scope": {
            "model": "heisenberg-xxx",
            "covered": "S-operator convention, spinon velocity, lower boundary",
            "not_covered": "two-spinon upper boundary",
        },
        "checks": checks,
        "rows": rows,
        "source_sha256": {
            str(PROJECTION.relative_to(ROOT)): sha256(PROJECTION),
            str(MULTIPLETS.relative_to(ROOT)): sha256(MULTIPLETS),
        },
        "figure_sha256": {path.name: sha256(path) for path in figure_paths},
        "boundary": (
            "The two-spinon formulas are thermodynamic leading-order effective-chain "
            "boundaries. Formal overlap beyond g=0.65 is not a controlled hybridization prediction."
        ),
    }
    summary_path = OUTDIR / "continuum_overlap_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    files = sorted(path for path in OUTDIR.iterdir() if path.is_file() and path.name != "checksums.sha256")
    (OUTDIR / "checksums.sha256").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in files), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
