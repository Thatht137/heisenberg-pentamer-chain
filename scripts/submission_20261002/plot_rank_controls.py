"""绘制局域机制与周期链对照，保留未收敛标记。"""

import csv
import hashlib
import json
import subprocess
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "results/novelty_20261004"
OUT = BASE / "rank_controls_figure"


def csv_rows(name):
    with (BASE / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def toml_rows(name):
    result = subprocess.run(["py", "-3.12", "-c",
        "import json,sys,tomllib; print(json.dumps(tomllib.loads(sys.stdin.read())))"],
        input=(BASE / name).read_text(), text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


def main():
    family = csv_rows("compensation_family/roots.csv")
    even = csv_rows("rank_even_effective/comparisons.csv")
    channels = json.loads((BASE/"bond_spin_channels_v2/summary.json").read_text())
    assert channels["all_checks_pass"]
    sizes = csv_rows("effective_size_extension/size_checks.csv")
    periodic = toml_rows("effective_periodic_refined/results.toml")["rows"]
    folded = toml_rows("rank_folded_mps/results.toml")["rows"]
    assert toml_rows("rank_folded_mps/summary.toml")["all_gates_pass"]
    OUT.mkdir(exist_ok=True)
    plt.rcParams.update({"font.family":"sans-serif", "font.sans-serif":["Arial"],
        "font.size":8, "axes.labelsize":9, "axes.titlesize":9,
        "axes.spines.top":False, "axes.spines.right":False,
        "legend.frameon":False, "legend.fontsize":7,
        "pdf.fonttype":42, "svg.fonttype":"none"})
    red, blue, gray = "#B54A40", "#226A9A", "#656565"
    fig, axes = plt.subplots(2, 2, figsize=(7.15, 5.2), layout="constrained")
    a, b, c, d = axes.ravel()
    for spin, color, label in ((1.5,red,"Quartet"),(.5,blue,"Doublet")):
        rows = [r for r in family if float(r["spin"]) == spin]
        a.plot([float(r["Q_over_pi"]) for r in rows],
               [float(r["alpha_root"]) for r in rows], "o-", color=color,
               ms=3, lw=.8, label=label)
    a.set(xlabel=r"Effective momentum $Q/\pi$", ylabel=r"Local root $\alpha_*$",
          title="Paired local interference zeros")
    a.legend(loc="center right")
    b.axhline(0, color="#cccccc", lw=.7)
    b.plot([1,2,3], channels["quartet_composite_channel_coefficients"],
           "s-", color=red, ms=5, lw=.8, label="Quartet")
    b.plot([1], [channels["doublet_composite_coefficient"]], "o", color=blue, ms=5, label="Doublet")
    b.set(xlabel=r"Bond-spin transition $J\leftrightarrow J-1$", ylabel=r"Composite coefficient $r_J$",
          title="Channel-dependent composite vector", xticks=[1,2,3],
          xticklabels=[r"$1\leftrightarrow0$",r"$2\leftrightarrow1$",r"$3\leftrightarrow2$"])
    b.legend(loc="upper left")
    rows = [r for r in sizes if r["boundary"] == "PBC"]
    c.plot([int(r["cells"]) for r in rows],
           [float(r["retuned_W_over_beta2"]) for r in rows], "s-",
           color=red, ms=4, lw=.8, label="ED")
    for n in sorted({r["cells"] for r in periodic}):
        selected = [r for r in periodic if r["cells"] == n]
        row = next((r for r in reversed(selected) if r["accepted"]), selected[-1])
        c.plot(n, row["W_min"], "^" if row["accepted"] else "x",
               color=red if row["accepted"] else gray, ms=5,
               label="DMRG (accepted)" if row["accepted"] else "DMRG (not converged)")
    handles, labels = c.get_legend_handles_labels()
    unique = dict(zip(labels, handles))
    c.legend(unique.values(), unique.keys(), loc="lower right")
    c.set(xlabel="Number of effective cells", ylabel=r"Minimum $W_\pi/\beta^2$",
          title=r"Even periodic chains: $q=\pi$", xticks=[4,6,8,10,12,16], ylim=(-.00005,.001))
    c.ticklabel_format(axis="y", style="sci", scilimits=(0,0), useMathText=True)
    rows = [r for r in even if float(r["spin"]) == 1.5]
    d.plot([int(r["cells"]) for r in rows], [float(r["W_min_over_beta2"]) for r in rows],
           "s", color=red, ms=4, label="Quartet ED")
    for row in folded:
        if row["cells"] == 12 and row["ground_state_accepted"]:
            d.plot(12,row["W_min_over_beta2"],"^",color=red,ms=5,label="Quartet DMRG")
    d.axhline(0,color=blue,lw=.8,ls="--",label="Doublet: first-order cancellation")
    rows = [r for r in even if float(r["spin"]) == .5]
    d.plot([int(r["cells"]) for r in rows], [float(r["W_min_over_beta2"]) for r in rows],
           "o",color=blue,ms=4)
    d.set(xlabel="Number of effective cells", ylabel=r"Minimum $W_q/\beta^2$",
          title=r"Same roots and $Q=2\pi/3$", xticks=[3,6,12], ylim=(-.01,.16))
    d.legend(loc="upper right")
    for label, ax in zip("abcd",axes.ravel()):
        ax.text(-.18,1.06,label,transform=ax.transAxes,weight="bold",fontsize=11)
    for suffix in ("pdf","svg","png"):
        fig.savefig(OUT / f"rank_controls.{suffix}",dpi=300)
    plt.close(fig)
    sources = [BASE / p for p in ("compensation_family/roots.csv",
        "effective_size_extension/size_checks.csv", "effective_periodic_refined/results.toml",
        "rank_folded_mps/results.toml", "rank_folded_mps/summary.toml",
        "rank_even_effective/comparisons.csv", "bond_spin_channels_v2/summary.json")]
    (OUT/"sha256.json").write_text(json.dumps({str(p.relative_to(ROOT)):
        hashlib.sha256(p.read_bytes()).hexdigest() for p in
        [Path(__file__),*sources,*sorted(OUT.glob("rank_controls.*"))]},indent=2)+"\n")


if __name__ == "__main__":
    main()
