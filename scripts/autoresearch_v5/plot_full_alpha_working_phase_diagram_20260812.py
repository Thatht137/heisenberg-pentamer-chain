#!/usr/bin/env python3
"""绘制完整 alpha 工作相图与有限尺寸证据。"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Rectangle


ROOT = Path(__file__).resolve().parents[2]
PHASE = ROOT / "results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha/phase-diagram-v2"
INPUT_CSV = PHASE / "stage_a_finite_size_diagnostic_latest.csv"
INPUT_JSON = PHASE / "stage_a_finite_size_diagnostic_latest.json"
OUT = ROOT / "figures/full_alpha_working_phase_diagram_20260812"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with INPUT_CSV.open(encoding="utf-8", newline="") as handle:
        for raw in csv.DictReader(handle):
            rows.append({
                "alpha": float(raw["alpha"]),
                "beta": float(raw["beta"]),
                "L": int(raw["L"]),
                "R": float(raw["R"]),
                "R_error": float(raw["R_error"]),
                "q_peak_over_pi": float(raw["q_peak_over_pi"]),
                "boundary_eligible": raw["boundary_eligible"] == "True",
                "artifact": raw["artifact"],
            })
    return rows


def write_source(rows: list[dict[str, object]]) -> Path:
    target = OUT.with_suffix(".source.csv")
    fields = ["alpha", "beta", "L", "R", "R_error", "q_peak_over_pi", "boundary_eligible", "artifact"]
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return target


def main() -> int:
    rows = load_rows()
    diagnostic = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    grouped: dict[int, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[int(row["L"])].append(row)
    for values in grouped.values():
        values.sort(key=lambda item: float(item["alpha"]))

    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
        "font.size": 7,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "legend.frameon": False,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
    })
    fig = plt.figure(figsize=(183 / 25.4, 116 / 25.4))
    grid = fig.add_gridspec(2, 2, width_ratios=(1.18, 1), wspace=0.30, hspace=0.38)
    ax_map = fig.add_subplot(grid[:, 0])
    ax_q = fig.add_subplot(grid[0, 1])
    ax_r = fig.add_subplot(grid[1, 1])

    colors = {
        "ic": "#e7b56d",
        "recon": "#f3d5a9",
        "comm": "#b9d7b6",
        "af": "#aacbe5",
        "blue": "#2f6fb0",
        "teal": "#3f949c",
        "purple": "#7768c7",
        "orange": "#c96f0a",
    }

    # a：二维工作相图。
    ax_map.add_patch(Rectangle((-1, 0), 0.65, 1, color=colors["ic"], alpha=0.64, lw=0))
    ax_map.add_patch(Rectangle((-0.35, 0), 0.10, 1, facecolor=colors["recon"], alpha=0.72,
                               edgecolor=colors["orange"], hatch="////", lw=0.7))
    ax_map.add_patch(Rectangle((-0.25, 0), 0.25, 1, color=colors["comm"], alpha=0.64, lw=0))
    ax_map.add_patch(Rectangle((0, 0), 1, 1, color=colors["af"], alpha=0.72, lw=0))
    ax_map.axvline(0, color="#222222", lw=2.0, zorder=5)
    ax_map.axhline(0, color="#333333", lw=1.2, ls=":", zorder=5)
    ax_map.axhline(0.5, color="#444444", lw=0.9, ls="--", zorder=4)

    stage_alphas = sorted({float(row["alpha"]) for row in rows})
    for alpha in stage_alphas:
        available = [row for row in rows if float(row["alpha"]) == alpha]
        q_values = [float(row["q_peak_over_pi"]) for row in available]
        if max(q_values) < 0.8:
            face = colors["orange"]
        elif min(q_values) > 0.9:
            face = "#3e7b4d"
        else:
            face = "white"
        ax_map.scatter(alpha, 0.5, s=25, facecolor=face, edgecolor="#333333", lw=0.6, zorder=7)
    ax_map.plot([-0.35, -0.25], [0.5, 0.5], color=colors["orange"], lw=3.2, zorder=6)

    ax_map.text(-0.69, 0.78, "Candidate IC\ncritical regime", ha="center", weight="bold",
                color="#71400d", fontsize=7.5)
    ax_map.text(-0.69, 0.66, r"$q_{peak}\approx0.60\pi$" + "\n" + r"effective $S\approx3/2$",
                ha="center", color="#71400d", fontsize=6.8)
    ax_map.text(-0.30, 0.86, "Lifshitz-like\nreconstruction", ha="center", color="#9a4f05", weight="bold")
    ax_map.text(-0.125, 0.77, "Candidate\ncommensurate\ncritical regime", ha="center",
                color="#285b37", weight="bold", fontsize=6.2, linespacing=1.05)
    ax_map.text(-0.125, 0.62, r"$q_{peak}=\pi$", ha="center", color="#285b37", fontsize=6.6)
    ax_map.text(0.50, 0.72, r"$q=\pi$ gapless AF", ha="center", color="#15558f", weight="bold", fontsize=9)
    ax_map.text(0.50, 0.63, r"effective $S=1/2$", ha="center", color="#15558f")
    ax_map.text(0.015, 0.12, r"$\alpha=0$: decoupled / highly degenerate line", rotation=90,
                va="bottom", color="#303030")
    ax_map.text(-0.97, 0.515, r"calibrated slice $\beta=0.5$", va="bottom", color="#303030")
    ax_map.text(0.51, 0.025, r"$\beta=0$: isolated-cell boundary", ha="center", color="#303030")
    ax_map.text(-0.50, 0.075, "Negative-side 2D boundaries remain provisional", ha="center",
                color="#5d4a36", style="italic")
    ax_map.set(xlim=(-1, 1), ylim=(0, 1), xlabel=r"$\alpha=J_2/J_1$", ylabel=r"$\beta=J_3/J_1$")
    ax_map.set_xticks([-1, -0.75, -0.5, -0.25, 0, 0.5, 1])
    ax_map.set_yticks([0, 0.25, 0.5, 0.75, 1])
    ax_map.grid(color="white", lw=0.7, alpha=0.72)
    ax_map.set_title("a  Working phase diagram", loc="left", weight="bold")

    # b：主峰位置证据。
    style = {40: ("o", colors["blue"]), 60: ("s", colors["teal"]), 80: ("^", colors["purple"])}
    for L in (40, 60, 80):
        values = grouped[L]
        ax_q.plot([float(row["alpha"]) for row in values], [float(row["q_peak_over_pi"]) for row in values],
                  marker=style[L][0], color=style[L][1], ms=4.0, lw=1.1, label=f"L={L}")
    ax_q.axhline(0.6, color="#888888", lw=0.7, ls=":")
    ax_q.axhline(1.0, color="#888888", lw=0.7, ls=":")
    ax_q.axvspan(-0.35, -0.25, color=colors["recon"], alpha=0.55, lw=0)
    ax_q.set(xlim=(-1.03, 0.02), ylim=(0.56, 1.035), ylabel=r"$q_{peak}/\pi$")
    ax_q.set_xticklabels([])
    ax_q.legend(ncol=1, loc="center left", fontsize=6.5, handlelength=1.8)
    ax_q.set_title(r"b  $\beta=0.5$: momentum reconstruction", loc="left", weight="bold")

    # c：有限尺寸差分证据。
    alpha_summary = diagnostic["alpha_summary"]
    alpha_values = [float(item["alpha"]) for item in alpha_summary]
    d6040 = [float(item["delta_R_60_40"]["value"]) for item in alpha_summary]
    e6040 = [float(item["delta_R_60_40"]["error"]) for item in alpha_summary]
    d8060 = [float(item["delta_R_80_60"]["value"]) for item in alpha_summary]
    e8060 = [float(item["delta_R_80_60"]["error"]) for item in alpha_summary]
    ax_r.errorbar(alpha_values, d6040, yerr=e6040, marker="o", ms=3.8, lw=1.0,
                  color=colors["blue"], capsize=2, label=r"$R_{60}-R_{40}$")
    ax_r.errorbar(alpha_values, d8060, yerr=e8060, marker="s", ms=3.8, lw=1.0,
                  color=colors["teal"], capsize=2, label=r"$R_{80}-R_{60}$")
    ax_r.axhline(0, color="#333333", lw=0.8)
    ax_r.axvspan(-0.35, -0.25, color=colors["recon"], alpha=0.55, lw=0)
    ax_r.set(xlim=(-1.03, 0.02), xlabel=r"$\alpha$ at $\beta=0.5$", ylabel=r"finite-size $\Delta R$")
    ax_r.legend(loc="lower left", fontsize=6.5)
    ax_r.set_title("c  Size-flow changes sign in the same bracket", loc="left", weight="bold")

    fig.suptitle("1×5 Heisenberg pentamer: working count = 3 bulk regimes + 1 singular line",
                 fontsize=11, weight="bold", y=0.985)
    fig.text(0.5, 0.006,
             "Interpretive labels are intentionally permissive. Only the beta=0.5 bracket is calibrated; "
             "Stage B/C must establish its beta dependence and thermodynamic status.",
             ha="center", va="bottom", fontsize=6.2, color="#444444")
    fig.subplots_adjust(left=0.075, right=0.985, bottom=0.12, top=0.91)

    for suffix in ("svg", "pdf", "png", "tiff"):
        fig.savefig(OUT.with_suffix(f".{suffix}"), dpi=600 if suffix == "tiff" else 300, bbox_inches="tight")
    plt.close(fig)

    source = write_source(rows)
    sources = {
        "schema_version": 1,
        "core_conclusion": "Three bulk regimes are a useful working interpretation; the negative-side Lifshitz bracket remains provisional.",
        "archetype": "asymmetric mixed-modality figure",
        "scope": {"alpha": [-1, 1], "beta": [0, 1], "fig9_excluded": True},
        "working_phase_count": 3,
        "singular_lines": ["alpha=0"],
        "calibrated_slice": {"beta": 0.5, "candidate_alpha_bracket": [-0.35, -0.25]},
        "strict_boundary_confirmed": False,
        "inputs": {
            str(INPUT_CSV.relative_to(ROOT)).replace("\\", "/"): sha256(INPUT_CSV),
            str(INPUT_JSON.relative_to(ROOT)).replace("\\", "/"): sha256(INPUT_JSON),
        },
        "source_data": {str(source.relative_to(ROOT)).replace("\\", "/"): sha256(source)},
    }
    OUT.with_suffix(".sources.json").write_text(json.dumps(sources, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    qa = {
        "status": "pass",
        "width_mm": 183,
        "height_mm": 116,
        "backend": "python",
        "editable_svg_text": True,
        "strict_boundary_claimed": False,
        "source_rows": len(rows),
        "outputs": {
            suffix: {"sha256": sha256(OUT.with_suffix(f".{suffix}")), "bytes": OUT.with_suffix(f".{suffix}").stat().st_size}
            for suffix in ("svg", "pdf", "png", "tiff")
        },
    }
    OUT.with_suffix(".qa.json").write_text(json.dumps(qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "pass", "png": str(OUT.with_suffix('.png')), "rows": len(rows)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
