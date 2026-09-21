#!/usr/bin/env python3
"""分析五聚体链能隙与有效 Heisenberg 链的有限尺寸对应。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "results" / "autoresearch_v3_20260729" / "round2_effective_scan"
ANALYSIS = SOURCE / "analysis_final"
ORACLE = ROOT / "results" / "autoresearch_v3_20260729" / "round2_effective_oracle" / "heisenberg_obc_oracle.csv"
OUTDIR = ROOT / "results" / "autoresearch_v5_20260731" / "round12_effective_gap_scaling"
DEFAULT_SCALING = Path.home() / "code" / "quantum.harness" / "scripts" / "scaling_fit.py"


mpl.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
        "font.size": 7,
        "axes.linewidth": 0.8,
        "axes.spines.right": False,
        "axes.spines.top": False,
        "legend.frameon": False,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
    }
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError("没有可写数据")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def load_selected() -> dict[tuple[float, float, int], dict[int, dict[str, float]]]:
    grouped: dict[tuple[float, float, int], dict[int, dict[str, float]]] = defaultdict(dict)
    for row in read_csv(ANALYSIS / "candidate_audit.csv"):
        if row["selected"] != "True":
            continue
        key = (float(row["alpha"]), float(row["beta"]), int(row["N_units"]))
        sector = int(row["target_sz"])
        grouped[key][sector] = {
            "energy": float(row["energy"]),
            "variance_per_site": float(row["variance_per_site"]),
            "final_energy_change": abs(float(row["final_energy_change"])),
        }
    if any(set(sectors) != {0, 1} for sectors in grouped.values()):
        raise ValueError("存在不完整的 Sz=0/1 扇区配对")
    return grouped


def load_effective() -> dict[tuple[float, float, int], dict[str, float]]:
    values = {}
    for row in read_csv(ANALYSIS / "effective_comparison.csv"):
        key = (float(row["alpha"]), float(row["beta"]), int(row["N_units"]))
        values[key] = {
            "jeff": float(row["jeff"]),
            "local_gap": float(row["local_gap"]),
            "control_ratio": float(row["beta_over_local_gap"]),
        }
    return values


def load_oracle() -> dict[int, float]:
    return {int(row["N_units"]): float(row["spin_gap"]) for row in read_csv(ORACLE)}


def build_rows() -> list[dict[str, object]]:
    selected = load_selected()
    effective = load_effective()
    oracle = load_oracle()
    rows = []
    for key in sorted(selected):
        alpha, beta, n_units = key
        sectors = selected[key]
        if key not in effective or n_units not in oracle:
            raise ValueError(f"缺少有效理论或 oracle 数据: {key}")
        gap = sectors[1]["energy"] - sectors[0]["energy"]
        l_sites = 5 * n_units
        # 方差残差范数与末扫能量漂移取较大者。
        sigma0 = max(
            math.sqrt(l_sites * sectors[0]["variance_per_site"]),
            sectors[0]["final_energy_change"],
        )
        sigma1 = max(
            math.sqrt(l_sites * sectors[1]["variance_per_site"]),
            sectors[1]["final_energy_change"],
        )
        gap_err = sigma0 + sigma1
        jeff = effective[key]["jeff"]
        normalized = gap / jeff
        normalized_err = gap_err / jeff
        oracle_gap = oracle[n_units]
        relative_deviation = (normalized - oracle_gap) / oracle_gap
        rows.append(
            {
                "alpha": alpha,
                "beta": beta,
                "N_units": n_units,
                "L_sites": l_sites,
                "control_ratio": effective[key]["control_ratio"],
                "spin_gap": gap,
                "spin_gap_err_proxy": gap_err,
                "J_eff": jeff,
                "gap_over_Jeff": normalized,
                "gap_over_Jeff_err_proxy": normalized_err,
                "oracle_gap": oracle_gap,
                "relative_deviation": relative_deviation,
                "controlled": effective[key]["control_ratio"] < 1.0,
            }
        )
    return rows


def run_scaling_fit(rows: list[dict[str, object]], scaling_script: Path) -> str:
    controlled = [
        {"N_units": row["N_units"], "obs": row["gap_over_Jeff"], "err": row["gap_over_Jeff_err_proxy"]}
        for row in rows
        if row["controlled"]
    ]
    input_path = OUTDIR / "controlled_scaling_input.csv"
    write_csv(input_path, controlled)
    if not scaling_script.is_file():
        raise FileNotFoundError(f"找不到 scaling_fit.py: {scaling_script}")
    command = [
        str(Path(sys.executable)),
        str(scaling_script),
        str(input_path),
        "--form",
        "power-law",
        "--size-col",
        "N_units",
        "--obs-col",
        "obs",
        "--err-col",
        "err",
        "--bootstrap",
        "1000",
        "--seed",
        "20260731",
        "--out-csv",
        str(OUTDIR / "scaling-fit.csv"),
        "--out-png",
        str(OUTDIR / "scaling-fit.png"),
    ]
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    invocation = " ".join(command)
    (OUTDIR / "scaling-fit-command.txt").write_text(invocation + "\n", encoding="utf-8")
    (OUTDIR / "scaling-fit-stdout.txt").write_text(completed.stdout, encoding="utf-8")
    return invocation


def read_fit() -> dict[str, dict[str, float | None]]:
    result = {}
    for row in read_csv(OUTDIR / "scaling-fit.csv"):
        result[row["parameter"]] = {
            "value": float(row["value"]),
            "ci_lo": float(row["ci_lo"]) if row["ci_lo"] else None,
            "ci_hi": float(row["ci_hi"]) if row["ci_hi"] else None,
        }
    return result


def series_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[float, float], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[(float(row["alpha"]), float(row["beta"]))].append(row)
    summary = []
    for (alpha, beta), points in sorted(grouped.items()):
        deviations = [abs(float(point["relative_deviation"])) for point in points]
        summary.append(
            {
                "alpha": alpha,
                "beta": beta,
                "control_ratio": float(points[0]["control_ratio"]),
                "mean_abs_relative_deviation": sum(deviations) / len(deviations),
                "max_abs_relative_deviation": max(deviations),
                "controlled": bool(points[0]["controlled"]),
            }
        )
    return summary


def make_figure(rows: list[dict[str, object]], summaries: list[dict[str, object]]) -> None:
    colors = ["#3B6FB6", "#2A9D8F", "#7A7A7A", "#D28E2C", "#B85C5C", "#8064A2"]
    markers = ["o", "s", "^", "D", "v", "P"]
    grouped: dict[tuple[float, float], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[(float(row["alpha"]), float(row["beta"]))].append(row)

    width = 183 / 25.4
    fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(width, 3.15), gridspec_kw={"width_ratios": [1.55, 1]})
    oracle_by_n = {int(row["N_units"]): float(row["oracle_gap"]) for row in rows}
    ns = sorted(oracle_by_n)
    ax0.plot(ns, [oracle_by_n[n] for n in ns], color="black", lw=1.6, marker="x", ms=5, label="Heisenberg oracle")
    for index, ((alpha, beta), points) in enumerate(sorted(grouped.items())):
        points = sorted(points, key=lambda item: int(item["N_units"]))
        ax0.errorbar(
            [point["N_units"] for point in points],
            [point["gap_over_Jeff"] for point in points],
            yerr=[point["gap_over_Jeff_err_proxy"] for point in points],
            color=colors[index],
            marker=markers[index],
            ms=4,
            lw=1.0,
            capsize=2,
            label=rf"$\alpha={alpha:g},\ \beta={beta:g}$",
        )
    ax0.set(xlabel="Pentamer units, $N$", ylabel=r"Normalized spin gap, $\Delta_s/J_{\rm eff}$", xticks=ns)
    ax0.legend(fontsize=6, ncol=2, handlelength=1.6, columnspacing=0.8)
    ax0.text(-0.13, 1.03, "a", transform=ax0.transAxes, fontsize=8, fontweight="bold")

    for index, item in enumerate(summaries):
        face = colors[index]
        ax1.scatter(
            item["control_ratio"],
            100 * item["mean_abs_relative_deviation"],
            color=face,
            marker=markers[index],
            s=27,
            edgecolor="black" if not item["controlled"] else face,
            linewidth=0.8,
            zorder=3,
        )
        if not item["controlled"]:
            ax1.annotate(
                rf"excluded: $({item['alpha']:g},{item['beta']:g})$",
                (item["control_ratio"], 100 * item["mean_abs_relative_deviation"]),
                xytext=(5, 4),
                textcoords="offset points",
                fontsize=5.5,
            )
    ax1.axvline(1.0, color="#777777", lw=0.8, ls="--")
    ax1.text(1.0, 0.98, "projection limit", transform=ax1.get_xaxis_transform(), ha="right", va="top", fontsize=5.5)
    ax1.set(
        xlabel=r"Control ratio, $\beta/\Delta_{\rm local}$",
        ylabel="Mean absolute oracle deviation (%)",
        xscale="log",
    )
    ax1.text(-0.16, 1.03, "b", transform=ax1.transAxes, fontsize=8, fontweight="bold")
    fig.tight_layout(w_pad=1.8)
    base = OUTDIR / "effective_gap_scaling"
    fig.savefig(base.with_suffix(".svg"), bbox_inches="tight")
    fig.savefig(base.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(base.with_suffix(".png"), dpi=300, bbox_inches="tight")
    fig.savefig(base.with_suffix(".tiff"), dpi=600, bbox_inches="tight", pil_kwargs={"compression": "tiff_lzw"})
    plt.close(fig)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scaling-script", type=Path, default=DEFAULT_SCALING)
    args = parser.parse_args()
    OUTDIR.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    write_csv(OUTDIR / "effective_gap_scaling.csv", rows)
    invocation = run_scaling_fit(rows, args.scaling_script)
    summaries = series_summary(rows)
    write_csv(OUTDIR / "series_summary.csv", summaries)
    make_figure(rows, summaries)
    fit = read_fit()
    controlled = [item for item in summaries if item["controlled"]]
    smallest = min(summaries, key=lambda item: item["control_ratio"])
    largest = max(summaries, key=lambda item: item["control_ratio"])
    oracle = load_oracle()
    oracle_endpoint_slope = math.log(oracle[8] / oracle[16]) / math.log(2.0)
    summary = {
        "status": "tentative",
        "claim": "五条投影受控曲线近似 matched-size Heisenberg oracle，但尚未达到严格数值塌缩；投影失控点明显偏离。",
        "uncertainty_proxy": "每个扇区取 max(sqrt(L*variance_per_site), abs(final_energy_change))，能隙误差取两扇区之和。",
        "bootstrap_interpretation": "误差代理不是统计抽样误差；bootstrap 区间仅表示对该数值误差模型的敏感性。",
        "controlled_definition": "beta/local_gap < 1",
        "controlled_series": len(controlled),
        "total_series": len(summaries),
        "controlled_mean_abs_deviation_range": [
            min(item["mean_abs_relative_deviation"] for item in controlled),
            max(item["mean_abs_relative_deviation"] for item in controlled),
        ],
        "controlled_deviation_monotonic": False,
        "oracle_endpoint_effective_slope_N8_to_N16": oracle_endpoint_slope,
        "fit": fit,
        "smallest_control_ratio": smallest,
        "largest_control_ratio": largest,
        "scaling_invocation": invocation,
        "figure_contract": {
            "core_conclusion": "受控曲线近似 oracle，但偏差不随 beta/local_gap 单调变化；失控点明显破坏对应，不能宣称已完成普适塌缩。",
            "evidence_chain": ["a: 六条有限尺寸曲线与 matched-size oracle", "b: 每条曲线的平均绝对偏差随控制比变化"],
            "archetype": "quantitative grid",
            "backend": "Python/matplotlib",
            "export": "183 mm；SVG/PDF 可编辑文字；PNG 300 dpi；LZW TIFF 600 dpi",
        },
    }
    (OUTDIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    artifacts = sorted(path for path in OUTDIR.iterdir() if path.name != "checksums.sha256")
    (OUTDIR / "checksums.sha256").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in artifacts if path.is_file()),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
