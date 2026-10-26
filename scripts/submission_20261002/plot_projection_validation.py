"""绘制两胞精确对角化与弱耦合投影的定量比较。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from plot_controlled_static import OUT, ROOT, BLUE, TEAL, GRAY, export, read_csv, sha256, style, write_csv


SOURCE = ROOT / "results/submission_20261002/local_projection"
INPUT_NAMES = ["protocol.json", "summary.json", "coupling_checks.csv", "q_resolved_weights.csv", "folded_prediction.csv"]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    hashes = {name: sha256(SOURCE / name) for name in INPUT_NAMES}
    protocol = json.loads((SOURCE / "protocol.json").read_text(encoding="utf-8"))
    summary = json.loads((SOURCE / "summary.json").read_text(encoding="utf-8"))
    if protocol["L"] != 10 or protocol["boundary"] != "OBC" or protocol["q_points"] != 41:
        raise ValueError("小体系基准协议不匹配")
    if not summary["all_predefined_weak_predictions_pass"]:
        raise ValueError("预设弱耦合判据未全部通过")
    checks = read_csv(SOURCE / "coupling_checks.csv")
    spectra = read_csv(SOURCE / "q_resolved_weights.csv")
    style()
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 4.65), layout="constrained", sharex="row", sharey="row")
    plotted_q, plotted_g, diagnostics = [], [], []
    for column, alpha in enumerate((0.5, -0.5)):
        rows = sorted([r for r in spectra if float(r["alpha"]) == alpha and float(r["g"]) == 0.01], key=lambda r: float(r["q_over_pi"]))
        if len(rows) != 41:
            raise ValueError("绘制的动量点数不完整")
        q = np.array([float(r["q_over_pi"]) for r in rows])
        ed = np.array([float(r["low_weight_ed"]) for r in rows])
        predicted = np.array([float(r["low_weight_prediction"]) for r in rows])
        target = next(r for r in checks if float(r["alpha"]) == alpha and float(r["g"]) == 0.01)
        reconstructed_error = float(np.linalg.norm(ed - predicted) / np.linalg.norm(predicted))
        if abs(reconstructed_error - float(target["low_band_weight_relative_error"])) > 1e-12:
            raise ValueError("动量权重与汇总误差不一致")
        ax = axes[0, column]
        ax.plot(q, predicted, color=GRAY, lw=1.1, label="First-order prediction", zorder=2)
        ax.plot(q, ed, linestyle="none", marker="o", ms=3.2, mfc="white", mec=BLUE, mew=0.8, label="Exact diagonalization", zorder=3)
        ax.set(xlim=(0, 2), ylim=(-0.014, 0.47), xlabel=r"$q$")
        ax.set_xticks([0, 0.5, 1, 1.5, 2], ["0", r"$\pi/2$", r"$\pi$", r"$3\pi/2$", r"$2\pi$"])
        ax.set_title(fr"{'ab'[column]}  $\alpha={alpha:g}$", loc="left", fontweight="bold")
        if column == 0:
            ax.set_ylabel(r"Low-band weight $W_{\mathrm{low}}(q)$")
            ax.legend(loc="upper left", fontsize=7)
        plotted_q.extend(rows)

        selected = sorted([r for r in checks if float(r["alpha"]) == alpha and float(r["g"]) in protocol["g_values"]], key=lambda r: float(r["g"]))
        if len(selected) != 5:
            raise ValueError("耦合扫描必须仅包含五个真实点")
        g = np.array([float(r["g"]) for r in selected])
        ax = axes[1, column]
        ax.set_xscale("log", base=2)
        ax.axvspan(g.min() / 1.13, protocol["weak_domain_g_max"], color="#EAF2F1", zorder=0)
        ax.axvline(protocol["weak_domain_g_max"], color="#A0B6B2", lw=0.7, ls=":", zorder=1)
        ax.plot(g, [100 * float(r["gap_relative_error"]) for r in selected], color=TEAL, marker="D", ms=3.8, lw=1, label="Gap")
        ax.plot(g, [100 * float(r["low_band_weight_relative_error"]) for r in selected], color=BLUE, marker="o", mfc="white", ms=4, lw=1, label="Low-band weight")
        ax.set(xlim=(g.min() / 1.13, g.max() * 1.13), ylim=(-0.06, 2.42), xlabel=r"$g=\beta/\Delta_{\mathrm{loc}}$")
        ax.set_xticks(g, [".0025", ".005", ".01", ".02", ".04"])
        ax.set_title(fr"{'cd'[column]}  Relative projection error", loc="left", fontweight="bold")
        if column == 0:
            ax.set_ylabel("Relative error (%)")
            ax.legend(loc="upper left", fontsize=7)
        plotted_g.extend(selected)
        outside = next(r for r in checks if float(r["alpha"]) == alpha and float(r["beta"]) == 0.5)
        if outside["band_separated"] != "False":
            raise ValueError("域外谱带分离诊断与图注不符")
        diagnostics.append({"alpha": alpha, "g": 0.01,
                            "gap_relative_error": float(target["gap_relative_error"]),
                            "weight_relative_error": reconstructed_error,
                            "outside_domain_g": float(outside["g"]),
                            "outside_domain_band_separated": False})
    exported = export(fig, "fig_projection_ed_benchmark")
    write_csv(OUT / "projection_plotted_q_weights.csv", plotted_q)
    write_csv(OUT / "projection_plotted_coupling_errors.csv", plotted_g)
    for name in INPUT_NAMES:
        if sha256(SOURCE / name) != hashes[name]:
            raise ValueError("源数据在绘图期间改变")
        shutil.copyfile(SOURCE / name, OUT / f"projection_source_{name}")
    qa = {
        "status": "rendered_for_visual_review", "backend": "Python/matplotlib",
        "core_conclusion": "The two-pentamer weak-coupling projection predicts absolute low-band weights and the gap at predefined weak points; it is not a validation of the production beta=0.5 spectra.",
        "L": 10, "q_points_per_panel": 41, "coupling_points_per_panel": 5,
        "q_panel_g": 0.01, "predefined_weak_g_max": 0.01,
        "production_beta_in_plot": False, "parameter_footer": False,
        "source_data_changed": False, "new_computation_by_plotter": False,
        "statistical_error_bars": False, "interpolation": False, "smoothing": False,
        "source_sha256": hashes, "script_sha256": sha256(Path(__file__)),
        "export_helper_sha256": sha256(Path(__file__).with_name("plot_controlled_static.py")),
        "data": diagnostics, "exports": exported,
        "plot_source_sha256": {p.name: sha256(p) for p in sorted(OUT.glob("projection_plotted_*.csv"))},
    }
    (OUT / "projection_qa.json").write_text(json.dumps(qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT / "fig_projection_ed_benchmark.pdf"), "data": diagnostics}))


if __name__ == "__main__":
    main()
