#!/usr/bin/env python3
"""按 round43 交接结果绘制 bounded 或 production Fig.8。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.text import Text


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CV = ROOT / "results/autoresearch_v5_20260805/round40_qpi_cv_anchor_assembly_accepted"
DEFAULT_CROSS = ROOT / "results/autoresearch_v5_20260805/round40_cv_tebd_accepted7_analysis/cross-method-check.json"
DEFAULT_TEBD = ROOT / "results/autoresearch_v5_20260803/round26_qpi_tebd_production/cell-alpha023-qpi-dt00125-t30"
PROJECTION = ROOT / "results/autoresearch_v3_20260729/round1_doublet_projection/representative.csv"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def verify_checksums(root: Path) -> None:
    ledger = root / "checksums.sha256"
    if not ledger.is_file():
        raise ValueError("handoff 缺少 checksums.sha256")
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split(maxsplit=1)
        target = (root / relative).resolve()
        target.relative_to(root.resolve())
        if not target.is_file() or sha256(target) != expected:
            raise ValueError(f"handoff checksum 失败: {relative}")


def select_mode(summary: dict[str, object]) -> str:
    production = summary.get("production_ready") is True
    if production:
        if summary.get("status") != "production_ready" or summary.get("tag") != "Agreement":
            raise ValueError("production 标志与 Agreement 不一致")
        return "production"
    if summary.get("tag") not in {"NotEvaluable", "Disagreement"}:
        raise ValueError("bounded 状态缺少有效交叉标签")
    return "bounded"


def configure() -> None:
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 7,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "legend.frameon": False,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "axes.unicode_minus": False,
    })


def output_paths(base: Path) -> dict[str, Path]:
    return {suffix: base.with_suffix(suffix) for suffix in (".svg", ".pdf", ".png", ".tiff")}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--handoff-root", required=True)
    parser.add_argument("--output-base", required=True)
    parser.add_argument("--tebd-dir", default=str(DEFAULT_TEBD))
    args = parser.parse_args()

    handoff = Path(args.handoff_root).resolve()
    output = Path(args.output_base).resolve()
    outputs = output_paths(output)
    sidecar_path = output.with_suffix(".sources.json")
    data_path = output.with_suffix(".source.csv")
    qa_path = output.with_suffix(".qa.json")
    existing = [path for path in [*outputs.values(), sidecar_path, data_path, qa_path] if path.exists()]
    if existing:
        raise SystemExit(f"拒绝覆盖已有 Fig.8 输出: {existing}")
    verify_checksums(handoff)
    summary = read_json(handoff / "handoff_summary.json")
    mode = select_mode(summary)

    if mode == "production":
        cv_dir = handoff / "accepted11"
        cross_path = handoff / "cross_method/cross-method-check.json"
    else:
        cv_dir = DEFAULT_CV
        cross_path = DEFAULT_CROSS
    cross = read_json(cross_path)
    if mode == "production" and (cross.get("status") != "pass" or cross.get("tag") != "Agreement"):
        raise SystemExit("production cross-method 证据不完整")
    if mode == "bounded" and cross.get("tag") != "NotEvaluable":
        raise SystemExit("bounded 分支必须保留 NotEvaluable")

    cv_rows = read_rows(cv_dir / "spectrum.csv")
    cv_omega = np.asarray([float(row["omega"]) for row in cv_rows])
    cv_value = np.asarray([float(row["intensity"]) for row in cv_rows])
    cv_residual = np.asarray([float(row["relative_residual"]) for row in cv_rows])
    if list(cv_omega) != sorted(cv_omega) or cv_residual.max() > 1e-5:
        raise SystemExit("CV 网格或 residual 不满足绘图合同")

    tebd_dir = Path(args.tebd_dir).resolve()
    tebd_rows = read_rows(tebd_dir / "spectrum.csv")
    tebd_omega = np.asarray([float(row["omega"]) for row in tebd_rows])
    tebd_value = np.asarray([float(row["intensity"]) for row in tebd_rows])
    tebd_shared = np.interp(cv_omega, tebd_omega, tebd_value)
    relative = np.abs(tebd_shared - cv_value) / np.maximum(np.abs(cv_value), 1e-30)
    expected = np.asarray(cross["diagnostics"]["shared_point_relative_differences"])
    if expected.shape != relative.shape or not np.allclose(relative, expected, rtol=1e-10, atol=1e-12):
        raise SystemExit("绘图数据与 cross-method 诊断不一致")

    projection = next(
        row for row in read_rows(PROJECTION)
        if math.isclose(float(row["alpha"]), 0.23, rel_tol=0.0, abs_tol=1e-12)
    )
    continuum_upper = math.pi * 0.5 * float(projection["jeff_over_beta"])
    gates = [
        ("peak bracket", bool(cross["coverage"]["main_peak_bracketed_by_cv_grid"])),
        ("weight window", bool(cross["coverage"]["major_weight_window_covered_by_cv_grid"])),
        ("peak budget", bool(cross["checks"]["peak_delta_le_budget"])),
        ("weight budget", bool(cross["checks"]["major_weight_delta_le_budget"])),
    ]
    if mode == "production" and not all(value for _, value in gates):
        raise SystemExit("production 分支存在未通过验收门")

    output.parent.mkdir(parents=True, exist_ok=True)
    with data_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["omega", "cv_intensity", "tebd_intensity", "relative_delta", "cv_residual", "accepted"])
        for values in zip(cv_omega, cv_value, tebd_shared, relative, cv_residual):
            writer.writerow([*values, True])

    configure()
    figure = plt.figure(figsize=(3.39, 3.78), constrained_layout=True)
    grid = figure.add_gridspec(3, 1, height_ratios=(2.35, 0.95, 0.42), hspace=0.08)
    main_axis = figure.add_subplot(grid[0])
    delta_axis = figure.add_subplot(grid[1], sharex=main_axis)
    gate_axis = figure.add_subplot(grid[2])

    main_axis.axvspan(0.0, continuum_upper, color="#dce8df", alpha=0.72, label="effective window")
    main_axis.plot(tebd_omega, tebd_value, color="#276b8e", lw=1.35, label="TEBD")
    main_axis.scatter(cv_omega, cv_value, s=24, color="#c75b2a", edgecolor="white", linewidth=0.45, zorder=4, label="accepted CV")
    main_axis.set_ylabel(r"$S^{zz}(q=\pi,\omega)$")
    main_axis.set_xlim(0.0, 1.55)
    main_axis.set_ylim(bottom=0.0)
    main_axis.legend(loc="upper right", fontsize=5.2, handlelength=1.4, borderaxespad=0.35)
    main_axis.text(0.02, 0.96, "a", transform=main_axis.transAxes, va="top", fontweight="bold", fontsize=8)
    status_color = "#17715a" if mode == "production" else "#9a5b09"
    main_axis.text(0.04, 0.80, "Agreement" if mode == "production" else "bounded · NotEvaluable", transform=main_axis.transAxes, fontsize=6.3, color=status_color)
    main_axis.tick_params(labelbottom=False)

    delta_axis.axhspan(0.0, 0.15, color="#edf3ef", zorder=0)
    delta_axis.axhline(0.15, color="#65756a", lw=0.85, ls="--")
    delta_axis.scatter(cv_omega, relative, s=20, color="#604f8a", zorder=3)
    delta_axis.set_xlabel(r"$\omega/J_1$")
    delta_axis.set_ylabel("relative\ndifference")
    delta_axis.set_ylim(0.0, max(0.17, float(relative.max()) * 1.18))
    delta_axis.text(0.02, 0.92, "b", transform=delta_axis.transAxes, va="top", fontweight="bold", fontsize=8)
    delta_axis.text(0.98, 0.90, f"max {100 * relative.max():.2f}%", transform=delta_axis.transAxes, ha="right", va="top", fontsize=6.2)

    gate_axis.set_axis_off()
    gate_axis.text(0.0, 0.88, "c", transform=gate_axis.transAxes, va="top", fontweight="bold", fontsize=8)
    for index, (label, passed) in enumerate(gates):
        left = 0.08 + index * 0.23
        color = "#17715a" if passed else "#a33838"
        gate_axis.text(left, 0.52, "PASS" if passed else "OPEN", color=color, weight="bold", fontsize=6.0, ha="center", va="center")
        gate_axis.text(left, 0.10, label, color="#4d5965", fontsize=5.2, ha="center", va="center")

    for suffix, path in outputs.items():
        kwargs: dict[str, object] = {}
        if suffix == ".png":
            kwargs["dpi"] = 450
        elif suffix == ".tiff":
            kwargs.update({"dpi": 600, "pil_kwargs": {"compression": "tiff_lzw"}})
        figure.savefig(path, bbox_inches="tight", **kwargs)
    min_font = min(text.get_fontsize() for text in figure.findobj(Text) if text.get_text())
    plt.close(figure)

    sources = [
        handoff / "handoff_summary.json",
        handoff / "checksums.sha256",
        cv_dir / "spectrum.csv",
        cv_dir / "manifest.json",
        cross_path,
        tebd_dir / "spectrum.csv",
        tebd_dir / "manifest.json",
        PROJECTION,
        data_path,
    ]
    sidecar = {
        "schema_version": 1,
        "figure_id": 8,
        "status": "production_agreement" if mode == "production" else "bounded_not_evaluable",
        "backend": "Python/matplotlib",
        "archetype": "quantitative grid",
        "final_size_mm": [89, 99],
        "core_conclusion": (
            "11 个 accepted CV 点关闭低频覆盖门，并通过与 TEBD 的峰位和积分权重验收。"
            if mode == "production"
            else "当前证据未关闭全部动态门，因此 Fig.8 保持 bounded 且不升级谱归属。"
        ),
        "acceptance": {"production_ready": mode == "production", "gates": dict(gates)},
        "source_files": [{"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(path)} for path in sources],
        "outputs": {suffix: sha256(path) for suffix, path in outputs.items()},
        "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True},
    }
    sidecar_path.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    png = plt.imread(outputs[".png"])
    svg_text = outputs[".svg"].read_text(encoding="utf-8")
    qa = {
        "schema_version": 1,
        "status": "pass",
        "checks": {
            "all_exports": all(path.stat().st_size > 1000 for path in outputs.values()),
            "editable_svg_text": "<text" in svg_text,
            "nonblank_png": float(np.std(png)) > 0.01,
            "minimum_font_pt": min_font >= 5.0,
            "source_data": data_path.is_file(),
            "scope": sidecar["scope"]["negative_alpha_excluded"] and sidecar["scope"]["fig9_excluded"],
            "branch_guard": sidecar["acceptance"]["production_ready"] == (mode == "production"),
        },
        "min_font_pt": min_font,
        "png_std": float(np.std(png)),
    }
    qa["status"] = "pass" if all(qa["checks"].values()) else "fail"
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": qa["status"], "mode": mode, "output": str(output)}, ensure_ascii=False))
    if qa["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
