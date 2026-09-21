"""绘制已回传 CV 扩展 cell 的强度、残差和求解成本诊断。"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results/autoresearch_v5_20260803/round31_qpi_cv_extension_completed_cells_20260804"
OUT = ROOT / "figures/qpi_cv_extension_residual_cost_diagnostic_20260804"
REPORT_PNG = ROOT / "results/research_progress/qpi_cv_extension_residual_cost_diagnostic_20260804.png"
REPORT = ROOT / "results/research_progress/report.json"
TITLE = "2026-08-04 round31 CV 扩展残差—成本离线诊断"
CELLS = ("cell-l40-qpi-low-000-020", "cell-l40-qpi-high-055")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_rows() -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    for cell in CELLS:
        path = RUN / cell / "spectrum.csv"
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                rows.append(
                    {
                        "cell": cell,
                        "omega": float(row["omega"]),
                        "intensity": float(row["intensity"]),
                        "residual": float(row["relative_residual"]),
                        "solve_seconds": float(row["solve_seconds"]),
                        "solution_maxdim": float(row["solution_maxdim"]),
                    }
                )
    return sorted(rows, key=lambda row: float(row["omega"]))


def main() -> None:
    rows = load_rows()
    omega = np.array([float(row["omega"]) for row in rows])
    intensity = np.array([float(row["intensity"]) for row in rows])
    residual = np.array([float(row["residual"]) for row in rows])
    minutes = np.array([float(row["solve_seconds"]) for row in rows]) / 60.0
    accepted = residual <= 1e-5
    if not np.all(np.isfinite(np.concatenate((omega, intensity, residual, minutes)))):
        raise SystemExit("诊断数据含非有限值")

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "DejaVu Sans", "Liberation Sans"],
            "font.size": 7.5,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "axes.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "legend.frameon": False,
        }
    )
    colors = np.where(accepted, "#238B45", "#D7301F")
    fig, axes = plt.subplots(1, 3, figsize=(7.4, 2.9), gridspec_kw={"wspace": 0.42})
    for axis in axes:
        axis.grid(axis="y", color="#D9D9D9", linewidth=0.45, alpha=0.65)
        axis.tick_params(width=0.7, length=3, pad=2)

    axes[0].plot(omega, intensity, color="#2166AC", linewidth=1.4, zorder=1)
    axes[0].scatter(omega, intensity, c=colors, edgecolor="white", linewidth=0.5, s=30, zorder=2)
    axes[0].set_xlabel(r"$\omega/J_1$ at $q=\pi$")
    axes[0].set_ylabel(r"$S(q,\omega)$")
    axes[0].set_title("signal", fontsize=8)

    axes[1].axhspan(0.0, 1e-5, color="#DDF3DE", alpha=0.8)
    axes[1].axhline(1e-5, color="#B64342", linestyle="--", linewidth=0.9)
    axes[1].plot(omega, residual, color="#42949E", linewidth=1.2, zorder=1)
    axes[1].scatter(omega, residual, c=colors, edgecolor="white", linewidth=0.5, s=30, zorder=2)
    axes[1].set_xlabel(r"$\omega/J_1$")
    axes[1].set_ylabel("relative CV residual")
    axes[1].set_title("acceptance gate", fontsize=8)
    axes[1].ticklabel_format(axis="y", style="sci", scilimits=(0, 0))

    axes[2].plot(omega, minutes, color="#B64342", linewidth=1.3, zorder=1)
    axes[2].scatter(omega, minutes, c=colors, edgecolor="white", linewidth=0.5, s=30, zorder=2)
    axes[2].set_xlabel(r"$\omega/J_1$")
    axes[2].set_ylabel("CV solve time (min)")
    axes[2].set_title("cost", fontsize=8)
    for axis, label in zip(axes, ("a", "b", "c")):
        axis.text(-0.14, 1.04, label, transform=axis.transAxes, fontsize=9, fontweight="bold")

    fig.suptitle("Round31 q=π CV extension: residual-limited low-frequency region", fontsize=9.5, fontweight="bold", x=0.02, ha="left")
    fig.text(0.02, 0.015, "alpha=0.23, beta=0.5, L=40, eta=0.1; green=accepted, red=residual > 10^-5; diagnostic only", fontsize=6.4, color="#4D4D4D")
    fig.subplots_adjust(left=0.08, right=0.99, top=0.80, bottom=0.24)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    outputs = []
    for suffix, kwargs in ((".svg", {}), (".pdf", {}), (".png", {"dpi": 450}), (".tiff", {"dpi": 600, "pil_kwargs": {"compression": "tiff_lzw"}})):
        path = OUT.with_suffix(suffix)
        fig.savefig(path, bbox_inches="tight", **kwargs)
        outputs.append(path)
    plt.close(fig)
    REPORT_PNG.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OUT.with_suffix(".png"), REPORT_PNG)

    source_files = [RUN / cell / "spectrum.csv" for cell in CELLS]
    source_files += [RUN / cell / "manifest.json" for cell in CELLS]
    source = {
        "figure": OUT.name,
        "backend": "Python/matplotlib",
        "claim": "低频 CV cell 的强度仍为正，但 residual 门在 ω=0.00–0.10 失败；ω=0.15、0.20 和 0.55 通过。",
        "boundary": "诊断图，不替代 CV–TEBD 交叉门，也不把低频失败点当作生产谱。",
        "scope": {"alpha": 0.23, "beta": 0.5, "L": 40, "q": "pi", "negative_alpha_excluded": True, "fig9_excluded": True},
        "acceptance": {
            "points": len(rows),
            "accepted_points": int(accepted.sum()),
            "failed_points": int((~accepted).sum()),
            "max_residual": float(residual.max()),
            "omega_failed": [float(value) for value in omega[~accepted]],
            "max_solve_minutes": float(minutes.max()),
        },
        "source_files": [{"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)} for path in source_files],
        "exports": [path.relative_to(ROOT).as_posix() for path in outputs],
    }
    (OUT.with_suffix(".sources.json")).write_text(json.dumps(source, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "仅使用已回传的 round31 两个 CV cell；不连接服务器、不启动新计算。",
        "blocks": [
            {"kind": "verdict", "status": "warn", "label": "诊断完成，动态门仍未关闭", "why": "6 个频点中 3 个通过 residual 门；omega=0.00、0.05、0.10 仍超过 1e-5。"},
            {"kind": "figures", "items": [{"src": REPORT_PNG.name, "caption": "Round31 q=pi CV 扩展的离线诊断。左：正强度；中：residual 门；右：线性求解成本。绿色点通过 residual<=1e-5，红色点为低频失败点。"}]},
            {"kind": "table", "columns": ["频率范围", "点数", "状态", "说明"], "rows": [["0.00–0.10", "3", "失败", "residual 1.07e-5–1.32e-5"], ["0.15–0.20", "2", "通过", "低频末端已达门槛"], ["0.55", "1", "通过", "高频锚点通过"]]},
            {"kind": "note", "label": "验收边界", "style": "pending", "text": "这张图只用于 retry 优先级和成本判断；不把低频失败点用于 CV–TEBD Agreement，也不替代 omega≈0.05 主峰和完整 [0,1.5] 积分窗覆盖。"},
        ],
    }
    report["sections"] = [item for item in report["sections"] if item.get("title") != TITLE]
    report["sections"].insert(2, section)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(source, ensure_ascii=False))


if __name__ == "__main__":
    main()
