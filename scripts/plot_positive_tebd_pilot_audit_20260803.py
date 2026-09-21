"""绘制正 alpha TEBD pilot 的时间窗与数值审计图。"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "results" / "autoresearch_v2_20260729" / "round5_dsf_window_audit_fix1" / "window_summary.csv"
OUT_DIR = ROOT / "results" / "research_progress"
FIG_DIR = ROOT / "figures"
STEM = "positive_tebd_pilot_audit_20260803"
ALPHAS = (0.14, 0.23, 0.33)
COLORS = ("#0F4D92", "#42949E", "#B64342")


mpl.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "DejaVu Sans", "Liberation Sans"],
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "font.size": 8,
        "axes.spines.right": False,
        "axes.spines.top": False,
        "axes.linewidth": 0.8,
        "legend.frameon": False,
    }
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_rows() -> list[dict[str, float]]:
    with INPUT.open(encoding="utf-8", newline="") as handle:
        rows = []
        for row in csv.DictReader(handle):
            values = {key: float(value) for key, value in row.items() if key != "raw_input_sha256"}
            if values["alpha"] in ALPHAS and values["beta"] == 0.5 and values["L"] == 40 and values["dt"] == 0.05:
                rows.append(values)
    if len(rows) != 9:
        raise RuntimeError(f"正区 pilot 行数异常: {len(rows)}")
    return sorted(rows, key=lambda row: (row["alpha"], row["tmax"]))


def panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(-0.14, 1.04, label, transform=ax.transAxes, fontsize=10, fontweight="bold", va="bottom")


def main() -> None:
    rows = load_rows()
    grouped: dict[float, list[dict[str, float]]] = defaultdict(list)
    for row in rows:
        grouped[row["alpha"]].append(row)

    source_rows = []
    for row in rows:
        source_rows.append(row)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    source_csv = OUT_DIR / f"{STEM}.csv"
    with source_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(source_rows[0]))
        writer.writeheader()
        writer.writerows(source_rows)

    fig, axes = plt.subplots(2, 2, figsize=(183 / 25.4, 110 / 25.4), constrained_layout=True)
    ax_peak, ax_rms, ax_negative, ax_q0 = axes.flat
    tmax_values = sorted({row["tmax"] for row in rows})

    for alpha, color in zip(ALPHAS, COLORS):
        data = grouped[alpha]
        tmax = [row["tmax"] for row in data]
        ax_peak.plot(tmax, [row["qpi_peak_omega"] for row in data], "o-", color=color, label=rf"$\alpha={alpha:.2f}$")
        ax_rms.plot(tmax, [row["inversion_relative_rms"] for row in data], "o-", color=color, label=rf"$\alpha={alpha:.2f}$")
        ax_negative.plot(tmax, [row["negative_to_positive_ratio"] for row in data], "o-", color=color, label=rf"$\alpha={alpha:.2f}$")
        ax_q0.semilogy(tmax, [row["q0_inelastic_ratio"] for row in data], "o-", color=color, label=rf"$\alpha={alpha:.2f}$")

    panel_label(ax_peak, "a")
    ax_peak.set_ylabel(r"$\omega_{\mathrm{peak}}(q=\pi)/J_1$")
    ax_peak.set_xlabel(r"$t_{\max}$")
    ax_peak.set_ylim(0, 1.3)
    ax_peak.set_xticks(tmax_values)
    ax_peak.axhline(0.05, color="#767676", linestyle="--", linewidth=0.8, label="production drift limit")
    ax_peak.legend(loc="upper left", fontsize=7)

    panel_label(ax_rms, "b")
    ax_rms.set_ylabel("raw inversion relative RMS")
    ax_rms.set_xlabel(r"$t_{\max}$")
    ax_rms.set_ylim(0, 1.3)
    ax_rms.set_xticks(tmax_values)
    ax_rms.axhline(0.05, color="#767676", linestyle="--", linewidth=0.8)
    ax_rms.text(0.04, 0.91, "large residual", transform=ax_rms.transAxes, color="#B64342", fontsize=7)

    panel_label(ax_negative, "c")
    ax_negative.set_ylabel("negative / positive raw weight")
    ax_negative.set_xlabel(r"$t_{\max}$")
    ax_negative.set_ylim(0, 3.6)
    ax_negative.set_xticks(tmax_values)
    ax_negative.axhline(0, color="#767676", linestyle="--", linewidth=0.8)
    ax_negative.text(0.04, 0.91, "nonnegative spectrum requires 0", transform=ax_negative.transAxes, fontsize=7)

    panel_label(ax_q0, "d")
    ax_q0.set_ylabel(r"$q=0$ inelastic ratio")
    ax_q0.set_xlabel(r"$t_{\max}$")
    ax_q0.set_xticks(tmax_values)
    ax_q0.set_ylim(1e-18, 1e-15)
    ax_q0.text(0.04, 0.91, "conservation check passes", transform=ax_q0.transAxes, fontsize=7)

    fig.suptitle("Positive-alpha TEBD pilot audit", fontsize=10, fontweight="bold")
    fig.text(0.5, -0.005, "L=40, beta=0.5, dt=0.05; pilot only, not production evidence", ha="center", fontsize=7)
    for ax in axes.flat:
        ax.grid(axis="y", color="#D9D9D9", linewidth=0.5, alpha=0.7)
        ax.set_axisbelow(True)

    for suffix, kwargs in (("svg", {}), ("pdf", {}), ("png", {"dpi": 600}), ("tiff", {"dpi": 600})):
        fig.savefig(FIG_DIR / f"{STEM}.{suffix}", bbox_inches="tight", **kwargs)
    fig.savefig(OUT_DIR / f"{STEM}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    audit = {
        "schema_version": 1,
        "status": "pilot_only",
        "scope": {"alpha_values": list(ALPHAS), "beta": 0.5, "L": 40, "dt": 0.05, "negative_alpha_included": False},
        "claim": "正区 TEBD pilot 显示 q≈pi 的候选低频响应，但时间窗、raw inversion 和 raw nonnegative 门槛尚未达到生产级。",
        "rows": rows,
        "checks": {
            "row_count": len(rows) == 9,
            "q0_conservation_max": max(row["q0_inelastic_ratio"] for row in rows),
            "raw_inversion_max": max(row["inversion_relative_rms"] for row in rows),
            "raw_negative_ratio_min": min(row["negative_to_positive_ratio"] for row in rows),
            "dt_half_available": False,
            "production_acceptance": False,
        },
        "source_sha256": {"window_summary.csv": sha256(INPUT), "derived_source.csv": sha256(source_csv)},
        "figure_files": [f"figures/{STEM}.{suffix}" for suffix in ("svg", "pdf", "png", "tiff")],
    }
    (OUT_DIR / f"{STEM}.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": audit["status"], "rows": len(rows), "figure_stem": STEM}, ensure_ascii=False))


if __name__ == "__main__":
    main()
