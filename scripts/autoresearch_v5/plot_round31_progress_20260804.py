#!/usr/bin/env python3
"""绘制 round31 只读进度图，不对缺失状态做外推。"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[2]
PROGRESS = ROOT / "results/research_progress"
OUT = ROOT / "figures/round31_cv_progress_20260804"
REPORT = PROGRESS / "report.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    snapshots = sorted(PROGRESS.glob("qpi_cv_extension_remote_snapshot_20260804_*.json"))
    records = [json.loads(path.read_text(encoding="utf-8")) for path in snapshots]
    times = [datetime.fromisoformat(item["checked_at"]) for item in records]
    elapsed = [item["cells"]["cell-l40-qpi-high-100"].get("elapsed_seconds") for item in records]
    cpu = [item["cells"]["cell-l40-qpi-high-100"].get("cpu_percent") for item in records]
    completed = [item["overall"]["completed_cells"] for item in records]
    total = [item["overall"]["total_cells"] for item in records]
    hours = [(time - times[0]).total_seconds() / 3600.0 for time in times]

    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
        "font.size": 7,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.8,
        "legend.frameon": False,
    })
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.1), gridspec_kw={"width_ratios": [1.0, 1.25]})
    fig.subplots_adjust(left=0.08, right=0.96, bottom=0.24, top=0.82, wspace=0.42)

    axes[0].step(hours, completed, where="post", color="#2b6ca3", linewidth=1.8)
    axes[0].scatter(hours, completed, s=26, color="#2b6ca3", zorder=3)
    axes[0].set_ylim(-0.1, max(total) + 0.25)
    axes[0].set_yticks(range(max(total) + 1))
    axes[0].set_xlabel("Hours since first snapshot")
    axes[0].set_ylabel("Completed cells")
    axes[0].set_title("Sequential handoff", pad=8)
    axes[0].text(0.04, 0.08, "2/4; no terminal handoff", transform=axes[0].transAxes, color="#555555")

    valid_elapsed = [(x, y / 3600.0) for x, y in zip(hours, elapsed) if y is not None]
    valid_cpu = [(x, y / 100.0) for x, y in zip(hours, cpu) if y is not None]
    axes[1].plot([x for x, _ in valid_elapsed], [y for _, y in valid_elapsed], "o-", color="#c47b20", label="high-100 elapsed")
    axes[1].set_xlabel("Hours since first snapshot")
    axes[1].set_ylabel("Elapsed time (h)", color="#c47b20")
    axes[1].tick_params(axis="y", labelcolor="#c47b20")
    axes[1].set_title("Active compute evidence", pad=8)
    twin = axes[1].twinx()
    twin.plot([x for x, _ in valid_cpu], [y for _, y in valid_cpu], "s--", color="#2e8b78", label="Julia CPU")
    twin.set_ylabel("CPU equivalent (cores)", color="#2e8b78")
    twin.tick_params(axis="y", labelcolor="#2e8b78")
    lines = axes[1].lines + twin.lines
    axes[1].legend(lines, [line.get_label() for line in lines], loc="upper left")
    fig.suptitle("Round31 q=pi CV extension: active compute without terminal output", fontsize=10, fontweight="bold")
    fig.text(0.08, 0.04, "Read-only snapshots; missing measurements are not interpolated and ETA is not inferred.", color="#555555")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    for suffix, kwargs in ((".png", {"dpi": 600}), (".tiff", {"dpi": 600}), (".svg", {}), (".pdf", {})):
        fig.savefig(OUT.with_suffix(suffix), bbox_inches="tight", **kwargs)
    plt.close(fig)

    provenance = {
        "schema_version": 1,
        "figure": "round31_cv_progress_20260804",
        "backend": "Python/matplotlib",
        "conclusion": "round31 remains 2/4 while high-100 has sustained active CPU and no terminal manifest",
        "source_snapshots": [{"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(path)} for path in snapshots],
        "negative_alpha_excluded": True,
        "figure_9_excluded": True,
        "no_eta_extrapolation": True,
    }
    OUT.with_suffix(".sources.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    title = "2026-08-04 round31 只读进度图"
    section = {
        "title": title,
        "note": "用本地保存的远端只读快照绘图；不连接服务器，不把墙钟时间当作 ETA。",
        "blocks": [
            {"kind": "verdict", "status": "warn", "label": "2/4，仍等待终态", "why": "high-100 的高 CPU 活动持续存在，但没有终态 manifest，因此不能进入回传和交叉验收。"},
            {"kind": "figures", "items": [{"src": "../../figures/round31_cv_progress_20260804.png", "caption": "round31 只读进度图。左：顺序 supervisor 的已完成 cell 数；右：high-100 的实测 elapsed 与 CPU 快照。缺失测量不插值，未根据旧 cell 成本外推 ETA。"}]},
            {"kind": "kv", "pairs": [["图件来源", "figures/round31_cv_progress_20260804.sources.json"], ["范围", "0 <= alpha,beta <= 1；排除负 alpha 与 Fig.9"], ["交接门", "终态 manifest -> remote checksum -> non-clobber fetch -> validator -> accepted-only assemble -> CV--TEBD"]]},
        ],
    }
    report["sections"] = [item for item in report["sections"] if item.get("title") != title]
    report["sections"].insert(2, section)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "pass", "snapshots": len(records), "outputs": 5}, ensure_ascii=False))


if __name__ == "__main__":
    main()
