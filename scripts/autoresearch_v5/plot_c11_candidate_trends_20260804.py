"""绘制 C11 候选控制点的有限尺寸趋势。"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "results/research_progress/c11_candidate_matrix_20260804.json"
OUT = ROOT / "figures/c11_candidate_trends_20260804"
REPORT_PNG = ROOT / "results/research_progress/c11_candidate_trends_20260804.png"
REPORT = ROOT / "results/research_progress/report.json"
TITLE = "2026-08-04 C11 候选点有限尺寸趋势"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    selected = payload["selected_controls"]
    sizes = np.array([40, 60, 80], dtype=float)
    colors = plt.get_cmap("tab10")(np.linspace(0.05, 0.85, len(selected)))
    plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"], "font.size": 7.5, "svg.fonttype": "none", "pdf.fonttype": 42, "axes.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.0), gridspec_kw={"wspace": 0.42})
    for axis in axes:
        axis.grid(axis="y", color="#D9D9D9", linewidth=0.45, alpha=0.65)
        axis.tick_params(width=0.7, length=3, pad=2)

    labels = []
    deltas = []
    errors = []
    for index, row in enumerate(selected):
        records = sorted(row["records"], key=lambda item: int(item["L"]))
        values = np.array([float(item["value"]) for item in records])
        yerr = np.array([float(item["error"]) for item in records])
        label = rf"$({row['alpha']:.3g},{row['beta']:.3g})$"
        labels.append(label)
        deltas.append(float(row["delta_60_80"]))
        errors.append(float(np.hypot(yerr[1], yerr[2])))
        axes[0].errorbar(sizes, values, yerr=yerr, marker="o", markersize=3.7, linewidth=1.1, capsize=2, color=colors[index], label=label)

    axes[0].set_xlabel("chain length $L$")
    axes[0].set_ylabel("$R(L)$")
    axes[0].set_xticks(sizes)
    axes[0].set_title("finite-size trend", fontsize=8)
    axes[0].legend(fontsize=6.1, ncol=2, frameon=False)
    positions = np.arange(len(selected))
    axes[1].axhline(0.0, color="#666666", linewidth=0.8)
    axes[1].errorbar(positions, deltas, yerr=errors, fmt="o", color="#2166AC", ecolor="#666666", capsize=2, markersize=4)
    axes[1].set_xticks(positions, labels, rotation=35, ha="right")
    axes[1].set_ylabel("$R(80)-R(60)$")
    axes[1].set_title("size promotion", fontsize=8)
    for axis, label in zip(axes, ("a", "b")):
        axis.text(-0.13, 1.04, label, transform=axis.transAxes, fontsize=9, fontweight="bold")
    fig.suptitle("C11 candidate controls: finite-size diagnostics", fontsize=9.5, fontweight="bold", x=0.02, ha="left")
    fig.text(0.02, 0.01, "Selected from validated manifests; trends are finite-size evidence, not a phase-boundary claim.", fontsize=6.4, color="#4D4D4D")
    fig.subplots_adjust(left=0.08, right=0.99, top=0.80, bottom=0.27)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    outputs = []
    for suffix, kwargs in ((".svg", {}), (".pdf", {}), (".png", {"dpi": 450}), (".tiff", {"dpi": 600, "pil_kwargs": {"compression": "tiff_lzw"}})):
        path = OUT.with_suffix(suffix)
        fig.savefig(path, bbox_inches="tight", **kwargs)
        outputs.append(path)
    plt.close(fig)
    REPORT_PNG.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OUT.with_suffix(".png"), REPORT_PNG)
    source = {"figure": OUT.name, "backend": "Python/matplotlib", "claim": "C11 候选点的 R(L) 尺寸变化可视化。", "boundary": "有限尺寸诊断，不定义相界。", "source_files": [{"path": DATA.relative_to(ROOT).as_posix(), "sha256": sha256(DATA)}], "exports": [path.relative_to(ROOT).as_posix() for path in outputs], "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True}}
    (OUT.with_suffix(".sources.json")).write_text(json.dumps(source, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {"title": TITLE, "note": "仅使用本地已验收 manifest；图中误差为独立初态/数值误差，不能替代新增收敛计算。", "blocks": [{"kind": "figures", "items": [{"src": REPORT_PNG.name, "caption": "C11 候选控制点的有限尺寸诊断。左：R(L) 及误差；右：R(80)-R(60) 及合成误差。所有点来自已验收 manifest，图示不等同于相界。"}]}, {"kind": "note", "label": "解释边界", "style": "pending", "text": "候选点用于决定最少的后续收敛矩阵；若最终尺寸差仍无显著 crossing，C11 只能写成当前有限尺寸数据未见可验收内部 crossing。"}]}
    report["sections"] = [item for item in report["sections"] if item.get("title") != TITLE]
    report["sections"].insert(4, section)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(source, ensure_ascii=False))


if __name__ == "__main__":
    main()
