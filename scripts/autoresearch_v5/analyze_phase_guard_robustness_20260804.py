"""汇总正区有限尺寸 guard 的显著性裕量和 leave-one-beta-out 稳健性。"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "results/autoresearch_v5_20260802/round19_phase_diagram_positive_mesh/phase-diagram/phase-size-differences.csv"
OUTPUT_DIR = ROOT / "results/autoresearch_v5_20260804/round34_phase_guard_robustness"
FIGURE = ROOT / "figures/positive_phase_guard_margin_20260804"
ALPHAS = (0.125, 0.25, 0.5, 1.0)
BETAS = (0.05, 0.1, 0.25, 0.5, 0.75, 1.0)
PAIRS = ("40-60", "60-80")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main() -> None:
    with SOURCE.open(encoding="utf-8", newline="") as handle:
        rows = [
            {
                "beta": float(row["beta"]),
                "alpha": float(row["alpha"]),
                "size_pair": row["size_pair"],
                "delta": float(row["delta_R"]),
                "error": float(row["error"]),
            }
            for row in csv.DictReader(handle)
            if float(row["alpha"]) > 0.0
        ]
    margins = {(pair, beta, alpha): next(row["delta"] / (2.0 * row["error"]) for row in rows if row["size_pair"] == pair and row["beta"] == beta and row["alpha"] == alpha) for pair in PAIRS for beta in BETAS for alpha in ALPHAS}
    leave_one_out = []
    for pair in PAIRS:
        subset = [row for row in rows if row["size_pair"] == pair]
        for beta in BETAS:
            kept = [row for row in subset if row["beta"] != beta]
            leave_one_out.append({
                "size_pair": pair,
                "omitted_beta": beta,
                "rows": len(kept),
                "all_negative": all(row["delta"] < 0 for row in kept),
                "all_significant_2sigma": all(abs(row["delta"]) > 2.0 * row["error"] for row in kept),
                "minimum_abs_delta_over_2sigma": min(abs(row["delta"]) / (2.0 * row["error"]) for row in kept),
            })
    pair_summary = []
    for pair in PAIRS:
        subset = [row for row in rows if row["size_pair"] == pair]
        pair_summary.append({
            "size_pair": pair,
            "count": len(subset),
            "all_negative": all(row["delta"] < 0 for row in subset),
            "all_significant_2sigma": all(abs(row["delta"]) > 2.0 * row["error"] for row in subset),
            "minimum_abs_delta_over_2sigma": min(abs(row["delta"]) / (2.0 * row["error"]) for row in subset),
            "maximum_abs_delta_over_2sigma": max(abs(row["delta"]) / (2.0 * row["error"]) for row in subset),
        })

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "schema_version": 1,
        "status": "pass" if len(rows) == 56 and all(item["all_negative"] and item["all_significant_2sigma"] for item in pair_summary) else "fail",
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": digest(SOURCE),
        "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True, "alpha_zero_boundary_excluded": True},
        "pair_summary": pair_summary,
        "leave_one_beta_out": leave_one_out,
        "interpretation": "两组最终相邻尺寸差在所有内部点均为负且过 2σ；逐 beta 留一后仍保持该性质，支持当前 guard 的有限尺寸稳健性，不等价于热力学极限相图完成。",
    }
    (OUTPUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUTPUT_DIR / "source.sha256").write_text(f"{digest(SOURCE)}  {SOURCE.name}\n", encoding="utf-8")

    plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans", "Liberation Sans"], "font.size": 7, "svg.fonttype": "none", "pdf.fonttype": 42})
    figure, axes = plt.subplots(1, 2, figsize=(7.2, 3.15), sharey=True, constrained_layout=True)
    values = np.array([[margins[(pair, beta, alpha)] for alpha in ALPHAS] for beta in BETAS])
    limit = max(1.0, float(np.max(np.abs(values))))
    for axis, pair in zip(axes, PAIRS):
        matrix = np.array([[margins[(pair, beta, alpha)] for alpha in ALPHAS] for beta in BETAS])
        image = axis.imshow(matrix, origin="lower", aspect="auto", cmap="Blues", vmin=-limit, vmax=0.0)
        axis.set_xticks(range(len(ALPHAS)), [str(alpha) for alpha in ALPHAS])
        axis.set_yticks(range(len(BETAS)), [str(beta) for beta in BETAS])
        axis.set_xlabel(r"$\alpha$ (internal)")
        axis.set_title(f"L={pair.replace('-', '→')}")
        for row_index in range(len(BETAS)):
            for col_index in range(len(ALPHAS)):
                axis.text(col_index, row_index, f"{matrix[row_index, col_index]:.1f}", ha="center", va="center", color="white" if matrix[row_index, col_index] < -limit * 0.45 else "#1f2937", fontsize=6)
    axes[0].set_ylabel(r"$\beta$")
    colorbar = figure.colorbar(image, ax=axes, fraction=0.035, pad=0.03)
    colorbar.set_label(r"$\Delta R/(2\sigma)$")
    figure.suptitle("Positive-region crossing-guard robustness", fontsize=10, fontweight="bold")
    figure.text(0.5, -0.035, "56 internal rows; all negative and significant; leave-one-beta-out remains negative; no phase label", ha="center", fontsize=6.5, color="#555555")
    for suffix, kwargs in ((".svg", {}), (".pdf", {}), (".png", {"dpi": 600}), (".tiff", {"dpi": 600})):
        figure.savefig(FIGURE.with_suffix(suffix), bbox_inches="tight", **kwargs)
    plt.close(figure)
    outputs = [FIGURE.with_suffix(suffix) for suffix in (".svg", ".pdf", ".png", ".tiff")]
    provenance = {
        "schema_version": 1,
        "figure": FIGURE.name,
        "backend": "Python/matplotlib",
        "reference_mapping": "positive phase finite-size crossing guard",
        "source_files": [{"path": str(SOURCE.relative_to(ROOT)).replace("\\", "/"), "sha256": digest(SOURCE)}],
        "outputs": [str(path.relative_to(ROOT)).replace("\\", "/") for path in outputs],
        "scope": summary["scope"],
        "status": summary["status"],
    }
    FIGURE.with_suffix(".sources.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": summary["status"], "rows": len(rows), "leave_one_out": len(leave_one_out)}, ensure_ascii=False))
    if summary["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
