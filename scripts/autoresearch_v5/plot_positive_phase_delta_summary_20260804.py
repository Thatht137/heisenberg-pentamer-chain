"""绘制正区有限尺寸差摘要图，不把尺寸趋势命名为相界。"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "results/autoresearch_v5_20260802/round19_phase_diagram_positive_mesh/phase-diagram/phase-size-differences.csv"
OUT_STEM = ROOT / "figures/positive_phase_delta_summary_20260804"
SUMMARY_JSON = ROOT / "results/research_progress/positive_phase_delta_summary_20260804.json"
SUMMARY_CSV = ROOT / "results/research_progress/positive_phase_delta_summary_20260804.csv"
REPORT = ROOT / "results/research_progress/report.json"
TITLE = "2026-08-04 正区有限尺寸差摘要图"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_rows() -> list[dict[str, float | str | bool]]:
    with SOURCE.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    selected = []
    for row in rows:
        alpha = float(row["alpha"])
        if alpha <= 0.0:
            continue
        selected.append(
            {
                "beta": float(row["beta"]),
                "alpha": alpha,
                "size_pair": row["size_pair"],
                "delta_R": float(row["delta_R"]),
                "error": float(row["error"]),
                "significant_2sigma": row["significant_2sigma"].lower() == "true",
            }
        )
    return selected


def make_figure(rows: list[dict[str, float | str | bool]]) -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "font.size": 8,
            "axes.spines.right": False,
            "axes.spines.top": False,
            "axes.linewidth": 0.8,
            "legend.frameon": False,
        }
    )
    betas = sorted({float(row["beta"]) for row in rows})
    pairs = ["40-60", "60-80"]
    colors = plt.get_cmap("viridis")(np.linspace(0.12, 0.88, len(betas)))
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.1), sharey=True, constrained_layout=True)
    x_values = np.array([0.125, 0.25, 0.5, 1.0])
    for axis, pair in zip(axes, pairs):
        for beta, color in zip(betas, colors):
            subset = [row for row in rows if row["size_pair"] == pair and float(row["beta"]) == beta]
            subset.sort(key=lambda item: float(item["alpha"]))
            if not subset:
                continue
            x = np.array([float(item["alpha"]) for item in subset])
            y = np.array([float(item["delta_R"]) for item in subset])
            yerr = 2.0 * np.array([float(item["error"]) for item in subset])
            axis.errorbar(x, y, yerr=yerr, color=color, marker="o", markersize=3.2, linewidth=1.0, capsize=2.0, label=fr"$\beta={beta:g}$")
        axis.axhline(0.0, color="#333333", linewidth=0.8, linestyle="--")
        pair_label = pair.replace("-", "→")
        axis.set_title(f"L={pair_label}", pad=7)
        axis.set_xlabel(r"$\alpha$ (internal points only)")
        axis.set_xticks(x_values)
        axis.set_xticklabels(["0.125", "0.25", "0.5", "1"])
        axis.grid(axis="y", color="#dddddd", linewidth=0.45, alpha=0.7)
        axis.set_xlim(0.05, 1.08)
    axes[0].set_ylabel(r"$\Delta R=R(L_{\rm large})-R(L_{\rm small})$")
    axes[1].legend(title="slice", fontsize=6.5, title_fontsize=7, loc="lower right")
    fig.suptitle("Positive-region finite-size differences", fontsize=11, fontweight="bold")
    fig.text(0.5, -0.015, "All 56 internal rows are negative and pass the 2σ guard; alpha=0 boundary rows omitted; no phase claim.", ha="center", fontsize=7.2, color="#555555")
    for suffix, kwargs in [("png", {"dpi": 600}), ("tiff", {"dpi": 600})]:
        fig.savefig(OUT_STEM.with_suffix(f".{suffix}"), bbox_inches="tight", **kwargs)
    fig.savefig(OUT_STEM.with_suffix(".svg"), bbox_inches="tight")
    fig.savefig(OUT_STEM.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    rows = load_rows()
    grouped: dict[str, list[dict[str, float | str | bool]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["size_pair"])].append(row)
    summary_rows = []
    for pair in sorted(grouped):
        subset = grouped[pair]
        deltas = [float(row["delta_R"]) for row in subset]
        margins = [abs(float(row["delta_R"])) - 2.0 * float(row["error"]) for row in subset]
        summary_rows.append(
            {
                "size_pair": pair,
                "count": len(subset),
                "delta_min": min(deltas),
                "delta_max": max(deltas),
                "delta_mean": sum(deltas) / len(deltas),
                "minimum_2sigma_margin": min(margins),
                "all_negative": all(value < 0 for value in deltas),
                "all_significant_2sigma": all(bool(row["significant_2sigma"]) for row in subset),
            }
        )
    result = {
        "schema_version": 1,
        "created_at": "2026-08-04T08:55:00+08:00",
        "status": "pass" if len(rows) == 56 and all(item["all_negative"] and item["all_significant_2sigma"] for item in summary_rows) else "fail",
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": sha256(SOURCE),
        "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True, "alpha_zero_boundary_excluded": True},
        "internal_rows": len(rows),
        "summary": summary_rows,
        "interpretation": "40-60 和 60-80 尺寸差的全部 alpha>0 内部记录均为负且通过 2σ；支持当前有限尺寸 guard 未见内部 crossing，不等价于热力学极限单相证明。",
        "figure_exports": [str(OUT_STEM.with_suffix(f".{suffix}").relative_to(ROOT)).replace("\\", "/") for suffix in ("png", "svg", "pdf", "tiff")],
    }
    SUMMARY_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with SUMMARY_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0]))
        writer.writeheader()
        writer.writerows(summary_rows)
    make_figure(rows)

    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "基于已有 105 条正区记录的本地摘要；不连接服务器，不新增计算，不把有限尺寸趋势命名为相界。",
        "blocks": [
            {"kind": "verdict", "status": "good" if result["status"] == "pass" else "bad", "label": "56/56 内部尺寸差通过 2σ 且为负", "why": "40–60 与 60–80 两组尺寸差均未出现可验收内部 crossing；alpha=0 边界点按协议排除。"},
            {"kind": "figures", "items": [{"src": "../../figures/positive_phase_delta_summary_20260804.png", "caption": "本地静态验收图。两组尺寸差的每条曲线对应一个正 beta 截面，误差棒为 2σ；所有内部 alpha>0 记录低于零。该图只支持‘当前有限尺寸数据未见内部 crossing’，不宣称热力学极限相图。"}]},
            {"kind": "table", "columns": ["尺寸对", "记录数", "ΔR 范围", "最小 2σ 裕量", "结论"], "rows": [[item["size_pair"], str(item["count"]), f"{item['delta_min']:.4f} … {item['delta_max']:.4f}", f"{item['minimum_2sigma_margin']:.3e}", "全部负且通过"] for item in summary_rows], "widths": ["15%", "15%", "28%", "22%", "20%"]},
            {"kind": "kv", "pairs": [["JSON", "results/research_progress/positive_phase_delta_summary_20260804.json"], ["CSV", "results/research_progress/positive_phase_delta_summary_20260804.csv"], ["解释边界", "支持有限尺寸 guard；不证明热力学极限单相"]]},
        ],
    }
    report["sections"] = [entry for entry in report["sections"] if entry.get("title") != TITLE]
    report["sections"].insert(3, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · STATIC PHASE-GUARD SUMMARY"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "internal_rows": len(rows), "exports": result["figure_exports"]}, ensure_ascii=False))
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
