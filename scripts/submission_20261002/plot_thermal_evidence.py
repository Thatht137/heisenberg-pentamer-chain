"""绘制热消光证据与有限动量窗口限制。"""

import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "results/novelty_20261008"
OUT = DATA / "figures"


def read_rows(path):
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def main():
    OUT.mkdir(exist_ok=True)
    sources = [DATA/"thermal_compensation/thermal_weights.csv",
               DATA/"thermal_microscopic_two_cells/comparisons.csv",
               DATA/"momentum_acceptance_v2/acceptance_weights.csv"]
    thermal, micro, acceptance = [read_rows(p) for p in sources]
    contract = {"conclusion": "ideal retuned thermal responses differ, but momentum averaging can mask the doublet scaling",
                "panels": ["effective N=4,6 thermal minimum", "microscopic two-cell weak-coupling scaling",
                           "microscopic finite momentum acceptance limitation"],
                "backend": "existing project Python/matplotlib workflow",
                "archetype": "quantitative grid", "dimensions_inches": [7.2, 2.7],
                "smoothing": "none", "interpolation": "straight segments between computed points only",
                "log_axes": "explicitly labelled; no change to source data",
                "error_bars": "deterministic finite-size ED; no statistical error bars",
                "scope": "not a thermodynamic-limit or instrument-feasibility figure"}
    (OUT/"figure_contract.json").write_text(json.dumps(contract, indent=2), encoding="utf-8")
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8,
        "axes.labelsize": 9, "axes.linewidth": .7, "lines.linewidth": 1.25,
        "lines.markersize": 4, "legend.fontsize": 7, "legend.frameon": False,
        "axes.spines.top": False, "axes.spines.right": False,
        "pdf.fonttype": 42, "svg.fonttype": "none"})
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.7))
    fig.subplots_adjust(left=.10, right=.985, bottom=.225, top=.87, wspace=.63)
    quartet, doublet = "#C45B3D", "#2878A2"
    a, b, c = axes
    for n, color, marker in ((4, quartet, "o"), (6, quartet, "s")):
        rows = [r for r in thermal if float(r["spin"]) == 1.5 and int(r["cells"]) == n
                and float(r["T_over_Jeff"]) <= 3.2]
        a.plot([float(r["T_over_Jeff"]) for r in rows], [1000*float(r["C_min"]) for r in rows],
               marker=marker, color=color, label=rf"$s=3/2,\ N={n}$",
               mfc="white" if n == 4 else quartet, ls="-" if n == 4 else ":")
    a.axhline(0, color=doublet, ls="--", label=r"$s=1/2,\ N=4,6$")
    a.set(xlabel=r"$T/J_{\rm eff}$", ylabel=r"$10^3 C_{\min}$", xlim=(0, 3.3), ylim=(-.5, 16.5))
    a.set_xticks([0, 1.6, 3.2])
    a.legend(loc="upper left", handlelength=1.5, borderaxespad=.25)
    for spin, color, marker in ((1.5, quartet, "o"), (.5, doublet, "s")):
        rows = [r for r in micro if float(r["spin"]) == spin and float(r["T_over_Jeff"]) == 1.6]
        rows.sort(key=lambda r: float(r["g"]))
        values = np.array([float(r["W_positive_low"]) for r in rows])
        b.loglog([float(r["g"]) for r in rows], values/values[0], marker=marker,
                 color=color, label=rf"$s={('3/2' if spin == 1.5 else '1/2')}$", mfc="white")
        rows = [r for r in acceptance if float(r["spin"]) == spin and float(r["T_over_Jeff"]) == 1.6
                and float(r["g"]) == .005 and float(r["half_width_over_pi"]) > 0]
        c.loglog([float(r["half_width_over_pi"]) for r in rows],
                 [float(r["ratio_to_ideal"]) for r in rows], marker=marker,
                 color=color, label=rf"$s={('3/2' if spin == 1.5 else '1/2')}$", mfc="white")
    b.set(xlabel=r"$g=\beta/\Delta_{\rm loc}$", ylabel=r"$W_+(g)/W_+(0.005)$",
          xlim=(.0045, .023), ylim=(.7, 400))
    b.set_xticks([.005, .01, .02], ["0.005", "0.01", "0.02"])
    b.set_yticks([1, 10, 100])
    b.minorticks_off()
    b.legend(loc="upper left")
    c.set(xlabel=r"$\delta q/\pi$", ylabel=r"$\overline{W}_+/W_+(q_0)$", xlim=(6e-7, .018), ylim=(.6, 1e9))
    c.set_xticks([1e-6, 1e-4, 1e-2])
    c.set_yticks([1, 1e3, 1e6, 1e9])
    c.minorticks_off()
    c.legend(loc="upper left")
    for label, axis in zip("abc", axes):
        axis.text(-.22, 1.06, label, transform=axis.transAxes, fontweight="bold", fontsize=10)
        axis.tick_params(direction="out", length=3, pad=3)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    bounds = fig.bbox
    outside = []
    for text in fig.findobj(matplotlib.text.Text):
        if text.get_visible() and text.get_text():
            box = text.get_window_extent(renderer)
            if box.x0 < -1 or box.y0 < -1 or box.x1 > bounds.x1+1 or box.y1 > bounds.y1+1:
                outside.append(text.get_text())
    assert not outside, outside
    for extension in ("pdf", "svg", "png", "tiff"):
        fig.savefig(OUT/f"thermal_evidence.{extension}", dpi=600 if extension == "tiff" else 240)
    plt.close(fig)
    qa = {"text_outside_canvas": outside, "data_modified": False,
          "gaussian_smoothing": False, "model_sources_separated_by_panel": True}
    (OUT/"qa.json").write_text(json.dumps(qa, indent=2), encoding="utf-8")
    files = [Path(__file__), *sources, *sorted(OUT.iterdir())]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in files if p.is_file() and p.name != "sha256.json"}
    (OUT/"sha256.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")
    print(json.dumps(qa))


if __name__ == "__main__":
    main()
