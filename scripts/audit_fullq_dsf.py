"""完整动量谱验收、ED 对照及截图风格输出。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
try:
    import tomllib
except ModuleNotFoundError:
    from pip._vendor import toml as tomllib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from plot_dsf_screenshot_style import draw

ROOT = Path(__file__).resolve().parents[1]


def load_run(directory):
    meta = tomllib.loads((directory / "run_metadata.toml").read_text(encoding="utf-8"))
    q = np.loadtxt(directory / "q.csv", delimiter=",")
    omega = np.loadtxt(directory / "omega.csv", delimiter=",")
    spectrum = np.loadtxt(directory / "spectrum.csv", delimiter=",")
    if spectrum.shape != (len(q), len(omega)) or not np.isfinite(spectrum).all():
        raise ValueError(f"谱网格无效：{directory}")
    with (directory / "metrics.csv").open(newline="", encoding="utf-8") as handle:
        metrics = [{key: float(value) for key, value in row.items()} for row in csv.DictReader(handle)]
    return {"directory": directory, "metadata": meta, "q": q, "omega": omega,
            "spectrum": spectrum, "metrics": metrics}


def check_ed(directory, alpha, ed_directory):
    q = np.loadtxt(directory / "q.csv", delimiter=",")
    omega = np.loadtxt(directory / "omega.csv", delimiter=",")
    actual = np.loadtxt(directory / "spectrum.csv", delimiter=",")
    exact_q = np.loadtxt(ed_directory / "q.csv", delimiter=",")
    weights = np.loadtxt(ed_directory / f"a{alpha}_weights.csv", delimiter=",")
    gaps = np.loadtxt(ed_directory / f"a{alpha}_gaps.csv", delimiter=",")
    errors, exact_correlations = [], []
    for index, momentum in enumerate(q):
        match = np.flatnonzero(np.isclose(exact_q, momentum, atol=1e-12, rtol=0))
        if len(match) != 1:
            raise ValueError("ED 动量网格不匹配")
        data = np.loadtxt(directory / f"q{index + 1:03}_correlation.csv", delimiter=",", skiprows=1)
        time = data[:, 0]
        exact = np.exp(-1j * np.outer(time, gaps)) @ weights[:, match[0]]
        measured = data[:, 1] + 1j * data[:, 2]
        errors.append(float(np.linalg.norm(measured - exact) / max(np.linalg.norm(exact), 1e-14)))
        exact_correlations.append(exact)
    exact_correlations = np.array(exact_correlations)
    window = 1 - time / time[-1]
    window[0] *= 0.5
    exact_spectrum = np.real((np.exp(1j * np.outer(omega, time)) @
                              (exact_correlations * window).T).T) * ((time[1] - time[0]) / np.pi)
    spectral_error = float(np.linalg.norm(actual - exact_spectrum) / np.linalg.norm(exact_spectrum))
    reflection_error = float(np.linalg.norm(actual - actual[::-1]) / np.linalg.norm(actual))
    result = {"alpha": alpha, "L": 10, "relative_spectrum_error": spectral_error,
              "max_relative_correlation_error": max(errors), "inversion_relative_rms": reflection_error,
              "q0_max": float(np.max(np.abs(actual[[0, -1]]))),
              "passed": spectral_error < 0.002 and reflection_error < 1e-7}
    return result


def quality(run):
    s, q, meta = run["spectrum"], run["q"], run["metadata"]
    full_grid = (np.allclose(q + q[::-1], 2 * np.pi, atol=1e-12, rtol=0) and
                 np.isclose(q[0], 0, atol=1e-12, rtol=0) and
                 np.isclose(q[-1], 2 * np.pi, atol=1e-12, rtol=0))
    reflection = float(np.linalg.norm(s - s[::-1]) / np.linalg.norm(s)) if full_grid else None
    negative = float(-np.minimum(s, 0).sum() / max(np.abs(s).sum(), 1e-30))
    norm_drift = max(row["relative_norm_drift"] for row in run["metrics"])
    norm_api_error = max(row.get("norm_api_max_relative_error", 0.0) for row in run["metrics"])
    source_error = max(row["source_norm_error"] / row["source_norm"]
                       for row in run["metrics"] if row["source_norm"] > 1e-12)
    inversion_pass = full_grid and reflection < 0.002
    q0_maximum = float(np.max(np.abs(s[[0, -1]]))) if full_grid else None
    q0_pass = full_grid and q0_maximum < 1e-10
    baseline_pass = (inversion_pass and meta["variance_per_site"] < 1e-8 and
                     q0_pass and meta["static_reflection_relative_rms"] < 1e-6 and
                     not meta["clipping"] and not meta["inversion_averaging"] and
                     negative < 0.001 and norm_drift < 0.01 and source_error < 1e-7 and
                     norm_api_error < 1e-8)
    return {"inversion_relative_rms": reflection,
            "max_absolute_inversion_difference": float(np.max(np.abs(s - s[::-1]))) if full_grid else None,
            "negative_absolute_weight_fraction": negative, "minimum_spectrum": float(s.min()),
            "maximum_spectrum": float(s.max()), "maximum_relative_norm_drift": norm_drift,
            "maximum_norm_api_relative_error": norm_api_error,
            "maximum_relative_source_norm_error": source_error,
            "q0_maximum": q0_maximum, "q0_pass": bool(q0_pass),
            "inversion_pass": bool(inversion_pass), "baseline_pass": bool(baseline_pass)}


def crosscheck(base, refined):
    for key in ("alpha", "beta", "L", "tmax"):
        if base["metadata"][key] != refined["metadata"][key]:
            raise ValueError(f"收敛对照模型或时间不匹配：{key}")
    for key in ("itensors_version", "itensormps_version"):
        if base["metadata"].get(key) != refined["metadata"].get(key):
            raise ValueError(f"对照包版本不匹配：{key}")
    if abs(base["metadata"]["energy"] - refined["metadata"]["energy"]) > 1e-9:
        raise ValueError("同基态对照的基态能量不匹配")
    if not np.isclose(refined["metadata"]["dt"], base["metadata"]["dt"] / 2) or \
            refined["metadata"]["tebd_maxdim"] <= base["metadata"]["tebd_maxdim"]:
        raise ValueError("联合对照必须减半步长并增大键维数")
    indices = []
    for q in refined["q"]:
        match = np.flatnonzero(np.isclose(base["q"], q, atol=1e-12, rtol=0))
        if len(match) != 1:
            raise ValueError("收敛对照动量不匹配")
        indices.append(int(match[0]))
    if not np.array_equal(base["omega"], refined["omega"]):
        raise ValueError("收敛对照频率不匹配")
    a, b = base["spectrum"][indices], refined["spectrum"]
    source_a = np.array([base["metrics"][index]["source_norm"] for index in indices])
    source_b = np.array([row["source_norm"] for row in refined["metrics"]])
    source_error = float(np.linalg.norm(source_a - source_b) / max(np.linalg.norm(source_b), 1e-30))
    if source_error >= 1e-7:
        raise ValueError("同基态对照的初始静态谱权重不匹配")
    error = float(np.linalg.norm(a - b) / np.linalg.norm(b))
    low = base["omega"] <= 0.6
    low_error = float(np.linalg.norm(a[:, low] - b[:, low]) / np.linalg.norm(b[:, low]))
    weights_a = np.trapezoid(a[:, low], base["omega"][low], axis=1)
    weights_b = np.trapezoid(b[:, low], base["omega"][low], axis=1)
    weight_error = float(np.linalg.norm(weights_a - weights_b) / np.linalg.norm(weights_b))
    peaks_a = base["omega"][np.argmax(a, axis=1)]
    peaks_b = base["omega"][np.argmax(b, axis=1)]
    peak_drift = float(np.max(np.abs(peaks_a - peaks_b)))
    refined_drift = max(row["relative_norm_drift"] for row in refined["metrics"])
    reflected = np.allclose(refined["q"] + refined["q"][::-1], 2 * np.pi, atol=1e-12, rtol=0)
    reflection = float(np.linalg.norm(b - b[::-1]) / np.linalg.norm(b)) if reflected else None
    negative = float(-np.minimum(b, 0).sum() / max(np.abs(b).sum(), 1e-30))
    result = {"q_over_pi": (refined["q"] / np.pi).tolist(), "relative_spectrum_error": error,
              "low_energy_relative_error": low_error, "low_energy_weight_relative_error": weight_error,
              "maximum_peak_drift": peak_drift, "refined_maximum_norm_drift": refined_drift,
              "refined_inversion_relative_rms": reflection, "refined_negative_weight_fraction": negative,
              "refined_dt": refined["metadata"]["dt"],
              "refined_tebd_maxdim": refined["metadata"]["tebd_maxdim"],
              "base_julia_version": base["metadata"].get("julia_version"),
              "refined_julia_version": refined["metadata"].get("julia_version"),
              "relative_source_weight_difference": source_error,
              "runtime_changed": base["metadata"].get("julia_version") !=
                                 refined["metadata"].get("julia_version")}
    result["passed"] = bool(error < 0.03 and low_error < 0.05 and weight_error < 0.05 and
                            peak_drift <= 0.015 + 1e-12 and refined_drift < 0.01 and
                            reflected and reflection < 0.002 and negative < 0.001)
    return result


def time_check(run):
    q, omega = run["q"], run["omega"]
    indices = [int(np.argmin(np.abs(q - value * np.pi))) for value in (0.4, 0.7, 1.0)]
    rows = []
    for index in indices:
        data = np.loadtxt(run["directory"] / f"q{index + 1:03}_correlation.csv", delimiter=",", skiprows=1)
        half = data[:(len(data) - 1) // 2 + 1]
        t, corr = half[:, 0], half[:, 1] + 1j * half[:, 2]
        window = 1 - t / t[-1]
        window[0] *= 0.5
        spectrum = np.real(np.exp(1j * np.outer(omega, t)) @ (window * corr)) * ((t[1] - t[0]) / np.pi)
        low = omega <= 0.6
        old_index = int(np.argmax(spectrum[low]))
        new_index = int(np.argmax(run["spectrum"][index, low]))
        old_peak = omega[low][old_index]
        new_peak = omega[low][new_index]
        rows.append({"q_over_pi": float(q[index] / np.pi), "short_time": float(t[-1]),
                     "short_window_maximum": float(old_peak), "full_window_maximum": float(new_peak),
                     "maximum_location_drift": float(abs(old_peak - new_peak)),
                     "boundary_maximum": old_index in (0, np.count_nonzero(low) - 1) or
                                          new_index in (0, np.count_nonzero(low) - 1),
                     "resolved_excitation_claim": False})
    return rows


def load_gap(path, metadata):
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    matches = [case for case in data["cases"] if all(
        case[key] == metadata[key] for key in ("alpha", "beta", "L"))]
    if len(matches) != 1:
        raise ValueError("能隙数据与谱模型不匹配")
    case = matches[0]
    if case["budget_drift"] >= 1e-6 or max(case["variance_sz0"], case["variance_sz1"]) > 1e-10:
        raise ValueError("能隙预算或方差检查未通过")
    return {**case, "method": data["method"], "rigorous_error_bound": data["rigorous_error_bound"],
            "thermodynamic_extrapolation": data["thermodynamic_extrapolation"],
            "gap_smaller_than_current_window_fwhm": bool(case["gap768"] < metadata["window_fwhm"]),
            "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def check_partial(run, directory):
    metadata = tomllib.loads((directory / "partial_metadata.toml").read_text(encoding="utf-8"))
    for key in ("alpha", "beta", "L", "dt", "tebd_maxdim"):
        if metadata[key] != run["metadata"][key]:
            raise ValueError(f"部分关联核验参数不匹配：{key}")
    if abs(metadata["energy"] - run["metadata"]["energy"]) > 1e-9:
        raise ValueError("部分关联核验的基态不匹配")
    rows = []
    for cell in metadata["cells"]:
        indices = np.flatnonzero(np.isclose(run["q"], cell["q"], atol=1e-12, rtol=0))
        if len(indices) != 1:
            raise ValueError("部分关联动量不匹配")
        a = np.loadtxt(directory / f"{cell['name']}_correlation.csv", delimiter=",", skiprows=1)
        b = np.loadtxt(run["directory"] / f"q{indices[0] + 1:03}_correlation.csv", delimiter=",", skiprows=1)
        if len(a) > len(b) or not np.allclose(a[:, 0], b[:len(a), 0], atol=1e-12, rtol=0):
            raise ValueError("部分关联时间不匹配")
        ac, bc = a[:, 1] + 1j * a[:, 2], b[:len(a), 1] + 1j * b[:len(a), 2]
        negligible = bool(abs(ac[0]) < 1e-20)
        error = None if negligible else float(np.linalg.norm(ac - bc) / np.linalg.norm(ac))
        rows.append({"q_over_pi": float(cell["q"] / np.pi), "t_reached": float(a[-1, 0]),
                     "relative_correlation_error": error, "conserved_zero_source": negligible})
    maximum = max((row["relative_correlation_error"] for row in rows
                   if row["relative_correlation_error"] is not None), default=None)
    return {"julia_version": metadata["julia_version"], "partial_only": True,
            "merged_into_final_spectrum": False, "cells": rows,
            "maximum_relative_correlation_error": maximum,
            "passed": maximum is not None and maximum < 0.002}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", nargs="+", type=Path)
    parser.add_argument("--checks", nargs="*", type=Path, default=[])
    parser.add_argument("--output", type=Path, default=ROOT / "figures/fullq_dsf_20261001")
    parser.add_argument("--vmax", type=float, default=3.0)
    parser.add_argument("--ed-check", type=Path)
    parser.add_argument("--alpha", type=float)
    parser.add_argument("--gap-file", type=Path)
    parser.add_argument("--partial-check", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.ed_check:
        if args.alpha is None:
            parser.error("ED 对照需要 --alpha")
        result = check_ed(args.ed_check, args.alpha, ROOT / "results/fullq_dsf_20261001/ed_L10")
        (args.ed_check / "ed_crosscheck.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
        if not result["passed"]:
            raise SystemExit("小体系 ED 对照未通过")
        return
    if not args.inputs or args.vmax <= 0:
        parser.error("需要有效输入和正色标上限")
    runs = [load_run(path) for path in args.inputs]
    checks = [load_run(path) for path in args.checks]
    plt.rcParams.update({"font.family": "Arial", "mathtext.fontset": "stixsans",
                         "pdf.fonttype": 42, "svg.fonttype": "none"})
    results = []
    for run in runs:
        meta = run["metadata"]
        qa = quality(run)
        gap = load_gap(args.gap_file, meta) if args.gap_file else None
        partial = None
        if args.partial_check:
            partial_meta = tomllib.loads((args.partial_check / "partial_metadata.toml").read_text(encoding="utf-8"))
            if partial_meta["alpha"] == meta["alpha"]:
                partial = check_partial(run, args.partial_check)
        matching = [refined for refined in checks if refined["metadata"]["alpha"] == meta["alpha"]]
        refinement = crosscheck(run, matching[0]) if matching else None
        independent_pass = partial is None or partial["passed"]
        accepted = qa["baseline_pass"] and refinement is not None and refinement["passed"] and independent_pass
        status = "accepted" if accepted else "symmetry_checked_draft" if qa["baseline_pass"] and independent_pass else "diagnostic_only"
        prefix = f"Sqw_L{meta['L']}_J2={meta['alpha']:g}_J3={meta['beta']:g}_{status}"
        for label, ymax in (("full", 4.0), ("low", 0.6)):
            draw(run["spectrum"], run["q"], run["omega"], meta["alpha"], meta["beta"], ymax,
                 args.vmax, args.output / f"{prefix}_{label}")
        results.append({"directory": str(run["directory"].resolve()), "metadata": meta,
                        "quality": qa, "refinement": refinement, "time_resolution_check": time_check(run),
                        "finite_chain_spin_gap": gap, "partial_environment_check": partial,
                        "status": status, "vmin": 0, "vmax": args.vmax,
                        "display_saturation_fraction": float(np.mean(run["spectrum"] > args.vmax)),
                        "spectrum_sha256": hashlib.sha256((run["directory"] / "spectrum.csv").read_bytes()).hexdigest()})
    manifest = {"smoothing": False, "spatial_interpolation": False, "inversion_averaging": False,
                "source_clipping": False, "display_saturation_only": True,
                "style": "user reference screenshot", "results": results}
    (args.output / "qa.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# L=40 完整动量谱复算", "", "使用完整连通动量算符，自相关包含 t=0；三角时间窗，不做高斯平滑、镜像平均或数据裁剪。", "",
             f"色标为共同线性范围 0 至 {args.vmax:g}；超过 vmax 的数值仅显示饱和，原始谱值不变。", ""]
    for result in results:
        meta, qa = result["metadata"], result["quality"]
        prefix = f"Sqw_L{meta['L']}_J2={meta['alpha']:g}_J3={meta['beta']:g}_{result['status']}"
        lines.extend([f"## J2={meta['alpha']}, J3={meta['beta']}",
                      f"状态：{result['status']}。L={meta['L']}，dt={meta['dt']}，T={meta['tmax']}，TEBD χ={meta['tebd_maxdim']}。",
                      f"反演相对 RMS：{qa['inversion_relative_rms']:.4g}；最大范数漂移：{qa['maximum_relative_norm_drift']:.4g}；负谱绝对权重比例：{qa['negative_absolute_weight_fraction']:.4g}。",
                      f"基态方差/格点：{meta['variance_per_site']:.4g}；时间窗 FWHM≈{meta['window_fwhm']:.4g} J1。",
                      "低于此分辨率的峰间距不能仅凭图认定已分开。",
                      f"[全能段 PNG]({(args.output / (prefix + '_full.png')).resolve().as_posix()}) | "
                      f"[低能 PNG]({(args.output / (prefix + '_low.png')).resolve().as_posix()})",
                      f"[全能段 PDF]({(args.output / (prefix + '_full.pdf')).resolve().as_posix()}) | "
                      f"[全能段 SVG]({(args.output / (prefix + '_full.svg')).resolve().as_posix()})；低能图同样提供 PDF/SVG。",
                      f"[原始谱 CSV]({(Path(result['directory']) / 'spectrum.csv').as_posix()}) | "
                      f"[计算元数据]({(Path(result['directory']) / 'run_metadata.toml').as_posix()})", ""])
        if result["refinement"]:
            ref = result["refinement"]
            lines.extend([f"dt/2 与 χ 增大的联合对照：谱 RMS 差异 {ref['relative_spectrum_error']:.4g}；低能权重差异 {ref['low_energy_weight_relative_error']:.4g}；最大主峰漂移 {ref['maximum_peak_drift']:.4g} J1。", ""])
            if ref["runtime_changed"]:
                lines.extend([f"本对照同时包含运行环境差异：Julia {ref['base_julia_version']} → {ref['refined_julia_version']}；ITensor 包版本一致，使用同一基态。不能将差异分别归因于步长或键维数。", ""])
        if result["finite_chain_spin_gap"]:
            gap = result["finite_chain_spin_gap"]
            lines.extend([f"开放有限链自旋隙 E(Sz=1)-E(Sz=0)：{gap['gap768']:.8g} J1；χ=512/768 与 cutoff=1e-12/1e-13 联合预算差异 {gap['budget_drift']:.4g} J1。",
                          "这是有限链能级差，可能受边界态影响；不是热力学极限体相能隙，预算差异也不是严格误差界。",
                          "该能隙小于当前时间窗的 FWHM，不宣称热图已将其与零频区分。" if gap["gap_smaller_than_current_window_fwhm"] else
                          "时间窗宽度小于该能级差，但峰的识别仍需实际谱权重及时间收敛证据。", ""])
        if result["partial_environment_check"]:
            partial = result["partial_environment_check"]
            lines.extend([f"服务器部分时间段独立核验：{len(partial['cells'])} 个动量单元；最大关联函数相对差异 {partial['maximum_relative_correlation_error']:.4g}。",
                          "服务器部分关联仅用于核验，没有拼接或补入最终谱。", ""])
    lines.extend(["## 复算与核查",
                  f"[详细验收数据]({(args.output / 'qa.json').resolve().as_posix()}) | "
                  f"[计算协议]({(ROOT / 'docs/fullq_dsf_protocol_20261001.md').as_posix()}) | "
                  f"[最终源码快照]({(ROOT / 'results/fullq_dsf_20261001/source_final_20261001.tar').as_posix()})",
                  "accepted 表示通过本次内部数值标准，不代表热力学极限或所有低能峰已可分辨。", ""])
    (args.output / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    if any(not result["quality"]["baseline_pass"] for result in results):
        raise SystemExit("初始谱验收未通过，图像仅供诊断")
    if args.checks and any(result["status"] != "accepted" for result in results):
        raise SystemExit("联合收敛对照未通过")
    if any(result["partial_environment_check"] is not None and not result["partial_environment_check"]["passed"]
           for result in results):
        raise SystemExit("服务器部分关联核验未通过")


if __name__ == "__main__":
    main()
