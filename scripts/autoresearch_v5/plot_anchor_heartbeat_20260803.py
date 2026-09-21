"""绘制 L=80 anchor 的运行心跳诊断图。"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_DIR = ROOT / "results" / "research_progress"
FIGURE_DIR = ROOT / "figures"
NAME = "anchor_heartbeat_20260803"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def elapsed_hours(value: str) -> float:
    parts = [int(item) for item in value.split(":")]
    if len(parts) == 3:
        hours, minutes, seconds = parts
    elif len(parts) == 2:
        hours = 0
        minutes, seconds = parts
    else:
        raise ValueError(f"无法解析运行时长: {value}")
    return hours + minutes / 60.0 + seconds / 3600.0


def load_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in sorted(SNAPSHOT_DIR.glob("server_*snapshot_20260803_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        anchor = data.get("anchor", {})
        if "cpu_percent" not in anchor or "elapsed" not in anchor:
            continue
        rows.append(
            {
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "timestamp": data["timestamp"],
                "elapsed_hours": elapsed_hours(str(anchor["elapsed"])),
                "cpu_percent": float(anchor["cpu_percent"]),
                "points": int(anchor.get("points_present", anchor.get("cv_points_present", 0))),
                "tebd_started": data.get("tebd", {}).get("status") not in {"not_started", None},
            }
        )
    if not rows:
        raise SystemExit("没有可用的 anchor 快照")
    return rows


def main() -> None:
    rows = load_rows()
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    x = [float(row["elapsed_hours"]) for row in rows]
    cpu = [float(row["cpu_percent"]) for row in rows]
    points = [int(row["points"]) for row in rows]
    labels = [datetime.fromisoformat(str(row["timestamp"])).strftime("%H:%M") for row in rows]

    plt.rcParams.update({"font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9})
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.2), constrained_layout=True)

    axes[0].plot(x, cpu, color="#0b7285", marker="o", linewidth=1.8, markersize=4)
    axes[0].set_title("Anchor CPU heartbeat")
    axes[0].set_xlabel("Elapsed wall time (h)")
    axes[0].set_ylabel("Julia CPU (%)")
    axes[0].grid(True, alpha=0.25)
    axes[0].set_ylim(0, max(cpu) * 1.12)
    for index, (xpos, ypos, label) in enumerate(zip(x, cpu, labels)):
        # 交错标签，避免密集快照互相遮挡。
        offset = 8 if index % 2 == 0 else -14
        axes[0].annotate(
            label,
            (xpos, ypos),
            xytext=(0, offset),
            textcoords="offset points",
            ha="center",
            va="bottom" if offset > 0 else "top",
            fontsize=6.5,
        )

    axes[1].step(x, points, where="post", color="#d9480f", linewidth=2, label="CV points")
    axes[1].axhline(0, color="#495057", linewidth=0.8)
    axes[1].set_title("Output availability")
    axes[1].set_xlabel("Elapsed wall time (h)")
    axes[1].set_ylabel("Completed points")
    axes[1].set_ylim(-0.05, 1.0)
    axes[1].set_yticks([0, 1])
    axes[1].set_yticklabels(["none", "present"])
    axes[1].text(0.02, 0.86, "TEBD: not started", transform=axes[1].transAxes, fontsize=8, color="#842029")
    axes[1].grid(True, axis="x", alpha=0.25)

    fig.suptitle("1x5 pentamer L=80 CV anchor · 2026-08-03", fontsize=11)
    for suffix in ("png", "svg", "pdf"):
        fig.savefig(FIGURE_DIR / f"{NAME}.{suffix}", dpi=220 if suffix == "png" else None, bbox_inches="tight")
    plt.close(fig)

    source = {
        "schema_version": 1,
        "figure": NAME,
        "sources": [{"path": row["path"], "sha256": sha256(ROOT / str(row["path"]))} for row in rows],
        "interpretation": "CPU 心跳持续而 CV points 尚未写出；TEBD 尚未启动。该图是运行诊断，不是物理结果。",
        "negative_alpha_excluded": True,
    }
    (FIGURE_DIR / f"{NAME}.sources.json").write_text(
        json.dumps(source, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"figure": NAME, "snapshots": len(rows), "cpu_range": [min(cpu), max(cpu)]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
