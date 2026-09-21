#!/usr/bin/env python3
"""按验收 manifest 绘制 Fig.6--8，拒绝 pilot 和缺失数据。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_contract(path: Path) -> dict[str, object]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    if contract.get("status") != "production_accepted":
        raise SystemExit("仅接受 status=production_accepted 的数据契约")
    scope = contract.get("scope", {})
    if scope.get("negative_alpha_excluded") is not True or scope.get("fig9_excluded") is not True:
        raise SystemExit("范围声明未排除负 alpha 或参考 Fig.9")
    checks = contract.get("acceptance", {})
    required = {"cv_residual_pass", "tebd_convergence_pass", "peak_bracketed", "major_window_covered", "cross_method_gate_pass"}
    if not required.issubset(checks) or not all(checks.get(key) is True for key in required):
        raise SystemExit("production 验收项未全部通过")
    return contract


def source_path(root: Path, item: dict[str, object]) -> Path:
    path = (root / str(item["path"])).resolve()
    if not path.is_file():
        raise SystemExit(f"缺少源数据: {path}")
    if sha256(path) != item.get("sha256"):
        raise SystemExit(f"源数据哈希不符: {path}")
    return path


def read_columns(path: Path) -> dict[str, np.ndarray]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit(f"空数据: {path}")
    return {key: np.asarray([float(row[key]) for row in rows]) for key in rows[0]}


def configure() -> None:
    plt.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 7, "axes.linewidth": 0.8, "axes.spines.top": False,
        "axes.spines.right": False, "legend.frameon": False,
        "svg.fonttype": "none", "pdf.fonttype": 42,
    })


def plot_heatmap_grid(contract: dict[str, object], root: Path) -> plt.Figure:
    panels = contract["panels"]
    figure, axes = plt.subplots(1, len(panels), figsize=(7.2, 2.35), sharex=True, sharey=True)
    axes = np.atleast_1d(axes)
    arrays = [np.loadtxt(source_path(root, panel), delimiter=",") for panel in panels]
    vmax = max(float(np.nanmax(array)) for array in arrays)
    image = None
    for index, (axis, panel, array) in enumerate(zip(axes, panels, arrays)):
        q = np.linspace(0, 2, array.shape[0])
        omega = np.linspace(0, float(panel["omega_max"]), array.shape[1])
        image = axis.pcolormesh(q, omega, array.T, cmap="magma", shading="auto", vmin=0, vmax=vmax, rasterized=True)
        axis.set_title(str(panel["label"]))
        axis.set_xlabel(r"$q/\pi$")
        axis.text(0.04, 0.94, chr(97 + index), transform=axis.transAxes, color="white", fontweight="bold", va="top")
    axes[0].set_ylabel(r"$\omega/J_1$")
    figure.colorbar(image, ax=axes, fraction=0.025, pad=0.02, label=r"$S^{zz}(q,\omega)$")
    figure.subplots_adjust(left=0.08, right=0.90, bottom=0.20, top=0.86, wspace=0.16)
    return figure


def plot_alpha_path(contract: dict[str, object], root: Path) -> plt.Figure:
    panels = contract["panels"]
    figure, axes = plt.subplots(2, len(panels), figsize=(7.2, 4.25), sharex="row", sharey="row")
    arrays = [np.loadtxt(source_path(root, panel), delimiter=",") for panel in panels]
    vmax = max(float(np.nanmax(array)) for array in arrays)
    image = None
    for index, (panel, array) in enumerate(zip(panels, arrays)):
        q = np.linspace(0, 2, array.shape[0])
        omega = np.linspace(0, float(panel["omega_max"]), array.shape[1])
        image = axes[0, index].pcolormesh(q, omega, array.T, cmap="magma", shading="auto", vmin=0, vmax=vmax, rasterized=True)
        axes[0, index].set_title(str(panel["label"]))
        axes[0, index].set_xlabel(r"$q/\pi$")
        q_index = int(np.argmin(np.abs(q - 1)))
        axes[1, index].plot(omega, array[q_index], color="#2166ac", lw=1.2)
        axes[1, index].set_xlabel(r"$\omega/J_1$")
        axes[1, index].set_title(r"$q=\pi$ cut", fontsize=7)
        for row in range(2):
            axes[row, index].text(0.04, 0.92, chr(97 + index + row * len(panels)), transform=axes[row, index].transAxes, color="white" if row == 0 else "black", fontweight="bold", va="top")
    axes[0, 0].set_ylabel(r"$\omega/J_1$")
    axes[1, 0].set_ylabel(r"$S^{zz}(\pi,\omega)$")
    figure.colorbar(image, ax=axes[0, :], fraction=0.025, pad=0.02, label=r"$S^{zz}(q,\omega)$")
    figure.subplots_adjust(left=0.08, right=0.90, bottom=0.12, top=0.90, wspace=0.16, hspace=0.38)
    return figure


def plot_overlay(contract: dict[str, object], root: Path) -> plt.Figure:
    sources = {item["role"]: read_columns(source_path(root, item)) for item in contract["panels"]}
    required = {"cv", "tebd", "continuum"}
    if not required.issubset(sources):
        raise SystemExit("Fig.8 需要 cv、tebd、continuum 三类数据")
    figure, axis = plt.subplots(figsize=(3.6, 2.65))
    tebd, cv, continuum = sources["tebd"], sources["cv"], sources["continuum"]
    axis.plot(tebd["omega"], tebd["intensity"], color="#2166ac", lw=1.2, label="TEBD")
    axis.scatter(cv["omega"], cv["intensity"], color="#d55e00", s=16, zorder=3, label="CV")
    axis.axvspan(float(continuum["lower"][0]), float(continuum["upper"][0]), color="#7f8c8d", alpha=0.18, label="effective continuum")
    axis.set(xlabel=r"$\omega/J_1$", ylabel=r"$S^{zz}(\pi,\omega)$")
    axis.legend()
    figure.tight_layout()
    return figure


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    contract_path = Path(args.contract).resolve()
    contract = load_contract(contract_path)
    figure_id = int(contract.get("figure_id", 0))
    if figure_id not in {6, 7, 8}:
        raise SystemExit("figure_id 必须为 6、7 或 8")
    configure()
    if figure_id == 6:
        figure = plot_heatmap_grid(contract, contract_path.parent)
    elif figure_id == 7:
        figure = plot_alpha_path(contract, contract_path.parent)
    else:
        figure = plot_overlay(contract, contract_path.parent)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    for suffix, kwargs in ((".svg", {}), (".pdf", {}), (".png", {"dpi": 450}), (".tiff", {"dpi": 600})):
        figure.savefig(output.with_suffix(suffix), bbox_inches="tight", **kwargs)
    plt.close(figure)
    sidecar = {
        "schema_version": 1,
        "figure_id": figure_id,
        "contract": str(contract_path),
        "contract_sha256": sha256(contract_path),
        "inputs": [{"role": item.get("role"), "label": item.get("label"), "path": item["path"], "sha256": item["sha256"]} for item in contract["panels"]],
        "acceptance": contract["acceptance"],
        "outputs": {suffix: sha256(output.with_suffix(suffix)) for suffix in (".svg", ".pdf", ".png", ".tiff")},
    }
    output.with_suffix(".sources.json").write_text(json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "pass", "figure_id": figure_id, "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
