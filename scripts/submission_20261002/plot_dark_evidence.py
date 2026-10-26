"""从已验证数据绘制抵消点证据，不平滑或修改谱线。"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import dark_operator_expansion as dark
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = dark.ROOT
BASE = ROOT / "results/novelty_20261004"
OUT = BASE / "evidence_figures"


def read(relative):
    with (BASE / relative).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    summary = json.loads((BASE / "microscopic_retuning_v2/summary.json").read_text())
    assert summary["all_pass"]
    first = read("microscopic_four_cells/comparisons.csv")
    second = read("microscopic_retuning_v2/comparisons.csv")
    sizes = read("effective_size_extension/size_checks.csv")
    theory = [r for r in read("dark_operator/effective_spectra.csv")
              if r["cells"] == "4" and r["boundary"] == "OBC"]
    micro = [r for r in read("microscopic_retuning_v2/spectral_lines.csv")
             if r["mode"] == "retuned" and float(r["g"]) == 0.0025 and int(r["level"]) < 44]
    beta = next(float(r["beta"]) for r in second if r["mode"] == "retuned" and float(r["g"]) == 0.0025)
    alpha = np.linspace(-1.1, -.5, 241)
    x = (-3+np.sqrt(9-4*alpha*(2-alpha)))/(2*(2-alpha))
    amplitude = -1/3+8/(3*(6*x*x+8*x+6))
    for i in range(0, len(alpha), 40):
        cell, _, _ = dark.reference.local_projection(alpha[i], np.linspace(0, 2*np.pi, 41))
        assert abs(amplitude[i]-np.dot(cell["c"], [1,-1,1,-1,1])) < 1e-12
    dark.reference.write_csv(OUT / "local_amplitude.csv", [
        {"alpha": float(a), "A_pi": float(v)} for a, v in zip(alpha, amplitude)])
    plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Arial"],
        "font.size": 8, "axes.labelsize": 9, "axes.titlesize": 9,
        "axes.linewidth": .8, "axes.spines.top": False, "axes.spines.right": False,
        "legend.frameon": False, "legend.fontsize": 7, "pdf.fonttype": 42,
        "svg.fonttype": "none", "xtick.direction": "out", "ytick.direction": "out"})
    blue, red, gray = "#226A9A", "#B54A40", "#656565"
    fig, axes = plt.subplots(2, 2, figsize=(7.15, 5.45), layout="constrained")
    a, b, c, d = axes.ravel()
    a.plot(alpha, amplitude, color=blue, lw=1.5)
    a.axhline(0, color=gray, lw=.7)
    a.plot(dark.ALPHA, 0, "o", color=red, ms=4)
    a.annotate(r"$\alpha_*=-(2+\sqrt{7})/6$", (dark.ALPHA, 0),
               xytext=(-1.08, .014), arrowprops={"arrowstyle": "->", "lw": .7}, fontsize=8)
    a.set(xlabel=r"$\alpha=J_2/J_1$", ylabel=r"Local amplitude $A_\pi$",
          title="Local cancellation", xlim=(-1.1, -.5))
    for mode, color, marker, label in (("fixed", blue, "o", "Fixed cancellation point"),
                                      ("retuned", red, "s", "Retuned point")):
        rows = [r for r in second if r["mode"] == mode]+(first if mode == "fixed" else [])
        rows.sort(key=lambda r: float(r["g"]))
        b.plot([float(r["g"]) for r in rows], [100*float(r["relative_error"]) for r in rows],
               marker=marker, color=color, ms=4, lw=1, label=label)
    b.axhline(5, color=gray, lw=.8, ls=":", label="Prespecified 5% gate")
    b.set(xlabel=r"$g=\beta/\Delta_{\mathrm{local}}$", ylabel="Weight error (%)",
          title="Microscopic four-cell check", ylim=(0, 15), xlim=(0, .021))
    b.legend(loc="upper left")
    tx = np.array([float(r["omega_over_beta"]) for r in theory])
    ty = np.array([float(r["perpendicular_weight"]) for r in theory])
    mx = np.array([float(r["omega"])/beta for r in micro])
    my = np.array([float(r["W_pi"])/beta**2 for r in micro])
    c.vlines(tx, 0, ty, color=blue, lw=1.1)
    c.plot(tx, ty, "o", color=blue, ms=4, mfc="white", label="Leading effective probe")
    c.vlines(mx, 0, my, color=red, lw=.7, linestyles="dashed")
    c.plot(mx, my, "+", color=red, ms=5, label="Microscopic ED, retuned")
    c.set(xlabel=r"$\omega/\beta$", ylabel=r"Line weight / $\beta^2$",
          title="Residual spectrum after retuning", xlim=(0, 1.3), ylim=(-1e-5, 3.35e-4))
    c.ticklabel_format(axis="y", style="sci", scilimits=(0,0), useMathText=True)
    c.legend(loc="upper right")
    for bc, color, marker in (("OBC", blue, "o"), ("PBC", red, "s")):
        rows = [r for r in sizes if r["boundary"] == bc]
        d.plot([int(r["cells"]) for r in rows], [float(r["retuned_W_over_beta2"]) for r in rows],
               marker=marker, color=color, ms=4, lw=1, label=bc)
    d.set(xlabel="Number of effective cells", ylabel=r"Minimum $W_\pi/\beta^2$",
          title="Size and boundary checks", xticks=[4,6,8,10], ylim=(-.00005, .00115))
    d.ticklabel_format(axis="y", style="sci", scilimits=(0,0), useMathText=True)
    d.legend(loc="lower right")
    for label, ax in zip("abcd", axes.ravel()):
        ax.text(-.18, 1.06, label, transform=ax.transAxes, weight="bold", fontsize=11)
    for suffix in ("pdf", "svg", "png"):
        fig.savefig(OUT / f"dark_probe_evidence.{suffix}", dpi=300)
    plt.close(fig)
    comparison = {
        "spectral_vector_relative_error_by_sorted_low_energy_level": float(np.linalg.norm(my-ty)/np.linalg.norm(ty)),
        "max_energy_difference_over_beta": float(np.max(abs(mx-tx))),
        "sum_ed": float(my.sum()), "sum_prediction": float(ty.sum()),
        "matching": "sorted first 44 Sz0 levels; finite four-cell OBC, g=.0025, not bulk",
        "smoothing": False, "rescaling_each_line": False,
    }
    dark.reference.write_json(OUT / "spectral_comparison.json", comparison)
    sources = [BASE / p for p in (
        "microscopic_four_cells/comparisons.csv", "microscopic_retuning_v2/comparisons.csv",
        "microscopic_retuning_v2/spectral_lines.csv", "effective_size_extension/size_checks.csv",
        "dark_operator/effective_spectra.csv")]
    dark.reference.write_json(OUT / "sha256.json", {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [Path(__file__)] + sources + sorted(OUT.iterdir()) if p.is_file()})
    print(comparison)


if __name__ == "__main__":
    main()
