#!/usr/bin/env python3
"""分析全动量谱与五聚体有效链折叠边界。"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
SW = ROOT / "results/autoresearch_v5_20260731/round14_schrieffer_wolff/schrieffer_wolff_scan.csv"


def coefficients(alpha: float) -> dict[str, float]:
    with SW.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    row = min(rows, key=lambda item: abs(float(item["alpha"]) - alpha))
    if abs(float(row["alpha"]) - alpha) > 1e-9:
        raise SystemExit(f"缺少 alpha={alpha} 的有效理论系数")
    return {key: float(value) for key, value in row.items()}


def folded_continuum(q: np.ndarray, jeff: float) -> tuple[np.ndarray, np.ndarray]:
    k = np.mod(5.0 * q, 2.0 * np.pi)
    lower = 0.5 * np.pi * jeff * np.abs(np.sin(k))
    upper = np.pi * jeff * np.abs(np.sin(k / 2.0))
    return lower, upper


def uniform_continuum(q: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return 0.5 * np.pi * np.abs(np.sin(q)), np.pi * np.abs(np.sin(q / 2.0))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run = Path(args.run_dir).resolve()
    output = Path(args.output).resolve()
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("accepted") is not True:
        raise SystemExit("run 未通过单任务验收")
    alpha = float(manifest["params"]["alpha"])
    beta = float(manifest["params"]["beta"])
    if not 0.0 <= alpha <= 1.0 or not 0.0 <= beta <= 1.0:
        raise SystemExit("参数超出正区")
    spectrum = np.loadtxt(run / "spectrum_raw.csv", delimiter=",")
    q = np.linspace(0.0, 2.0 * np.pi, spectrum.shape[0])
    omega_max = float(manifest["settings"]["omega_max"])
    omega = np.linspace(0.0, omega_max, spectrum.shape[1])

    coeff = coefficients(alpha)
    control_ratio = beta / coeff["local_gap"]
    if math.isclose(alpha, 1.0) and math.isclose(beta, 1.0):
        lower, upper = uniform_continuum(q)
        overlay = "uniform_exact"
        controlled = True
    else:
        jeff = beta * coeff["projection_J1_over_beta"]
        lower, upper = folded_continuum(q, jeff)
        overlay = "pentamer_effective_folded"
        controlled = control_ratio <= 0.65

    figure, axis = plt.subplots(figsize=(7.2, 3.8), constrained_layout=True)
    vmax = float(np.quantile(np.maximum(spectrum, 0.0), 0.995))
    image = axis.pcolormesh(q / np.pi, omega, spectrum.T, shading="auto", cmap="magma", vmin=0.0, vmax=vmax)
    if controlled:
        axis.plot(q / np.pi, lower, color="#00BFC4", lw=1.1, label="lower boundary")
        axis.plot(q / np.pi, upper, color="white", lw=1.1, label="upper boundary")
    axis.set(xlabel=r"$q/\pi$", ylabel=r"$\omega/J_1$", xlim=(0.0, 2.0), ylim=(0.0, omega_max))
    axis.legend(frameon=False, fontsize=7) if controlled else None
    figure.colorbar(image, ax=axis, label=r"raw $S^{zz}(q,\omega)$")
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output.with_suffix(".png"), dpi=450)
    figure.savefig(output.with_suffix(".svg"))
    plt.close(figure)
    result = {
        "status": "pass",
        "alpha": alpha,
        "beta": beta,
        "overlay": overlay,
        "control_ratio_beta_over_local_gap": control_ratio,
        "effective_overlay_drawn": controlled,
        "boundary": "beta/local_gap>0.65 时不绘制有效链边界",
    }
    output.with_suffix(".json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
