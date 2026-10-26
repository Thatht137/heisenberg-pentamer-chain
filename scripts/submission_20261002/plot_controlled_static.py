"""从现存数据生成静态证据图与求解器对照。"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.text import Text
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "figures/submission_20261002_static"
PHASE = ROOT / "results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha/phase-diagram-v2"
IMPACT = ROOT / "results/autoresearch_v5_20260920/static_krylov_impact_v2"
JOINT = ROOT / "results/autoresearch_v5_20260919/closeout_stage1_joint_v2"
SOURCES = {
    "phase_decisions": PHASE / "stage_c_practical_v2_r1_boundary_decision.json",
    "entropy_fits": IMPACT / "entropy_fit_comparison.csv",
    "finite_size_impact": IMPACT / "finite_size_impact.csv",
    "historical_joint": JOINT / "joint_size_evidence.csv",
    "impact_provenance": IMPACT / "source_provenance.json",
}
BLUE = "#286592"
TEAL = "#087F79"
GRAY = "#676C76"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def style() -> None:
    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "DejaVu Sans"],
        "font.size": 8,
        "axes.titlesize": 8.5,
        "axes.labelsize": 8,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "legend.fontsize": 7,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.7,
        "legend.frameon": False,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
    })


def export(fig, stem: str) -> dict:
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    hidden_ticks = set()
    for ax in fig.axes:
        for axis, limits in ((ax.xaxis, ax.get_xlim()), (ax.yaxis, ax.get_ylim())):
            lower, upper = sorted(limits)
            for tick in axis.get_major_ticks():
                if not lower - 1e-10 <= tick.get_loc() <= upper + 1e-10:
                    hidden_ticks.update((tick.label1, tick.label2))
    outside = []
    for text in fig.findobj(Text):
        if text in hidden_ticks or not text.get_visible() or not text.get_text().strip():
            continue
        box = text.get_window_extent(renderer)
        if box.width and box.height and (
            box.x0 < -1 or box.y0 < -1
            or box.x1 > fig.bbox.width + 1 or box.y1 > fig.bbox.height + 1
        ):
            outside.append(text.get_text())
    if outside:
        raise ValueError(f"文字越界：{outside}")
    outputs = []
    for suffix in ("pdf", "svg", "png"):
        path = OUT / f"{stem}.{suffix}"
        fig.savefig(path, dpi=400, facecolor="white")
        outputs.append(path)
    plt.close(fig)
    pixels = np.asarray(Image.open(OUT / f"{stem}.png").convert("RGB"))
    nonwhite = float(np.mean(np.any(pixels < 245, axis=2)))
    if nonwhite < 0.02:
        raise ValueError("图像近乎空白")
    return {
        "nonwhite_fraction": nonwhite,
        "text_outside_canvas": outside,
        "outputs": {p.name: {"sha256": sha256(p), "bytes": p.stat().st_size} for p in outputs},
    }


def phase_rows(payload: dict) -> tuple[list[dict], list[dict]]:
    points = {}
    decisions = []
    for index, decision in enumerate(payload["decisions"], start=1):
        beta = float(decision["beta"])
        for point in decision["points"]:
            row = {
                "alpha": float(point["alpha"]), "beta": beta,
                "q60_over_pi": float(point["q"]["L60"]),
                "q80_over_pi": float(point["q"]["L80"]),
                "momentum_class": point["momentum_class"],
                "delta_r": float(point["delta_R_80_60"]["value"]),
                "epsilon": float(point["delta_R_80_60"]["error"]),
            }
            key = (beta, row["alpha"])
            if key in points and row != points[key]:
                raise ValueError(f"重复参数记录不一致：{key}")
            points[key] = row
        candidates = decision["candidate_brackets"]
        decisions.append({
            "target": index, "beta": beta,
            "alpha_left": float(decision["initial_alpha"][0]),
            "alpha_right": float(decision["initial_alpha"][1]),
            "momentum_shift": int(any("momentum_reconstruction" in c["evidence"] for c in candidates)),
            "two_error_flow": int(any("two_sigma_ratio_sign" in c["evidence"] for c in candidates)),
            "narrow_interval": int(any(float(c["width"]) <= 0.025 + 1e-12 for c in candidates)),
            "joint_criterion": int(any(c["dual_diagnostic"] for c in candidates)),
        })
    return sorted(points.values(), key=lambda r: (r["beta"], r["alpha"])), decisions


def plot_phase(points: list[dict], decisions: list[dict]) -> dict:
    fig = plt.figure(figsize=(7.2, 5.7), layout="constrained")
    grid = fig.add_gridspec(2, 2, height_ratios=[1.06, 1], width_ratios=[1.18, 1])
    ax_map = fig.add_subplot(grid[0, :])
    ax_flow = fig.add_subplot(grid[1, 0])
    ax_gate = fig.add_subplot(grid[1, 1])
    betas = sorted({r["beta"] for r in points})
    for beta in betas:
        rows = [r for r in points if r["beta"] == beta]
        ax_map.plot([r["alpha"] for r in rows], [beta] * len(rows), color="#D5D8DD", lw=0.65, zorder=1)
    scatter = ax_map.scatter(
        [r["alpha"] for r in points], [r["beta"] for r in points],
        c=[r["q80_over_pi"] for r in points], cmap="cividis", vmin=0.6, vmax=1,
        s=39, edgecolor="#25282D", linewidth=0.4, zorder=3,
    )
    mixed = [r for r in points if r["momentum_class"] == "size_sensitive_or_mixed"]
    ax_map.scatter(
        [r["alpha"] for r in mixed], [r["beta"] for r in mixed],
        marker="x", s=24, color="#BF3C43", linewidth=0.9, zorder=4,
        label=r"$L=60,80$ momentum mismatch",
    )
    bar = fig.colorbar(scatter, ax=ax_map, fraction=0.025, pad=0.02)
    bar.set_label(r"$q_{\mathrm{peak}}(80)/\pi$")
    bar.set_ticks([0.6, 0.7, 0.8, 0.9, 1.0])
    ax_map.set(xlim=(-0.82, -0.005), ylim=(0, 1.06), xlabel=r"$\alpha=J_2/J_1$", ylabel=r"$\beta=J_3/J_1$")
    ax_map.set_title("a  Finite-size momentum reconstruction", loc="left", fontweight="bold")
    ax_map.legend(loc="lower left", fontsize=7)

    colors = mpl.colormaps["viridis"](np.linspace(0.08, 0.9, len(betas)))
    markers = ["o", "s", "^", "D", "v", "P", "X"]
    for beta, color, marker in zip(betas, colors, markers):
        rows = [r for r in points if r["beta"] == beta]
        ax_flow.errorbar(
            [r["alpha"] for r in rows], [r["delta_r"] for r in rows],
            yerr=[r["epsilon"] for r in rows], marker=marker, ms=3.3,
            color=color, capsize=2, lw=0.85, label=fr"${beta:g}$",
        )
    ax_flow.axhline(0, color=GRAY, lw=0.7, ls="--")
    ax_flow.set(xlabel=r"$\alpha$", ylabel=r"$\Delta R=R_{80}-R_{60}$")
    ax_flow.set_title("b  Dominant-ratio size flow", loc="left", fontweight="bold")
    ax_flow.legend(title=r"$\beta$", title_fontsize=7, ncol=3, fontsize=6.5, loc="lower left", columnspacing=0.5, handlelength=1.1)

    keys = ["momentum_shift", "two_error_flow", "narrow_interval", "joint_criterion"]
    matrix = np.array([[r[k] for k in keys] for r in decisions])
    ax_gate.imshow(matrix, cmap=mpl.colors.ListedColormap(["#F0F2F4", BLUE]), vmin=0, vmax=1, aspect="auto")
    ax_gate.set_xticks(range(4), [r"$q$ shift", r"$2\epsilon$ flow", "Narrow", "Joint"], rotation=30, ha="right")
    ax_gate.set_yticks(range(len(decisions)), [f"{r['target']}: {r['beta']:g}" for r in decisions])
    ax_gate.set_ylabel(r"Target: $\beta$")
    for i in range(len(decisions)):
        for j in range(4):
            ax_gate.text(j, i, "yes" if matrix[i, j] else "no", ha="center", va="center", fontsize=6.6, color="white" if matrix[i, j] else GRAY)
    ax_gate.tick_params(length=0)
    for spine in ax_gate.spines.values():
        spine.set_visible(False)
    ax_gate.set_title("c  Candidate-interval criteria", loc="left", fontweight="bold")
    return export(fig, "fig8_finite_size_reconstruction")


def entropy_rows(fits: list[dict], joint: list[dict], size: list[dict]) -> tuple[list[dict], list[dict]]:
    alphas = [-0.175, -0.1]
    historical = []
    controls = []
    for row in joint:
        if float(row["alpha"]) in alphas:
            historical.append({
                "alpha": float(row["alpha"]), "beta": float(row["beta"]),
                "L": int(row["L"]), "krylov": 3,
                "fixed_window": 0.2, "period": 10,
                "mean_fixed_window": float(row["c10_fixed_mean"]),
                "min_all_windows_starts": float(row["c10_all_min"]),
                "max_all_windows_starts": float(row["c10_all_max"]),
            })
    if len(historical) != 6:
        raise ValueError("历史尺寸记录应为两参数点、三长度")
    for alpha in alphas:
        for solver in ("k3", "k8"):
            for window in (0.1, 0.15, 0.2, 0.25):
                rows = [r for r in fits if float(r["alpha"]) == alpha and r["solver"] == solver
                        and int(r["period"]) == 10 and float(r["window"]) == window]
                if len(rows) != 2 or {r["start"] for r in rows} != {"center", "ferro_j2"}:
                    raise ValueError("求解器对照的初态或拟合窗口不完整")
                values = [float(r["c_eff"]) for r in rows]
                record = {"alpha": alpha, "beta": 0.25, "L": 80,
                          "krylov": int(solver[1:]), "window": window, "period": 10,
                          "mean": float(np.mean(values)), "min_start": min(values), "max_start": max(values)}
                controls.append(record)
                if window == 0.2:
                    check = [r for r in size if float(r["alpha"]) == alpha and int(r["L"]) == 80 and r["solver"] == solver]
                    if len(check) != 1 or abs(record["mean"] - float(check[0]["entropy_period10_window020_mean"])) > 1e-12:
                        raise ValueError("独立汇总表的固定窗口均值不一致")
    return historical, controls


def plot_entropy(historical: list[dict], controls: list[dict]) -> dict:
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.85), layout="constrained", gridspec_kw={"width_ratios": [1.15, 1, 1]})
    for alpha, color, marker in [(-0.175, BLUE, "o"), (-0.1, "#AA5A6A", "D")]:
        rows = sorted([r for r in historical if r["alpha"] == alpha], key=lambda r: r["L"])
        means = np.array([r["mean_fixed_window"] for r in rows])
        interval = np.array([[r["min_all_windows_starts"], r["max_all_windows_starts"]] for r in rows])
        axes[0].errorbar([r["L"] for r in rows], means, yerr=[means - interval[:, 0], interval[:, 1] - means],
                         fmt=marker, color=color, ms=4, capsize=3, lw=0.9, label=fr"$\alpha={alpha:g}$")
    axes[0].set(xlabel=r"$L$", ylabel=r"$c_{\mathrm{eff}}$", xlim=(33, 87), ylim=(0.38, 1.4))
    axes[0].set_xticks([40, 60, 80])
    axes[0].set_title(r"a  Historical sizes: $k=3$", loc="left", fontweight="bold")
    axes[0].legend(loc="lower left", fontsize=7)

    for ax, alpha, label in zip(axes[1:], [-0.1, -0.175], ["b", "c"]):
        for krylov, color, marker, offset in [(3, GRAY, "o", -0.002), (8, TEAL, "s", 0.002)]:
            rows = [r for r in controls if r["alpha"] == alpha and r["krylov"] == krylov]
            means = np.array([r["mean"] for r in rows])
            ax.errorbar([r["window"] + offset for r in rows], means,
                        yerr=[means - [r["min_start"] for r in rows], [r["max_start"] for r in rows] - means],
                        fmt=marker, color=color, ms=4, capsize=3, lw=0.9, label=fr"$k={krylov}$")
        ax.set(xlabel=r"Fit-window fraction $f$", xlim=(0.085, 0.265), ylim=(0.38, 1.06))
        ax.set_xticks([0.1, 0.15, 0.2, 0.25], [".10", ".15", ".20", ".25"])
        ax.set_title(fr"{label}  $L=80,\ \alpha={alpha:g}$", loc="left", fontweight="bold")
        ax.legend(loc="lower right", fontsize=7)
    for ax in axes:
        ax.axhline(1, color="#B6BDC4", ls=":", lw=0.8, zorder=0)
    return export(fig, "fig9_entropy_solver_control")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    style()
    original_hashes = {name: sha256(path) for name, path in SOURCES.items()}
    phase = json.loads(SOURCES["phase_decisions"].read_text(encoding="utf-8"))
    points, decisions = phase_rows(phase)
    historical, controls = entropy_rows(read_csv(SOURCES["entropy_fits"]), read_csv(SOURCES["historical_joint"]), read_csv(SOURCES["finite_size_impact"]))
    for name, rows in [("fig8_points", points), ("fig8_candidate_criteria", decisions),
                       ("fig9_historical_sizes", historical), ("fig9_l80_solver_controls", controls)]:
        write_csv(OUT / f"{name}.csv", rows)
    exports = {"fig8": plot_phase(points, decisions), "fig9": plot_entropy(historical, controls)}
    for name, path in SOURCES.items():
        if sha256(path) != original_hashes[name]:
            raise ValueError("绘图期间源文件发生变化")
        shutil.copyfile(path, OUT / f"source_{name}{path.suffix}")
    provenance = json.loads(SOURCES["impact_provenance"].read_text(encoding="utf-8"))
    source_audit = []
    for record in provenance["files"]:
        path = ROOT / record["path"]
        current_hash = sha256(path) if path.is_file() else None
        source_audit.append({
            "path": record["path"], "role": record["role"],
            "recorded_sha256": record["sha256"], "current_sha256": current_hash,
            "exists": path.is_file(), "matches": current_hash == record["sha256"],
        })
    qa = {
        "status": "rendered_for_visual_review", "backend": "Python/matplotlib",
        "figure_contract": {
            "fig8": "Finite-size momentum reconstruction; operational criteria do not establish a thermodynamic phase boundary.",
            "fig9": "The L80 entropy coefficient is solver sensitive; k8 controls do not replace a consistently controlled size sequence.",
            "archetype": "quantitative grid", "width_inches": 7.2,
            "parameter_footer": False, "interpolation": False, "smoothing": False,
        },
        "sources": {name: {"path": path.relative_to(ROOT).as_posix(), "sha256": original_hashes[name]} for name, path in SOURCES.items()},
        "upstream_source_audit": source_audit,
        "upstream_provenance_caveat": "The current candidate-audit adapter code differs from its historical hash; archived measurement files match. No historical code equivalence is asserted.",
        "exported_source_data": {p.name: sha256(p) for p in sorted(OUT.glob("*.csv"))},
        "source_data_changed": False, "new_numerical_runs": False,
        "script_sha256": sha256(Path(__file__)), "phase_points": len(points),
        "candidate_intervals": len(decisions), "joint_criterion_intervals": sum(r["joint_criterion"] for r in decisions),
        "entropy_historical_points": len(historical), "entropy_solver_window_groups": len(controls),
        "mixed_solver_size_lines": False, "intervals_are_statistical_ci": False,
        "cross_table_entropy_check_tolerance": 1e-12,
        "fixed_window_controls": [r for r in controls if r["window"] == 0.2],
        "exports": exports,
    }
    (OUT / "qa.json").write_text(json.dumps(qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), "phase_points": len(points), "entropy_controls": len(controls)}))


if __name__ == "__main__":
    main()
