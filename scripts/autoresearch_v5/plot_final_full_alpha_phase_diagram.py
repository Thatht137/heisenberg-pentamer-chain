#!/usr/bin/env python3
"""绘制完整 alpha 范围的最终相图与证据面板。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--boundaries", type=Path, required=True)
    parser.add_argument("--decision", type=Path, required=True)
    parser.add_argument("--output-prefix", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def save_json(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main() -> int:
    args = parse_args()
    for path in (args.source, args.boundaries, args.decision):
        if not path.is_file():
            raise FileNotFoundError(path)
    decision = json.loads(args.decision.read_text(encoding="utf-8"))
    if decision.get("status") not in {"complete", "complete_bounded"}:
        raise ValueError("Stage D 决策未完成")
    rows, boundary_rows = read_csv(args.source), read_csv(args.boundaries)
    if not rows:
        raise ValueError("source CSV 为空")
    prefix = args.output_prefix.resolve()
    prefix.parent.mkdir(parents=True, exist_ok=True)
    outputs = {suffix: prefix.with_suffix(f".{suffix}") for suffix in ("svg", "pdf", "png", "tiff")}
    sidecars = {"sources": prefix.with_suffix(".sources.json"), "qa": prefix.with_suffix(".qa.json")}
    if any(path.exists() for path in [*outputs.values(), *sidecars.values()]):
        raise FileExistsError("最终相图输出已存在，拒绝覆盖")

    mpl.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 8.0, "axes.linewidth": 0.8,
        "xtick.direction": "out", "ytick.direction": "out", "svg.fonttype": "none",
        "pdf.fonttype": 42, "figure.dpi": 150,
    })
    fig = plt.figure(figsize=(7.2, 5.5), constrained_layout=True)
    grid = fig.add_gridspec(2, 2, width_ratios=(1.55, 1.0))
    ax_map = fig.add_subplot(grid[:, 0])
    ax_boundary = fig.add_subplot(grid[0, 1])
    ax_q = fig.add_subplot(grid[1, 1])

    ax_map.axvspan(0, 1, color="#b9d6ea", alpha=0.9, zorder=0)
    ax_map.axvspan(-1, 0, color="#f0d3a2", alpha=0.7, zorder=0)
    if boundary_rows:
        betas = np.array([float(row["beta"]) for row in boundary_rows])
        mids = np.array([float(row["alpha_mid"]) for row in boundary_rows])
        lefts = np.array([float(row["alpha_left"]) for row in boundary_rows])
        rights = np.array([float(row["alpha_right"]) for row in boundary_rows])
        order = np.argsort(betas)
        betas, mids, lefts, rights = betas[order], mids[order], lefts[order], rights[order]
        ax_map.fill_betweenx(betas, -1, mids, color="#e7a35c", alpha=0.75, zorder=1)
        ax_map.fill_betweenx(betas, mids, 0, color="#a9d2aa", alpha=0.75, zorder=1)
        ax_map.fill_betweenx(betas, lefts, rights, color="#fff2cc", hatch="///",
                             edgecolor="#c97b24", linewidth=0, zorder=2)
        ax_map.plot(mids, betas, color="#9b4d00", lw=1.5, marker="o", ms=3.0, zorder=3)
    ax_map.axvline(0, color="#333333", lw=2.0)
    ax_map.axhline(0, color="#333333", lw=1.2, ls="--")
    ax_map.text(-0.72, 0.72, "candidate IC\ncritical regime", ha="center", va="center",
                color="#7d4100", weight="bold")
    ax_map.text(-0.12, 0.72, "candidate\ncommensurate\ncritical regime", ha="center", va="center",
                color="#1f6a3a", weight="bold")
    ax_map.text(0.50, 0.68, r"$q=\pi$ gapless AF", ha="center", color="#145a96", weight="bold")
    ax_map.text(0.02, 0.08, r"$\alpha=0$ singular line", rotation=90, va="bottom", color="#333333")
    ax_map.set(xlim=(-1, 1), ylim=(0, 1), xlabel=r"$\alpha=J_2/J_1$",
               ylabel=r"$\beta=J_3/J_1$", title="a  Full working phase diagram")

    if boundary_rows:
        errors = np.array([(float(row["alpha_right"]) - float(row["alpha_left"])) / 2
                           for row in boundary_rows])[order]
        dual = np.array([row["dual_diagnostic"].lower() == "true" for row in boundary_rows])[order]
        ax_boundary.errorbar(mids[dual], betas[dual], xerr=errors[dual], fmt="o",
                             color="#9b4d00", ms=3.5, capsize=2, label="dual diagnostic")
        if np.any(~dual):
            ax_boundary.errorbar(mids[~dual], betas[~dual], xerr=errors[~dual], fmt="s",
                                 color="#777777", ms=3.5, capsize=2, label="bounded")
        ax_boundary.legend(frameon=False, fontsize=7)
    ax_boundary.axvline(0, color="#777777", lw=0.8, ls=":")
    ax_boundary.set(xlim=(-0.5, 0), ylim=(0, 1), xlabel=r"boundary $\alpha_c$",
                    ylabel=r"$\beta$", title="b  Boundary brackets")

    negative = [row for row in rows if float(row["alpha"]) < 0 and row["q_peak_over_pi"] not in {"", "None"}]
    for beta in sorted({float(row["beta"]) for row in negative}):
        selected = [row for row in negative if abs(float(row["beta"]) - beta) <= 1e-12]
        latest: dict[float, dict[str, str]] = {}
        for row in selected:
            alpha = float(row["alpha"])
            if alpha not in latest or int(row["L"]) > int(latest[alpha]["L"]):
                latest[alpha] = row
        points = [latest[alpha] for alpha in sorted(latest)]
        ax_q.plot([float(row["alpha"]) for row in points],
                  [float(row["q_peak_over_pi"]) for row in points], marker="o", ms=2.4,
                  lw=0.8, label=f"β={beta:g}")
    ax_q.axhline(1, color="#777777", lw=0.8, ls=":")
    ax_q.axhline(0.6, color="#777777", lw=0.8, ls=":")
    if len({float(row["beta"]) for row in negative}) <= 8:
        ax_q.legend(frameon=False, fontsize=6, ncol=2)
    ax_q.set(xlim=(-1, 0), ylim=(0.55, 1.03), xlabel=r"$\alpha$",
             ylabel=r"$q_{peak}/\pi$", title="c  Accepted momentum evidence")
    fig.suptitle("1×5 Heisenberg pentamer: full α phase map", fontsize=11, weight="bold")
    fig.text(0.5, 0.005, "Phase names use the permissive interpretation; numerical and boundary gates are unchanged.",
             ha="center", fontsize=7, color="#444444")
    for suffix, path in outputs.items():
        fig.savefig(path, dpi=300 if suffix in {"png", "tiff"} else None,
                    facecolor="white", bbox_inches="tight")
    plt.close(fig)

    with Image.open(outputs["png"]) as image:
        png_size = image.size
    with Image.open(outputs["tiff"]) as image:
        tiff_size = image.size
    sources = {
        "schema_version": 1, "status": "pass", "inputs": [
            {"artifact": path.resolve().relative_to(ROOT).as_posix(),
             "sha256": sha256(path), "bytes": path.stat().st_size}
            for path in (args.source, args.boundaries, args.decision)
        ],
        "outputs": [{"artifact": path.resolve().relative_to(ROOT).as_posix(),
                     "sha256": sha256(path), "bytes": path.stat().st_size}
                    for path in outputs.values()],
        "software": {"python": True, "matplotlib": mpl.__version__},
        "manual_graphics_editor": False,
    }
    save_json(sidecars["sources"], sources)
    qa = {
        "schema_version": 1, "status": "pass",
        "checks": {"all_formats": all(path.is_file() for path in outputs.values()),
                   "source_rows": len(rows) > 0, "boundary_rows": len(boundary_rows) > 0,
                   "svg_editable_text": "<text" in outputs["svg"].read_text(encoding="utf-8"),
                   "png_resolution": min(png_size) >= 1200,
                   "tiff_resolution": min(tiff_size) >= 1200},
        "metrics": {"source_rows": len(rows), "boundary_rows": len(boundary_rows),
                    "png_size": list(png_size), "tiff_size": list(tiff_size)},
    }
    if not all(qa["checks"].values()):
        qa["status"] = "fail"
    save_json(sidecars["qa"], qa)
    if qa["status"] != "pass":
        raise ValueError(f"最终相图 QA 失败: {qa['checks']}")
    print(json.dumps({"status": "pass", "source_rows": len(rows),
                      "boundary_rows": len(boundary_rows), "prefix": str(prefix)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
