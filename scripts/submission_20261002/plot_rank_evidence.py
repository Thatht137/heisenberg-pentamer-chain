"""绘制同几何对照与边界检查，不平滑或重标定原始谱权重。"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "results/novelty_20261004"
OUT = BASE / "rank_figures"


def read_csv(name):
    with (BASE / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main():
    OUT.mkdir(exist_ok=True)
    same = read_csv("same_ring_microscopic/comparisons.csv")
    sizes = read_csv("effective_size_extension/size_checks.csv")
    summary = json.loads((BASE / "same_ring_microscopic/summary.json").read_text())
    validity = json.loads((BASE / "microscopic_validity_v3/summary.json").read_text())
    parsed = subprocess.run(["py", "-3.12", "-c",
        "import json,sys,tomllib; print(json.dumps(tomllib.loads(sys.stdin.read())))"],
        input=(BASE / "effective_dmrg_refined/results.toml").read_text(),
        text=True, capture_output=True, check=True)
    refined = json.loads(parsed.stdout)
    assert summary["all_gates_pass"] and validity["all_prespecified_gates_pass"]
    plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Arial"],
        "font.size": 8, "axes.labelsize": 9, "axes.titlesize": 9,
        "axes.linewidth": .8, "axes.spines.top": False, "axes.spines.right": False,
        "legend.frameon": False, "legend.fontsize": 7, "pdf.fonttype": 42,
        "svg.fonttype": "none", "xtick.direction": "out", "ytick.direction": "out"})
    blue, red, gray = "#226A9A", "#B54A40", "#656565"
    fig, axes = plt.subplots(2, 2, figsize=(7.15, 5.4), layout="constrained")
    for ax, spin, title, color in zip(axes[0], (1.5, .5),
            (r"Local quartet: $s=3/2$", r"Local doublet: $s=1/2$"), (red, blue)):
        for mode, marker, style, label in (("fixed", "o", "--", "Fixed root"),
                                         ("retuned", "s", "-", "Linear retuning")):
            rows = [r for r in same if float(r["spin"]) == spin and r["mode"] == mode]
            ax.loglog([float(r["g"]) for r in rows], [float(r["W_low"]) for r in rows],
                      marker=marker, color=color, ls=style, ms=4, lw=1, label=label,
                      mfc="white" if mode == "fixed" else color)
        ax.set(xlabel=r"$g=\beta/\Delta_{\mathrm{loc}}$", ylabel=r"Absolute $W_{\mathrm{low}}$",
               title=title, xlim=(.004, .05))
        ax.legend(loc="upper left")
        ax.set_xticks([.005, .01, .02, .04], labels=["0.005", "0.01", "0.02", "0.04"])
        ax.tick_params(axis="x", which="minor", bottom=False, labelbottom=False)
    c, d = axes[1]
    for bc, color, marker in (("OBC", blue, "o"), ("PBC", red, "s")):
        rows = [r for r in sizes if r["boundary"] == bc]
        c.plot([int(r["cells"]) for r in rows], [float(r["retuned_W_over_beta2"]) for r in rows],
               marker=marker, ms=4, color=color, lw=.8, label=f"ED, {bc}")
    for row in refined["rows"]:
        if row["maxdim"] != 256:
            continue
        passed = row["chi_convergence_pass"] and row["variance_pass"] and row["spin_symmetry_pass"]
        c.plot(row["cells"], row["W_min"], "^" if passed else "x", color=blue if passed else gray,
               ms=5, label="DMRG, OBC (accepted)" if passed else "DMRG, OBC (not converged)")
    c.set(xlabel="Number of effective cells", ylabel=r"Minimum $W_\pi/\beta^2$",
          title="Even-chain residual at the quartet root", xticks=[4,10,20,30,40], ylim=(-.00007,.0012))
    c.ticklabel_format(axis="y", style="sci", scilimits=(0,0), useMathText=True)
    c.legend(loc="lower right")
    rows = sorted([r for r in validity["cases"] if r["seed"] == 20261005], key=lambda r:r["g"])
    d.loglog([r["g"] for r in rows], [100*r["line_vector_relative_error"] for r in rows],
             "o-", color=red, ms=4, lw=1, label="Line-vector error")
    d.loglog([r["g"] for r in rows], [100*r["weight_relative_error"] for r in rows],
             "s--", color=blue, ms=4, lw=1, label="Integrated-weight error")
    d.set(xlabel=r"$g=\beta/\Delta_{\mathrm{loc}}$", ylabel="Relative error (%)",
          title="Microscopic four-cell OBC validation", xlim=(.00045,.06), ylim=(.08,170))
    d.legend(loc="upper left")
    for label, ax in zip("abcd", axes.ravel()):
        ax.text(-.17, 1.06, label, transform=ax.transAxes, weight="bold", fontsize=11)
    for suffix in ("pdf", "svg", "png"):
        fig.savefig(OUT / f"rank_compensation.{suffix}", dpi=300)
    plt.close(fig)
    sources = [BASE / name for name in ("same_ring_microscopic/comparisons.csv",
        "same_ring_microscopic/summary.json", "effective_size_extension/size_checks.csv",
        "microscopic_validity_v3/summary.json", "effective_dmrg_refined/results.toml")]
    (OUT / "sha256.json").write_text(json.dumps({str(p.relative_to(ROOT)):
        hashlib.sha256(p.read_bytes()).hexdigest() for p in
        [Path(__file__), *sources, *sorted(OUT.glob("rank_compensation.*"))]}, indent=2)+"\n")
    print(json.dumps({"output":str(OUT),"smoothing":False,"absolute_weights":True}))


if __name__ == "__main__":
    main()
