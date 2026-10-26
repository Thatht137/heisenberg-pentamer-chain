"""审计有限耦合近零频谱与低温背景，不修改原始结果。"""

import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import validate_thermal_four_cells as calc

ROOT = calc.ROOT
SOURCE = ROOT/"results/novelty_20261008/thermal_microscopic_four_cells"
OUT = ROOT/"results/novelty_20261008/four_cell_window_audit"


def read_rows(path):
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def load_blocks(g):
    with np.load(SOURCE/f"low_band_g{g:.7f}.npz") as z:
        return [(z[f"e_{m}"], z[f"op_{m}"], z[f"spin_{m}"], int(z[f"multiplicity_{m}"]))
                for m in range(7)]


def main():
    OUT.mkdir(exist_ok=True)
    protocol = {"posthoc_diagnostic": True,
        "motivation": "raw run found frequency-threshold sensitivity at tau=1.6 and a low-T background",
        "original_protocol_unchanged": True,
        "resolved_frequency_cutoffs_over_Jeff": [.02, .05, .1],
        "figure_cutoff_over_Jeff": .05,
        "raw_positive_threshold": 1e-10,
        "no_new_eigensolves": True,
        "interpretation": "C from the leading effective Hamiltonian describes finite scaled frequency, not automatically all finite-beta omega>0 weight"}
    calc.reference.write_json(OUT/"protocol.json", protocol)
    calc.reference.write_json(OUT/"figure_contract.json", {
        "claim": "microscopic thermal activation and line strengths converge, with a finite-beta low-T background",
        "panels": ["Arrhenius response including ground-state background", "two line-strength convergence checks"],
        "backend": "existing Python/matplotlib workflow", "archetype": "quantitative grid",
        "size_inches": [7.2, 2.85], "smoothing": "none", "data": "saved microscopic low-band eigenvalues and probe matrices",
        "error_bars": "deterministic calculation, no statistical error bars", "exports": ["pdf", "svg", "png", "tiff"]})
    raw = read_rows(SOURCE/"comparisons.csv")
    lines = read_rows(SOURCE/"activation_lines.csv")
    alpha = float(raw[0]["alpha_root"])
    t, quad, c1, lc, rc, gap, _ = calc.thermal.local.local_probe(alpha, np.pi)
    data, _ = calc.thermal.blocks(4, 4, t, quad, c1, lc, rc, np.pi)
    lam = calc.thermal.weight(data, 0.)["lambda"]
    b = float(lc[1].real)
    rows, curves, diagnostics = [], [], []
    for g in (.000625, .00125, .0025):
        blocks = load_blocks(g)
        beta, jeff = g*gap, g*gap*c1*c1
        e0 = min(e.min() for e, op, spin, mult in blocks)
        leading_label_error = max(float(np.max(abs((e-e0)/jeff-np.rint((e-e0)/jeff))))
                                  for e, op, spin, mult in blocks)
        assert leading_label_error < .1
        for tau in (.1, .2, .4, 1.6):
            total = calc.weight(blocks, tau*jeff)
            resolved = [calc.weight(blocks, tau*jeff, cut*jeff)["W_positive_low"] for cut in (.02, .05, .1)]
            predicted = calc.thermal.weight(data, tau, lam)["C_fixed_zeroT_retuning"]
            rows.append({"g": g, "tau": tau, "W_raw": total["W_positive_low"],
                "W_resolved": resolved[1], "C_resolved": resolved[1]/beta**2,
                "C_predicted": predicted, "resolved_relative_error": abs(resolved[1]/beta**2/predicted-1),
                "W_quasielastic_above_raw_threshold": total["W_positive_low"]-resolved[1],
                "quasielastic_fraction_raw": 1-resolved[1]/total["W_positive_low"],
                "ground_fraction_raw": total["W_ground_initial"]/total["W_positive_low"],
                "resolved_cutoff_relative_spread": (max(resolved)-min(resolved))/resolved[1]})
        for x in np.linspace(2.5, 20, 71):
            tau = 1/x
            result = calc.weight(blocks, tau*jeff, .05*jeff)
            predicted = calc.thermal.weight(data, tau, lam)["C_fixed_zeroT_retuning"]
            curves.append({"g": g, "inverse_tau": x, "C_resolved": result["W_positive_low"]/beta**2,
                           "C_ground": result["W_ground_initial"]/beta**2,
                           "C_effective": predicted, "C_activation": 51/50*b*b*np.exp(-x)})
        diagnostics.append({"g": g, "max_leading_energy_integer_label_error": leading_label_error})
    calc.reference.write_csv(OUT/"window_comparison.csv", rows)
    calc.reference.write_csv(OUT/"temperature_curves.csv", curves)
    ground_rows = [r for r in raw if float(r["tau"]) == .1]
    ground_slope = float(np.polyfit(np.log([float(r["beta"]) for r in ground_rows]),
                                   np.log([float(r["W_ground_initial"]) for r in ground_rows]), 1)[0])
    summary = {"ground_background_slope_tau0p1": ground_slope,
        "resolved_cutoff_relative_spread_max": max(r["resolved_cutoff_relative_spread"] for r in rows),
        "weakest_resolved_errors": [r for r in rows if r["g"] == .000625],
        "diagnostics": diagnostics, "original_numerical_pass_not_equal_to_complete_physics_validation": True}
    calc.reference.write_json(OUT/"summary.json", summary)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "axes.labelsize": 9,
        "axes.linewidth": .7, "lines.linewidth": 1.2, "legend.fontsize": 7,
        "legend.frameon": False, "axes.spines.top": False, "axes.spines.right": False,
        "pdf.fonttype": 42, "svg.fonttype": "none"})
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.85), gridspec_kw={"width_ratios": [1.35, 1]})
    fig.subplots_adjust(left=.10, right=.98, bottom=.21, top=.91, wspace=.43)
    a, c = axes
    for g, color, style in ((.000625, "#C45B3D", "-"), (.00125, "#B78237", "--"), (.0025, "#6D6963", "-.")):
        case = [r for r in curves if r["g"] == g]
        a.semilogy([r["inverse_tau"] for r in case], [r["C_resolved"] for r in case],
                   color=color, ls=style, label=rf"$10^3g={g*1000:g}$")
    case = [r for r in curves if r["g"] == .000625]
    a.semilogy([r["inverse_tau"] for r in case], [r["C_effective"] for r in case],
               color="#222222", lw=1, label="Effective model")
    a.semilogy([r["inverse_tau"] for r in case], [r["C_activation"] for r in case],
               color="#2878A2", ls=":", label="Leading activation")
    a.set(xlabel=r"$J_{\rm eff}/T$", ylabel=r"$W_{+,\eta}/\beta^2$", xlim=(2.5, 20), ylim=(1e-11, 4e-3))
    a.set_xticks([5, 10, 15, 20])
    a.set_yticks([1e-11, 1e-9, 1e-7, 1e-5, 1e-3])
    a.minorticks_off()
    a.legend(loc="upper right", handlelength=1.8, ncol=2, columnspacing=.8, fontsize=6.7)
    gs = [float(r["g"])*1000 for r in lines]
    c.plot(gs, [float(r["strength_omega2_over_beta2_b2"])/(.54) for r in lines],
           "o-", color="#C45B3D", mfc="white", markersize=4, label=r"$\omega\simeq 2J_{\rm eff}$")
    c.plot(gs, [float(r["strength_omega7_over_beta2_b2"])/(.48) for r in lines],
           "s--", color="#C45B3D", markersize=4, label=r"$\omega\simeq 7J_{\rm eff}$")
    c.axhline(1, color="#444444", lw=.8, ls=":")
    c.set(xlabel=r"$10^3g$", ylabel="Line strength / predicted value", xlim=(.4, 2.7), ylim=(.958, 1.04))
    c.set_xticks([.625, 1.25, 2.5], ["0.625", "1.25", "2.5"])
    c.legend(loc="upper left")
    for label, axis in zip("ab", axes):
        axis.text(-.17, 1.055, label, transform=axis.transAxes, fontweight="bold", fontsize=10)
        axis.tick_params(direction="out", length=3)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    outside = []
    for text in fig.findobj(matplotlib.text.Text):
        if text.get_visible() and text.get_text():
            box = text.get_window_extent(renderer)
            if box.x0 < -1 or box.y0 < -1 or box.x1 > fig.bbox.x1+1 or box.y1 > fig.bbox.y1+1:
                outside.append(text.get_text())
    assert not outside, outside
    for ext in ("pdf", "svg", "png", "tiff"):
        fig.savefig(OUT/f"four_cell_activation.{ext}", dpi=600 if ext == "tiff" else 240)
    plt.close(fig)
    calc.reference.write_json(OUT/"qa.json", {"text_outside_canvas": outside, "gaussian_smoothing": False,
                                              "ground_state_background_retained": True})
    files = [Path(__file__), *sorted(SOURCE.iterdir()), *sorted(OUT.iterdir())]
    calc.reference.write_json(OUT/"sha256.json", {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                               for p in files if p.is_file() and p != OUT/"sha256.json"})
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
