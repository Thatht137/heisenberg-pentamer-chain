#!/usr/bin/env python3
"""绘制完整 alpha 范围的证据受限相图。"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch, Rectangle


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha"
PHASE = RUN / "phase-diagram-v2"
FETCH = RUN / "fetches/stage-a-beta050-calibration-r16-a0050-L080-20260811-2140"
R16 = FETCH / "nega-r16-a0050-b0500-L080"
POSITIVE = ROOT / "results/autoresearch_v5_20260802/round19_phase_diagram_positive_mesh/phase-diagram/observations.json"
STATUS = ROOT / "results/research_progress/negative_full_phase_campaign_status_20260809.json"
OBS = PHASE / "observations.json"
CAL = PHASE / "accepted_calibration_through_r9.json"
STRICT = FETCH / "validation.json"
OUT = ROOT / "figures/full_alpha_phase_evidence_20260811"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scalar(record: dict, key: str) -> float:
    value = record["observables"][key]
    return float(value["value"] if isinstance(value, dict) else value)


def source_row(kind: str, record: dict) -> dict[str, object]:
    params = record["params"]
    q = record.get("diagnostics", {}).get("q_peak_over_pi", {})
    return {
        "record_type": kind,
        "alpha": params["alpha"],
        "beta": params["beta"],
        "L": params["L"],
        "R": record.get("value", ""),
        "R_error": record.get("error", ""),
        "q_peak_over_pi": q.get("value", ""),
        "q_error": q.get("error", ""),
        "E0": "",
        "E1": "",
        "spin_gap": "",
        "final_energy_change_sz0": "",
        "variance_per_site_sz0": "",
        "evidence_class": "strict accepted",
    }


def main() -> None:
    for path in (OBS, CAL, POSITIVE, STATUS, STRICT, R16 / "manifest.json"):
        if not path.is_file():
            raise FileNotFoundError(path)
    negative = [row for row in load(OBS)["records"] if row["status"] == "success" and row["params"]["beta"] == 0.5]
    calibration = [row for row in load(CAL)["records"] if row["status"] == "success"]
    positive = [row for row in load(POSITIVE)["records"] if row["status"] == "success"]
    positive_total = int(load(STATUS)["strict_reuse"]["positive_accepted_records"])
    if len(negative) != 14 or len(calibration) != 6 or len(positive) != 60 or positive_total != 105:
        raise ValueError("accepted 数据计数不匹配")
    strict = load(STRICT)
    if strict["status"] != "fail" or not strict["checks"]["original_gates"]:
        raise ValueError("R16 严格失败基线不匹配")

    modes = ("center_random", "ferro_j2", "domain")
    children = {mode: load(R16 / f"start_{mode}/manifest.json") for mode in modes}
    for mode, manifest in children.items():
        if manifest["status"] != "success" or manifest["params"]["alpha"] != -0.05:
            raise ValueError(f"R16 子结果不匹配: {mode}")
    denergy = np.array([abs(float(children[mode]["diagnostics"]["final_energy_change_sz0"])) for mode in modes])
    gaps = np.array([scalar(children[mode], "spin_gap") for mode in modes])
    e0 = np.array([scalar(children[mode], "energy_sz0") for mode in modes])
    if not (np.all(denergy <= 1e-7) and np.all(gaps >= -1e-8) and np.ptp(e0) <= 1e-6):
        raise ValueError("R16 practical 门不通过")

    rows = [source_row("negative_controller", row) for row in negative]
    rows.extend(source_row("negative_L80_calibration", row) for row in calibration)
    for mode in modes:
        manifest = children[mode]
        rows.append({
            "record_type": f"r16_practical_{mode}", "alpha": -0.05, "beta": 0.5, "L": 80,
            "R": scalar(manifest, "dominant_structure_factor_ratio"), "R_error": "",
            "q_peak_over_pi": scalar(manifest, "structure_factor_peak_q_over_pi"), "q_error": 0.0025,
            "E0": scalar(manifest, "energy_sz0"), "E1": scalar(manifest, "energy_sz1"),
            "spin_gap": scalar(manifest, "spin_gap"),
            "final_energy_change_sz0": manifest["diagnostics"]["final_energy_change_sz0"],
            "variance_per_site_sz0": manifest["diagnostics"]["variance_per_site_sz0"],
            "evidence_class": "practical calibration; boundary ineligible",
        })
    source_path = OUT.with_suffix(".source.csv")
    source_path.parent.mkdir(parents=True, exist_ok=True)
    with source_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans", "Liberation Sans"]
    plt.rcParams["svg.fonttype"] = "none"
    plt.rcParams["pdf.fonttype"] = 42
    plt.rcParams["font.size"] = 7.2
    plt.rcParams["axes.linewidth"] = 0.8
    plt.rcParams["axes.spines.top"] = False
    plt.rcParams["axes.spines.right"] = False
    plt.rcParams["legend.frameon"] = False

    blue = "#3775BA"
    teal = "#42949E"
    orange = "#E28E2C"
    violet = "#7C6CCF"
    grey = "#B8B8B8"
    dark = "#363636"
    fig, axes = plt.subplots(2, 2, figsize=(7.20, 5.55), constrained_layout=True)
    ax_a, ax_b, ax_c, ax_d = axes.flat

    # a：二维证据地图
    ax_a.add_patch(Rectangle((0, 0), 1, 1, facecolor="#DCEBF7", edgecolor="none", alpha=0.95))
    ax_a.add_patch(Rectangle((-1, 0), 1, 1, facecolor="#F1F1F1", edgecolor=grey, hatch="////", linewidth=0.5))
    ax_a.axvline(0, color=dark, linestyle="--", linewidth=1.0)
    ax_a.axhline(0, color=dark, linestyle=":", linewidth=1.0)
    ax_a.plot([-1, -0.75, -0.5, -0.35, -0.25, -0.1, -0.05], [0.5] * 7, "o", color=dark, ms=3.2, label="strict L40/L60")
    ax_a.plot([-1, -0.75, -0.5, -0.35, -0.25, -0.1], [0.5] * 6, "^", mfc="white", mec=violet, mew=0.9, ms=4.0, label="strict L80")
    ax_a.plot(-0.05, 0.5, "D", mfc="white", mec=orange, mew=1.1, ms=4.2, label="R16 practical L80")
    ax_a.plot([-0.35, -0.25], [0.5, 0.5], color=orange, lw=7, alpha=0.32, solid_capstyle="butt")
    ax_a.text(0.48, 0.70, r"$q=\pi$ gapless AF", ha="center", va="center", color="#0F4D92", weight="bold")
    ax_a.text(0.48, 0.61, "finite-size supported", ha="center", va="center", color="#0F4D92", fontsize=6.2)
    ax_a.text(-0.55, 0.78, "2D negative region\nnot yet classified", ha="center", va="center", color="#606060")
    ax_a.annotate("candidate momentum\ncompetition", xy=(-0.30, 0.5), xytext=(-0.72, 0.25),
                  arrowprops={"arrowstyle": "->", "color": orange, "lw": 0.8}, color="#9A5A12", fontsize=6.3)
    ax_a.text(0.015, 0.95, r"$\alpha=0$ decoupled line", transform=ax_a.get_xaxis_transform(), rotation=90,
              ha="left", va="top", fontsize=5.8, color=dark)
    ax_a.set(xlim=(-1, 1), ylim=(0, 1), xlabel=r"$\alpha=J_2/J_1$", ylabel=r"$\beta=J_3/J_1$", title="Evidence-bounded phase map")
    ax_a.set_xticks([-1, -0.5, 0, 0.5, 1])
    ax_a.set_yticks([0, 0.5, 1])
    ax_a.legend(handles=[Patch(facecolor="#DCEBF7", label="positive region: strict mesh"),
                         Patch(facecolor="#F1F1F1", edgecolor=grey, hatch="////", label="negative region: unscanned in 2D")],
                loc="lower right", fontsize=5.5, handlelength=1.4)

    # b：主导动量
    by_l: dict[int, list[dict]] = {40: [], 60: [], 80: []}
    for row in negative:
        by_l[int(row["params"]["L"])].append(row)
    for row in calibration:
        by_l[80].append(row)
    for length, color, marker in ((40, blue, "o"), (60, teal, "s"), (80, violet, "^")):
        series = sorted(by_l[length], key=lambda item: item["params"]["alpha"])
        x = [item["params"]["alpha"] for item in series]
        y = [item["diagnostics"]["q_peak_over_pi"]["value"] for item in series]
        ey = [item["diagnostics"]["q_peak_over_pi"]["error"] for item in series]
        ax_b.errorbar(x, y, yerr=ey, color=color, marker=marker, ms=3.5, lw=1.0, capsize=1.8, label=f"L={length}")
    r16_q = np.mean([scalar(children[mode], "structure_factor_peak_q_over_pi") for mode in modes])
    ax_b.plot(-0.05, r16_q, "D", mfc="white", mec=orange, mew=1.1, ms=4.2, label="R16 practical")
    ax_b.axvspan(-0.35, -0.25, color=orange, alpha=0.16, linewidth=0)
    ax_b.axhline(0.6, color="#999999", lw=0.7, ls=":")
    ax_b.axhline(1.0, color="#999999", lw=0.7, ls=":")
    ax_b.set(xlim=(-1.03, -0.015), ylim=(0.55, 1.04), xlabel=r"$\alpha$ at $\beta=0.5$", ylabel=r"$q_{\rm peak}/\pi$", title="Momentum reconstruction is size-sensitive")
    ax_b.legend(ncol=2, fontsize=5.8, loc="upper left")

    # c：有限尺寸 crossing
    pairs: dict[float, dict[int, dict]] = {}
    for row in negative:
        pairs.setdefault(float(row["params"]["alpha"]), {})[int(row["params"]["L"])] = row
    alpha = np.array(sorted(pairs))
    delta = np.array([pairs[a][60]["value"] - pairs[a][40]["value"] for a in alpha])
    error = np.array([math.hypot(pairs[a][60]["error"], pairs[a][40]["error"]) for a in alpha])
    ax_c.axhline(0, color=dark, lw=0.8)
    ax_c.axvspan(-0.35, -0.25, color=orange, alpha=0.16, linewidth=0)
    ax_c.errorbar(alpha, delta, yerr=error, color=blue, marker="o", ms=3.8, lw=1.0, capsize=2.0)
    ax_c.annotate(r"sign reversal", xy=(-0.25, delta[list(alpha).index(-0.25)]), xytext=(-0.62, 0.052),
                  arrowprops={"arrowstyle": "->", "color": orange, "lw": 0.8}, color="#9A5A12", fontsize=6.3)
    ax_c.set(xlim=(-1.03, -0.015), xlabel=r"$\alpha$ at $\beta=0.5$", ylabel=r"$R_{60}-R_{40}$", title="Finite-size bracket is only provisional")

    # d：R16 失败原因
    ratio = denergy / 1e-8
    bars = ax_d.bar(np.arange(3), ratio, color=[blue, teal, violet], width=0.62, edgecolor=dark, linewidth=0.6)
    ax_d.axhline(1, color="#B64342", lw=1.0, ls="--", label=r"strict $10^{-8}$")
    ax_d.axhline(10, color=orange, lw=1.0, ls=":", label=r"practical $10^{-7}$")
    for bar, gap in zip(bars, gaps):
        ax_d.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.24, f"gap={gap*1e6:.2f}", ha="center", va="bottom", fontsize=5.7)
    ax_d.text(0.02, 0.96, f"three-start E0 range = {np.ptp(e0):.3g}\nall gaps positive; all core gates pass",
              transform=ax_d.transAxes, ha="left", va="top", fontsize=6.1, color=dark)
    ax_d.set_xticks(range(3), ["random", "ferro", "domain"])
    ax_d.set(xlabel="initial state", ylabel=r"$|\Delta E_0^{last}| / 10^{-8}$", title="R16 raw data miss the strict plateau gate", ylim=(0, 11.7))
    ax_d.legend(loc="upper right", fontsize=5.8)

    for label, ax in zip("abcd", axes.flat):
        ax.text(-0.13, 1.06, label, transform=ax.transAxes, fontsize=8.5, weight="bold", va="top")
    fig.suptitle("1×5 Heisenberg pentamer: current phase evidence, not final phase labels", fontsize=9.0, weight="bold")
    fig.text(0.5, -0.015, "Solid symbols: strict accepted; hollow orange: author-approved practical calibration. Shading marks evidence status, not a thermodynamic phase claim.",
             ha="center", va="bottom", fontsize=5.9, color="#555555")
    for suffix, kwargs in (("svg", {}), ("pdf", {}), ("png", {"dpi": 400}), ("tiff", {"dpi": 600})):
        fig.savefig(OUT.with_suffix(f".{suffix}"), bbox_inches="tight", **kwargs)
    plt.close(fig)

    source_files = [OBS, CAL, POSITIVE, STATUS, STRICT, R16 / "manifest.json"]
    for mode in modes:
        source_files.append(R16 / f"start_{mode}/manifest.json")
    sources = {
        "schema_version": 1,
        "figure": str(OUT.relative_to(ROOT)),
        "core_conclusion": "Two critical regimes separated by alpha=0 are the leading physical hypothesis; the alpha=-0.35..-0.25 momentum change is not a confirmed phase boundary.",
        "evidence_hierarchy": {"hero": "accepted beta=0.5 momentum and crossing data", "validation": "R16 three-start convergence", "control": "positive-region 105-record strict mesh"},
        "boundary_eligible_r16": False,
        "sources": [{"path": str(path.relative_to(ROOT)), "sha256": sha256(path)} for path in source_files],
        "source_data": str(source_path.relative_to(ROOT)),
    }
    sources_path = OUT.with_suffix(".sources.json")
    sources_path.write_text(json.dumps(sources, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    svg = OUT.with_suffix(".svg").read_text(encoding="utf-8")
    exports = {suffix: OUT.with_suffix(f".{suffix}").stat().st_size for suffix in ("svg", "pdf", "png", "tiff")}
    qa = {
        "schema_version": 1,
        "status": "pass" if all(size > 1000 for size in exports.values()) and svg.count("<text") >= 20 else "fail",
        "backend": "python-matplotlib-only",
        "archetype": "quantitative grid",
        "final_width_mm": 183,
        "editable_svg_text_nodes": svg.count("<text"),
        "record_counts": {"negative_controller": len(negative), "negative_L80_calibration": len(calibration), "positive_phase_controller": len(positive), "positive_all_accepted": positive_total, "r16_starts": len(children)},
        "exports_bytes": exports,
        "review_risks": ["negative 2D region remains unscanned", "momentum shift may be crossover", "R16 practical calibration is boundary-ineligible"],
    }
    qa_path = OUT.with_suffix(".qa.json")
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if qa["status"] != "pass":
        raise SystemExit("figure QA failed")
    print(json.dumps({"status": "pass", "figure": str(OUT), "qa": qa}, ensure_ascii=False))


if __name__ == "__main__":
    main()
