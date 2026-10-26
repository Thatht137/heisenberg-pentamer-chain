"""核对有限时间谱的离散积分、频率分配与静态源范数。"""

from __future__ import annotations

import os

for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[variable] = "1"

import csv
import hashlib
import json
import time
from datetime import date
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/submission_20261002/window_audit"
RUNS = {
    "positive": ROOT / "results/fullq_dsf_20261001/L40_positive",
    "negative": ROOT / "results/fullq_dsf_20261001/L40_negative_local",
}
NFFTS = (32768, 65536)
TARGET_Q_PI = (0.2, 0.6, 1.0)
STARTED = time.monotonic()


def checkpoint() -> None:
    if time.monotonic() - STARTED > 280:
        raise RuntimeError("审计超过五分钟预算")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def span(rows: list[dict], key: str) -> dict:
    low = min(rows, key=lambda row: row[key])
    high = max(rows, key=lambda row: row[key])
    return {"min": low[key], "max": high[key],
            "min_q_over_pi": low["q_over_pi"], "max_q_over_pi": high["q_over_pi"]}


def audit_run(label: str, run: Path) -> tuple[dict, list[dict]]:
    q = np.loadtxt(run / "q.csv", delimiter=",")
    omegas = np.loadtxt(run / "omega.csv", delimiter=",")
    saved = np.loadtxt(run / "spectrum.csv", delimiter=",")
    metrics = np.genfromtxt(run / "metrics.csv", delimiter=",", names=True)
    if q.shape != (41,) or saved.shape != (41, len(omegas)):
        raise ValueError(f"{label}: 生产谱维度不符")
    np.testing.assert_allclose(q / np.pi, metrics["q_over_pi"], atol=1e-13, rtol=0)
    inputs = [run / name for name in ("q.csv", "omega.csv", "spectrum.csv", "metrics.csv", "run_metadata.toml")]
    correlations = []
    times = None
    for index in range(1, len(q) + 1):
        path = run / f"q{index:03d}_correlation.csv"
        values = np.genfromtxt(path, delimiter=",", names=True)
        inputs.append(path)
        if times is None:
            times = values["time"]
        else:
            np.testing.assert_allclose(values["time"], times, atol=0, rtol=0)
        correlations.append(values["real_corr"] + 1j * values["imag_corr"])
    corr = np.array(correlations)
    dt = float(times[1] - times[0])
    duration = float(times[-1])
    np.testing.assert_allclose(times, np.arange(len(times)) * dt, atol=1e-12, rtol=0)
    if len(times) != 1201 or abs(dt - 0.05) > 1e-14 or duration != 60:
        raise ValueError(f"{label}: 时间网格不符")
    if not np.all(np.isfinite(corr)) or not np.all(np.isfinite(saved)):
        raise ValueError(f"{label}: 非有限值")
    c0 = corr[:, 0].real
    np.testing.assert_allclose(corr[:, 0].imag, 0, atol=1e-15, rtol=0)
    np.testing.assert_allclose(c0, metrics["source_norm"], atol=1e-15, rtol=1e-14)
    nonzero = c0 > 1e-20
    static_error = np.abs(c0 - metrics["expected_static_norm"])
    static_relative = static_error[nonzero] / np.abs(metrics["expected_static_norm"][nonzero])
    np.testing.assert_allclose(static_error, metrics["source_norm_error"], atol=2e-16, rtol=1e-4)
    if static_error.max() > 1e-8 or static_relative.max() > 1e-8:
        raise ValueError(f"{label}: 初始源范数与静态收缩不符")
    weights = 1 - times / duration
    weights[0] *= 0.5
    weights[-1] = 0.0
    weighted = corr * weights[None, :]

    # 与生产网格直接积分比对，独立于 FFT 频率节点。
    reconstructed = (np.exp(1j * np.outer(omegas, times)) @ weighted.T).real.T * dt / np.pi
    direct_abs_error = float(np.max(np.abs(reconstructed - saved)))
    direct_rms_relative = float(np.linalg.norm(reconstructed - saved) / np.linalg.norm(saved))
    if direct_abs_error > 1e-11 or direct_rms_relative > 1e-11:
        raise ValueError(f"{label}: 保存谱与原始关联的重建不符")
    rows = []
    for nfft in NFFTS:
        checkpoint()
        spectrum = np.fft.ifft(weighted, n=nfft, axis=1).real * nfft * dt / np.pi
        omega = 2 * np.pi * np.fft.fftfreq(nfft, d=dt)
        delta = 2 * np.pi / (nfft * dt)
        zero_weight = 0.5 * spectrum[:, 0] * delta
        negative_weight = spectrum[:, omega < 0].sum(axis=1) * delta + zero_weight
        band_weight = spectrum[:, (omega > 0) & (omega <= 4)].sum(axis=1) * delta + zero_weight
        high_weight = spectrum[:, omega > 4].sum(axis=1) * delta
        total_weight = spectrum.sum(axis=1) * delta
        negative_value_weight = np.minimum(spectrum, 0.0).sum(axis=1) * delta
        if np.max(np.abs(total_weight - c0)) > 1e-12:
            raise ValueError(f"{label}: FFT 全周期代数恒等式未通过")
        np.testing.assert_allclose(negative_weight + band_weight + high_weight, total_weight,
                                   atol=1e-13, rtol=1e-13)
        for index, value in enumerate(q):
            denominator = float(c0[index]) if nonzero[index] else None
            fraction = lambda array: float(array[index] / denominator) if denominator is not None else None
            rows.append({
                "parameter": label, "q_index": index + 1, "q_over_pi": float(value / np.pi),
                "nfft": nfft, "delta_omega": delta, "dt": dt, "tmax": duration,
                "c0": float(c0[index]), "expected_static_norm": float(metrics["expected_static_norm"][index]),
                "source_norm_abs_error": float(static_error[index]),
                "near_zero_source": not bool(nonzero[index]), "full_period_integral": float(total_weight[index]),
                "full_period_algebra_abs_error": float(abs(total_weight[index] - c0[index])),
                "negative_frequency_weight": float(negative_weight[index]),
                "positive_0_to_4_weight": float(band_weight[index]),
                "positive_above_4_weight": float(high_weight[index]),
                "negative_frequency_fraction": fraction(negative_weight),
                "positive_0_to_4_fraction": fraction(band_weight),
                "positive_above_4_fraction": fraction(high_weight),
                "negative_nyquist_bin_weight": float(spectrum[index, nfft // 2] * delta),
                "half_zero_bin_weight": float(zero_weight[index]),
                "signed_integral_of_negative_spectrum_values": float(negative_value_weight[index]),
                "minimum_signed_spectrum_value": float(spectrum[index].min()),
            })
    coarse = [row for row in rows if row["nfft"] == NFFTS[0]]
    fine = [row for row in rows if row["nfft"] == NFFTS[1]]
    deltas = []
    for left, right in zip(coarse, fine):
        if right["near_zero_source"]:
            continue
        deltas.append({"q_over_pi": right["q_over_pi"], **{
            f"{key}_abs_change": abs(right[key] - left[key])
            for key in ("negative_frequency_fraction", "positive_0_to_4_fraction", "positive_above_4_fraction")
        }})
    fine_nonzero = [row for row in fine if not row["near_zero_source"]]
    summary = {
        "source": relative(run), "q_count": len(q), "nonzero_source_q_count": int(nonzero.sum()),
        "dt": dt, "tmax": duration, "times_count": len(times), "omega_max_production": float(omegas[-1]),
        "source_c0_max_absolute_difference": float(np.max(np.abs(c0 - metrics["source_norm"]))),
        "static_max_absolute_error": float(static_error.max()),
        "static_max_relative_error_nonzero_source": float(static_relative.max()),
        "direct_production_spectrum_max_absolute_error": direct_abs_error,
        "direct_production_spectrum_relative_rms_error": direct_rms_relative,
        "fft_full_period_max_absolute_algebra_error": max(row["full_period_algebra_abs_error"] for row in rows),
        "fine_grid_minimum_signed_spectrum_value": min(row["minimum_signed_spectrum_value"] for row in fine),
        "fine_grid_most_negative_signed_integral": min(row["signed_integral_of_negative_spectrum_values"] for row in fine),
        "negative_nyquist_bin_max_abs_weight_fine": max(abs(row["negative_nyquist_bin_weight"]) for row in fine),
        "fine_grid_fraction_ranges_nonzero_source": {
            key: span(fine_nonzero, key) for key in
            ("negative_frequency_fraction", "positive_0_to_4_fraction", "positive_above_4_fraction")
        },
        "grid_refinement_max_fraction_changes": {
            key: span(deltas, key) for key in deltas[0] if key != "q_over_pi"
        },
        "grid_refinement_by_q": deltas,
        "near_zero_source_rows": [row for row in fine if row["near_zero_source"]],
        "input_sha256": {relative(path): digest(path) for path in inputs},
    }
    return summary, rows


def write_readme(report: dict, selected: list[dict]) -> None:
    lines = [
        "# 有限时间谱的频率积分审计", "", f"日期：{report['date']}。仅分析已有生产 C(q,t)，不改变原图、谱值或时间序列。", "",
        "## 方法与边界", "",
        "使用原生产三角窗 w(t)=1-t/T；t=0 取梯形半权，t=T 权重为零。",
        "S_k=Re[ifft(w*C,Nfft)*Nfft]*dt/pi，omega_k=2*pi*fftfreq(Nfft,dt)。",
        "完整离散周期 [-pi/dt,pi/dt) 的 sum(S_k)*delta_omega=C(0) 是 FFT 代数恒等式，不是独立物理和规则验证，也不是无穷频域积分的收敛证明。",
        "这里只覆盖同一有限时间、离散时间信号的一个频率周期；时间采样导致周期化/混叠，增加零填充 Nfft 不增加物理时间分辨率。", "",
        "划分规则：omega=0 节点一半分入负频、一半分入正频 0..4；负 Nyquist 节点 -pi/dt 全部分入负频。",
        "0..4 使用满足 0<omega<=4 的节点，>4 使用 4<omega<pi/dt 的节点。4 不恰好在节点上；不插值边界，双网格差反映此节点划分与积分离散误差。",
        "所有权重都是 signed 求和。未截去负谱值；negative_frequency 指频率小于零的权重，不等于负的谱密度。",
        "分母统一用 C(0)，不是只用可见正频范围重新归一化。q=0 与 2pi 的接近零源范数单列，不报告比例。", "",
        "## 关键动量：Nfft=65536", "",
        "| J2/J1 | q/pi | 负频权重/C0 (%) | 0..4 权重/C0 (%) | >4 权重/C0 (%) |", "|---|---:|---:|---:|---:|",
    ]
    for row in selected:
        if row["nfft"] != NFFTS[-1]:
            continue
        sign = "+0.5" if row["parameter"] == "positive" else "-0.5"
        lines.append(f"| {sign} | {row['q_over_pi']:.1f} | {100 * row['negative_frequency_fraction']:.6f} | {100 * row['positive_0_to_4_fraction']:.6f} | {100 * row['positive_above_4_fraction']:.6f} |")
    lines += ["", "## 审计性质", "",
              "C(0) 与 source_norm 的一致性是保存值检查；C(0) 与 expected_static_norm 的一致性来自同一基态的源态范数与独立静态双点关联收缩两条计算路径。它不检验基态本身的误差。",
              "在原生产 omega 网格上重新进行直接梯形积分，并逐值核对 spectrum.csv；这检查时间数据、窗和傅里叶约定的一致性，不是独立求解动力学。",
              "有限时间窗把低能谱权扩展至负频；负频比例不能被直接解释为物理负频激发，也不能被裁去后宣称满足原始和规则。", ""]
    for label, item in report["runs"].items():
        change = item["grid_refinement_max_fraction_changes"]
        lines += [f"### {label}", "",
                  f"- 独立静态收缩最大相对差（非零源）：{item['static_max_relative_error_nonzero_source']:.6e}。",
                  f"- 原网格谱重建最大绝对差：{item['direct_production_spectrum_max_absolute_error']:.6e}；相对 RMS：{item['direct_production_spectrum_relative_rms_error']:.6e}。",
                  f"- 全周期代数恒等式最大绝对误差：{item['fft_full_period_max_absolute_algebra_error']:.6e}。",
                  f"- 双网格负频比例最大变化：{change['negative_frequency_fraction_abs_change']['max']:.6e}（绝对比例，不是相对误差）。",
                  f"- 双网格 0..4 比例最大变化：{change['positive_0_to_4_fraction_abs_change']['max']:.6e}。",
                  f"- 双网格 >4 比例最大变化：{change['positive_above_4_fraction_abs_change']['max']:.6e}。", ""]
    lines += ["完整 41 动量及两种 Nfft 见 all_q.csv，关键六组见 selected_q.csv，全部输入哈希与近零源检查见 summary.json。", ""]
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    summaries = {}
    all_rows = []
    for label, run in RUNS.items():
        summaries[label], rows = audit_run(label, run)
        all_rows.extend(rows)
    selected = [row for row in all_rows if any(abs(row["q_over_pi"] - target) < 1e-12 for target in TARGET_Q_PI)]
    report = {
        "schema": "spectral_window_audit/v1", "date": date.today().isoformat(),
        "nfft_values": list(NFFTS), "fft_integral_is_algebraic_identity": True,
        "independent_ground_state_validation": False, "infinite_frequency_sum_rule_claimed": False,
        "window": "triangular, t0 half weight, terminal zero", "frequency_period": "[-pi/dt,pi/dt)",
        "zero_bin_partition": "half to negative-frequency and half to [0,4]",
        "negative_nyquist_partition": "entire -pi/dt node assigned to negative-frequency",
        "negative_spectrum_clipped": False, "frequency_boundary_interpolation": False,
        "source_zero_threshold": 1e-20, "cpu_threads_requested": 1,
        "runs": summaries, "elapsed_seconds": time.monotonic() - STARTED,
        "script_sha256": digest(Path(__file__)), "numpy_version": np.__version__,
    }
    write_csv(OUT / "all_q.csv", all_rows)
    write_csv(OUT / "selected_q.csv", selected)
    tex = [r"\begin{tabular}{rrrrr}", r"\hline", r"$J_2/J_1$ & $q/\pi$ & $f_{-}$ (\%) & $f_{[0,4]}$ (\%) & $f_{>4}$ (\%) \\", r"\hline"]
    for row in selected:
        if row["nfft"] != NFFTS[-1]:
            continue
        sign = "+0.5" if row["parameter"] == "positive" else "-0.5"
        tex.append(f"{sign} & {row['q_over_pi']:.1f} & {100 * row['negative_frequency_fraction']:.3f} & "
                   f"{100 * row['positive_0_to_4_fraction']:.3f} & {100 * row['positive_above_4_fraction']:.3f} " + r"\\")
    tex += [r"\hline", r"\end{tabular}"]
    (OUT / "appendix_table.tex").write_text("\n".join(tex) + "\n", encoding="utf-8")
    (OUT / "summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_readme(report, selected)
    checkpoint()
    print(json.dumps({"output": relative(OUT), "elapsed_seconds": report["elapsed_seconds"],
                      "selected_fine": [row for row in selected if row["nfft"] == NFFTS[-1]]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
