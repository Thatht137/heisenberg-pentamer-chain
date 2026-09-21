#!/usr/bin/env python3
"""绘制负 alpha Practical V2 的终态证据图。"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
PHASE = ROOT / "results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha/phase-diagram-v2"
SOURCE = PHASE / "stage_c_practical_v2_r1_boundary_decision.json"
OUT = ROOT / "figures/negative_practical_v2_crossover_20260913"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_rows() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    points: dict[tuple[float, float], dict[str, object]] = {}
    evidence: list[dict[str, object]] = []

    for index, decision in enumerate(payload["decisions"], start=1):
        beta = float(decision["beta"])
        for point in decision["points"]:
            alpha = float(point["alpha"])
            points[(beta, alpha)] = {
                "beta": beta,
                "alpha": alpha,
                "q_l60": float(point["q"]["L60"]),
                "q_l80": float(point["q"]["L80"]),
                "momentum_class": point["momentum_class"],
                "delta_r": float(point["delta_R_80_60"]["value"]),
                "delta_r_error": float(point["delta_R_80_60"]["error"]),
                "delta_r_sigma": float(point["delta_R_80_60"]["sigma"]),
            }

        candidates = decision["candidate_brackets"]
        momentum = any("momentum_reconstruction" in item["evidence"] for item in candidates)
        ratio = any("two_sigma_ratio_sign" in item["evidence"] for item in candidates)
        width = any(float(item["width"]) <= 0.025 + 1e-12 for item in candidates)
        initial = [float(value) for value in decision["initial_alpha"]]
        evidence.append(
            {
                "target": index,
                "beta": beta,
                "alpha_left": initial[0],
                "alpha_right": initial[1],
                "momentum_reconstruction": int(momentum),
                "two_sigma_ratio_sign": int(ratio),
                "width_le_0p025": int(width),
                "dual_diagnostic": int(any(item["dual_diagnostic"] for item in candidates)),
                "status": decision["status"],
            }
        )

    return sorted(points.values(), key=lambda row: (row["beta"], row["alpha"])), evidence


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def draw(points: list[dict[str, object]], evidence: list[dict[str, object]]) -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "font.size": 7,
            "axes.linewidth": 0.8,
            "axes.spines.right": False,
            "axes.spines.top": False,
            "legend.frameon": False,
        }
    )
    OUT.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(7.2, 5.9), constrained_layout=True)
    grid = fig.add_gridspec(2, 2, height_ratios=[1.15, 1.0], width_ratios=[1.35, 1.0])
    ax_map = fig.add_subplot(grid[0, :])
    ax_flow = fig.add_subplot(grid[1, 0])
    ax_gate = fig.add_subplot(grid[1, 1])

    betas = sorted({float(row["beta"]) for row in points})
    colors = plt.cm.viridis(np.linspace(0.08, 0.92, len(betas)))
    beta_color = dict(zip(betas, colors))

    # a：只显示采样点，不做二维插值。
    for beta in betas:
        group = [row for row in points if float(row["beta"]) == beta]
        xs = np.array([float(row["alpha"]) for row in group])
        ys = np.full_like(xs, beta)
        order = np.argsort(xs)
        ax_map.plot(xs[order], ys[order], color="#c7cbd1", lw=0.8, zorder=1)
    q80 = np.array([float(row["q_l80"]) for row in points])
    scatter = ax_map.scatter(
        [row["alpha"] for row in points],
        [row["beta"] for row in points],
        c=q80,
        cmap="cividis",
        vmin=0.58,
        vmax=1.0,
        s=58,
        edgecolor="#20242a",
        linewidth=0.55,
        zorder=3,
    )
    mixed = [row for row in points if row["momentum_class"] == "size_sensitive_or_mixed"]
    ax_map.scatter(
        [row["alpha"] for row in mixed],
        [row["beta"] for row in mixed],
        marker="x",
        s=42,
        color="#c23b45",
        linewidth=1.1,
        zorder=4,
        label="L60/L80 momentum mismatch",
    )
    bar = fig.colorbar(scatter, ax=ax_map, pad=0.015, fraction=0.03)
    bar.set_label(r"$q_{\mathrm{peak}}(L=80)/\pi$")
    ax_map.set_xlim(-0.82, -0.005)
    ax_map.set_ylim(0.0, 1.05)
    ax_map.set_xlabel(r"$\alpha=J_2/J_1$")
    ax_map.set_ylabel(r"$\beta=J_3/J_1$")
    ax_map.legend(loc="lower left")
    ax_map.set_title("a  Accepted large-size momentum samples", loc="left", fontweight="bold")

    # b：尺寸流展示两西格玛换号与动量重构不总是重合。
    for beta in betas:
        group = sorted((row for row in points if float(row["beta"]) == beta), key=lambda row: row["alpha"])
        ax_flow.errorbar(
            [row["alpha"] for row in group],
            [row["delta_r"] for row in group],
            yerr=[row["delta_r_error"] for row in group],
            marker="o",
            ms=3.2,
            lw=1.0,
            capsize=1.8,
            color=beta_color[beta],
            label=fr"$\beta={beta:g}$",
        )
    ax_flow.axhline(0, color="#2c3138", lw=0.8, ls="--")
    ax_flow.set_xlabel(r"$\alpha$")
    ax_flow.set_ylabel(r"$\Delta R=R_{80}-R_{60}$")
    ax_flow.set_title("b  Dominant-ratio finite-size flow", loc="left", fontweight="bold")
    ax_flow.legend(ncol=2, fontsize=5.8, columnspacing=0.8, handlelength=1.4)

    # c：每个候选目标的正式证据门。
    matrix = np.array(
        [
            [
                row["momentum_reconstruction"],
                row["two_sigma_ratio_sign"],
                row["width_le_0p025"],
                row["dual_diagnostic"],
            ]
            for row in evidence
        ],
        dtype=float,
    )
    cmap = mpl.colors.ListedColormap(["#eef0f2", "#346e9d"])
    ax_gate.imshow(matrix, aspect="auto", cmap=cmap, vmin=0, vmax=1)
    ax_gate.set_xticks(range(4), ["q shift", r"$2\sigma$ flow", r"width $\leq .025$", "dual"], rotation=32, ha="right")
    labels = [
        rf"{row['target']}: $\beta={row['beta']:g}$" + "\n" + f"[{row['alpha_left']:g},{row['alpha_right']:g}]"
        for row in evidence
    ]
    ax_gate.set_yticks(range(len(evidence)), labels, fontsize=5.8)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            ax_gate.text(j, i, "yes" if matrix[i, j] else "no", ha="center", va="center", color="white" if matrix[i, j] else "#5f6670", fontsize=5.8)
    ax_gate.set_title("c  Boundary-evidence gates", loc="left", fontweight="bold")
    for spine in ax_gate.spines.values():
        spine.set_visible(False)

    fig.suptitle(r"Negative-$\alpha$ momentum reconstruction remains a finite-size crossover", fontsize=10, fontweight="bold")
    fig.text(
        0.5,
        -0.012,
        "All 29 Stage-C cells passed numerical validation; none of the eight targets passed the predeclared dual-diagnostic boundary rule.",
        ha="center",
        fontsize=6.5,
    )
    base = OUT / "negative_alpha_crossover_summary"
    fig.savefig(base.with_suffix(".svg"), bbox_inches="tight")
    fig.savefig(base.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(base.with_suffix(".png"), dpi=300, bbox_inches="tight")
    fig.savefig(base.with_suffix(".tiff"), dpi=600, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    points, evidence = load_rows()
    OUT.mkdir(parents=True, exist_ok=True)
    point_csv = OUT / "negative_alpha_crossover_points.csv"
    evidence_csv = OUT / "negative_alpha_crossover_evidence.csv"
    write_csv(point_csv, points)
    write_csv(evidence_csv, evidence)
    draw(points, evidence)
    outputs = [
        point_csv,
        evidence_csv,
        OUT / "negative_alpha_crossover_summary.svg",
        OUT / "negative_alpha_crossover_summary.pdf",
        OUT / "negative_alpha_crossover_summary.png",
        OUT / "negative_alpha_crossover_summary.tiff",
    ]
    qa = {
        "status": "pass",
        "core_conclusion": "Stage C resolves a finite-size momentum reconstruction but not a dual-diagnostic thermodynamic boundary.",
        "archetype": "quantitative grid",
        "backend": "python_matplotlib_only",
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "points": len(points),
        "targets": len(evidence),
        "dual_diagnostic_boundaries": sum(int(row["dual_diagnostic"]) for row in evidence),
        "interpolation_used": False,
        "exports": {path.name: {"bytes": path.stat().st_size, "sha256": sha256(path)} for path in outputs},
        "review_risks": [
            "Sparse beta slices do not define a continuous thermodynamic boundary.",
            "Mixed L60/L80 momentum points are marked explicitly and are not assigned a phase label.",
            "The figure supports crossover wording only; it does not establish a new phase.",
        ],
    }
    (OUT / "negative_alpha_crossover_summary.qa.json").write_text(
        json.dumps(qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": "pass", "points": len(points), "targets": len(evidence), "output": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
