#!/usr/bin/env python3
"""验收严格 q=pi TEBD 生产结果，并区分已通过门槛与证据缺口。"""

from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
import math
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_checksums(run: Path) -> tuple[bool, list[str]]:
    checksum_path = run / "checksums.sha256"
    failures: list[str] = []
    if not checksum_path.is_file():
        return False, ["缺少 checksums.sha256"]
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split(maxsplit=1)
        target = (run / relative.strip()).resolve()
        try:
            target.relative_to(run)
        except ValueError:
            failures.append(f"checksum 路径越界: {relative}")
            continue
        if not target.is_file():
            failures.append(f"checksum 文件缺失: {relative}")
        elif sha256(target) != expected:
            failures.append(f"checksum 不匹配: {relative}")
    return not failures, failures


def read_spectrum(path: Path) -> tuple[list[float], list[float]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    omegas = [float(row["omega"]) for row in rows]
    values = [float(row["intensity"]) for row in rows]
    if len(omegas) < 2 or omegas != sorted(omegas) or len(set(omegas)) != len(omegas):
        raise ValueError(f"频率网格无效: {path}")
    if not all(math.isfinite(value) for value in omegas + values):
        raise ValueError(f"频谱含非有限值: {path}")
    return omegas, values


def read_correlation(path: Path) -> tuple[list[float], list[complex]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    times = [float(row["time"]) for row in rows]
    values = [complex(float(row["real_corr"]), float(row["imag_corr"])) for row in rows]
    if len(times) < 2 or times != sorted(times) or len(set(times)) != len(times):
        raise ValueError(f"时间网格无效: {path}")
    if abs(times[0]) > 1e-14:
        raise ValueError(f"相关函数没有从 t=0 开始: {path}")
    finite = [part for value in values for part in (value.real, value.imag)]
    if not all(math.isfinite(value) for value in times + finite):
        raise ValueError(f"相关函数含非有限值: {path}")
    return times, values


def fourier_spectrum(
    times: list[float], correlations: list[complex], omegas: list[float], eta: float
) -> list[float]:
    if len(times) != len(correlations) or len(times) < 2:
        raise ValueError("时间与相关函数长度不一致")
    result: list[float] = []
    for omega in omegas:
        values = [
            complex(math.cos(omega * time), math.sin(omega * time))
            * math.exp(-eta * time)
            * corr
            for time, corr in zip(times, correlations)
        ]
        integral = sum(
            0.5 * (values[index] + values[index + 1]) * (times[index + 1] - times[index])
            for index in range(len(times) - 1)
        )
        result.append(integral.real / math.pi)
    return result


def truncate_time(
    times: list[float], correlations: list[complex], tmax: float
) -> tuple[list[float], list[complex]]:
    selected = [index for index, time in enumerate(times) if time <= tmax + 1e-12]
    if not selected or not math.isclose(times[selected[-1]], tmax, rel_tol=0.0, abs_tol=1e-10):
        raise ValueError(f"时间网格不含 tmax={tmax:g}")
    stop = selected[-1] + 1
    return times[:stop], correlations[:stop]


def trapezoid(grid: list[float], values: list[float]) -> float:
    return sum(
        0.5 * (values[index] + values[index + 1]) * (grid[index + 1] - grid[index])
        for index in range(len(grid) - 1)
    )


def relative_l2(reference: list[float], candidate: list[float]) -> float:
    numerator = math.sqrt(sum((left - right) ** 2 for left, right in zip(reference, candidate)))
    denominator = math.sqrt(sum(value * value for value in reference))
    return numerator / max(denominator, 1e-30)


def peak(grid: list[float], values: list[float]) -> float:
    return grid[max(range(len(values)), key=values.__getitem__)]


def same_grid(left: list[float], right: list[float]) -> bool:
    return len(left) == len(right) and all(
        math.isclose(a, b, rel_tol=0.0, abs_tol=1e-12) for a, b in zip(left, right)
    )


def interpolate(
    grid: list[float], values: list[float], points: list[float]
) -> list[float]:
    if len(grid) != len(values) or len(grid) < 2:
        raise ValueError("插值网格与数据长度不一致")
    result: list[float] = []
    for point in points:
        if point < grid[0] - 1e-12 or point > grid[-1] + 1e-12:
            raise ValueError(f"插值点 {point:g} 超出频率网格")
        if math.isclose(point, grid[-1], rel_tol=0.0, abs_tol=1e-12):
            result.append(values[-1])
            continue
        right = bisect.bisect_right(grid, point)
        left = max(0, right - 1)
        right = min(right, len(grid) - 1)
        fraction = (point - grid[left]) / max(grid[right] - grid[left], 1e-30)
        result.append(values[left] * (1.0 - fraction) + values[right] * fraction)
    return result


def clip_to_window(
    grid: list[float], values: list[float], lower: float, upper: float
) -> tuple[list[float], list[float]]:
    if not grid[0] <= lower < upper <= grid[-1]:
        raise ValueError("积分窗超出数据范围")
    clipped_grid = [lower]
    clipped_grid.extend(point for point in grid if lower < point < upper)
    clipped_grid.append(upper)
    return clipped_grid, interpolate(grid, values, clipped_grid)


def comparison_tag(
    covered: bool,
    peak_delta: float | None,
    weight_delta: float | None,
    peak_budget: float,
    weight_budget: float,
) -> tuple[str, dict[str, bool]]:
    checks = {
        "peak_delta_le_budget": peak_delta is not None and peak_delta <= peak_budget,
        "integrated_weight_delta_le_budget": (
            weight_delta is not None and weight_delta <= weight_budget
        ),
    }
    if not covered:
        return "NotEvaluable", checks
    return ("Agreement" if all(checks.values()) else "Disagreement"), checks


def maxdim_cap_exercised(actual: float, configured: int) -> bool:
    return configured > 0 and actual >= 0.95 * configured


def write_spectrum_comparison(
    path: Path,
    omega: list[float],
    coarse: list[float],
    refined: list[float],
    short: list[float],
    short_tmax: float,
    maxdim_values: list[float] | None = None,
    maxdim_configured: int | None = None,
) -> None:
    columns = ["omega", "coarse", "refined", f"refined_tmax_{short_tmax:g}"]
    series = [omega, coarse, refined, short]
    if maxdim_values is not None and maxdim_configured is not None:
        columns.append(f"maxdim_{maxdim_configured}")
        series.append(maxdim_values)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        writer.writerows(zip(*series))


def check_manifest(run: Path) -> tuple[dict[str, object], list[str]]:
    failures: list[str] = []
    manifest = read_json(run / "manifest.json")
    status = read_json(run / "status.json")
    if manifest.get("status") != "success" or manifest.get("accepted") is not True:
        failures.append(f"{run.name} manifest 未通过")
    if status.get("status") != "success" or status.get("accepted") is not True:
        failures.append(f"{run.name} status 未通过")
    acceptance = manifest.get("acceptance", {})
    if not isinstance(acceptance, dict) or not acceptance or not all(acceptance.values()):
        failures.append(f"{run.name} 单 run 验收项不完整")
    checksum_ok, checksum_failures = verify_checksums(run)
    if not checksum_ok:
        failures.extend(f"{run.name}: {item}" for item in checksum_failures)
    return manifest, failures


def locked_instance(manifest: dict[str, object]) -> tuple[float, float, int, float]:
    params = manifest["params"]
    settings = manifest["settings"]
    alpha = float(params["alpha"])
    beta = float(params["beta"])
    length = int(params["L"])
    eta = float(settings["window_eta"])
    if not 0.0 <= alpha <= 1.0 or not 0.0 <= beta <= 1.0:
        raise ValueError("参数超出正区")
    required = {
        "boundary": "OBC",
        "sector": "Sz=0",
        "momentum_source": "O_q|GS>",
        "momentum_normalization": "1/sqrt(L)",
        "fourier_normalization": "one_sided_trapezoid/pi",
        "time_window": "exponential",
    }
    if any(settings.get(key) != value for key, value in required.items()):
        raise ValueError("边界、扇区、动量源或 Fourier 定义不匹配")
    if settings.get("t0_included") is not True or int(settings.get("trotter_order", 0)) != 2:
        raise ValueError("t=0 或二阶 Trotter 定义不匹配")
    if not math.isclose(float(params["q_over_pi"]), 1.0, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("结果不是严格 q=pi")
    return alpha, beta, length, eta


def read_cv_points(path: Path) -> tuple[dict[str, object], list[tuple[float, float]]]:
    manifest = read_json(path / "manifest.json")
    with (path / "spectrum.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    points = [(float(row["omega"]), float(row["intensity"])) for row in rows]
    omegas = [point[0] for point in points]
    acceptance = manifest.get("acceptance", {})
    accepted = manifest.get("accepted") is True or (
        isinstance(acceptance, dict) and acceptance.get("status") == "pass"
    )
    checksum_ok, _ = verify_checksums(path)
    if manifest.get("status") != "success" or not accepted or not checksum_ok:
        raise ValueError("CV 锚点集未通过 manifest 或 checksum")
    if (
        not points
        or omegas != sorted(omegas)
        or len(set(omegas)) != len(omegas)
        or not all(math.isfinite(value) for point in points for value in point)
    ):
        raise ValueError("CV 频点无效")
    return manifest, points


def write_checksums(output: Path) -> None:
    files = sorted(path for path in output.iterdir() if path.is_file() and path.name != "checksums.sha256")
    (output / "checksums.sha256").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in files), encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coarse-dir", required=True)
    parser.add_argument("--refined-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--cv-dir")
    parser.add_argument("--maxdim-dir")
    parser.add_argument("--short-tmax", type=float, default=25.0)
    parser.add_argument("--peak-budget", type=float, default=0.05)
    parser.add_argument("--weight-budget", type=float, default=0.05)
    parser.add_argument("--cv-peak-budget", type=float, default=0.1)
    parser.add_argument("--cv-weight-budget", type=float, default=0.15)
    parser.add_argument("--cv-weight-window-min", type=float, default=0.0)
    parser.add_argument("--cv-weight-window-max", type=float, default=1.5)
    args = parser.parse_args()

    coarse_dir = Path(args.coarse_dir).resolve()
    refined_dir = Path(args.refined_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise SystemExit(f"拒绝覆盖已有分析: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    try:
        coarse_manifest, coarse_failures = check_manifest(coarse_dir)
        refined_manifest, refined_failures = check_manifest(refined_dir)
        failures.extend(coarse_failures + refined_failures)
        coarse_instance = locked_instance(coarse_manifest)
        refined_instance = locked_instance(refined_manifest)
        if coarse_instance != refined_instance:
            failures.append("coarse/refined 物理实例不一致")
        coarse_settings = coarse_manifest["settings"]
        refined_settings = refined_manifest["settings"]
        coarse_dt = float(coarse_settings["tstep"])
        refined_dt = float(refined_settings["tstep"])
        full_tmax = float(refined_settings["tmax"])
        if not math.isclose(coarse_dt, 2.0 * refined_dt, rel_tol=0.0, abs_tol=1e-12):
            failures.append("两档时间步不是 dt/dt2")
        if not math.isclose(
            float(coarse_settings["tmax"]), full_tmax, rel_tol=0.0, abs_tol=1e-12
        ):
            failures.append("两档时间步的 tmax 不一致")

        coarse_omega, coarse_values = read_spectrum(coarse_dir / "spectrum.csv")
        refined_omega, refined_values = read_spectrum(refined_dir / "spectrum.csv")
        if not same_grid(coarse_omega, refined_omega):
            failures.append("coarse/refined 频率网格不一致")
        coarse_times, coarse_corr = read_correlation(coarse_dir / "correlation.csv")
        refined_times, refined_corr = read_correlation(refined_dir / "correlation.csv")
        eta = refined_instance[3]
        coarse_recomputed = fourier_spectrum(coarse_times, coarse_corr, coarse_omega, eta)
        refined_recomputed = fourier_spectrum(refined_times, refined_corr, refined_omega, eta)
        coarse_fourier_error = relative_l2(coarse_values, coarse_recomputed)
        refined_fourier_error = relative_l2(refined_values, refined_recomputed)
        if coarse_fourier_error > 1e-10 or refined_fourier_error > 1e-10:
            failures.append("存储频谱无法由原始相关函数复算")

        short_times, short_corr = truncate_time(refined_times, refined_corr, args.short_tmax)
        short_values = fourier_spectrum(short_times, short_corr, refined_omega, eta)
        coarse_peak = peak(coarse_omega, coarse_values)
        refined_peak = peak(refined_omega, refined_values)
        short_peak = peak(refined_omega, short_values)
        coarse_weight = trapezoid(coarse_omega, coarse_values)
        refined_weight = trapezoid(refined_omega, refined_values)
        dt_peak_delta = abs(refined_peak - coarse_peak)
        dt_weight_delta = abs(refined_weight - coarse_weight) / max(abs(refined_weight), 1e-30)
        window_peak_delta = abs(refined_peak - short_peak)
        nonnegative_tolerance = -1e-10 * max(max(coarse_values + refined_values + short_values), 1.0)
        gates = {
            "dt_peak_convergence": dt_peak_delta <= args.peak_budget,
            "dt_weight_convergence": dt_weight_delta <= args.weight_budget,
            "time_window_peak_convergence": window_peak_delta <= args.peak_budget,
            "coarse_nonnegative": min(coarse_values) >= nonnegative_tolerance,
            "refined_nonnegative": min(refined_values) >= nonnegative_tolerance,
            "short_window_nonnegative": min(short_values) >= nonnegative_tolerance,
            "coarse_fourier_reproducible": coarse_fourier_error <= 1e-10,
            "refined_fourier_reproducible": refined_fourier_error <= 1e-10,
        }
        if failures:
            gates["terminal_integrity"] = False
        else:
            gates["terminal_integrity"] = True

        maxdim_supplied = args.maxdim_dir is not None
        maxdim_comparable = False
        maxdim_values: list[float] | None = None
        maxdim_configured: int | None = None
        maxdim_peak_delta: float | None = None
        maxdim_weight_delta: float | None = None
        maxdim_diagnostics: dict[str, object] = {"explicit_second_maxdim_supplied": maxdim_supplied}
        if maxdim_supplied:
            maxdim_dir = Path(args.maxdim_dir).resolve()
            maxdim_manifest, maxdim_failures = check_manifest(maxdim_dir)
            failures.extend(maxdim_failures)
            maxdim_instance = locked_instance(maxdim_manifest)
            maxdim_omega, maxdim_values = read_spectrum(maxdim_dir / "spectrum.csv")
            same_maxdim_instance = maxdim_instance == refined_instance
            same_maxdim_grid = same_grid(maxdim_omega, refined_omega)
            configured_maxdim = int(maxdim_manifest["settings"]["tebd_maxdim"])
            maxdim_configured = configured_maxdim
            reference_maxdim = int(refined_manifest["settings"]["tebd_maxdim"])
            maxdim_settings = maxdim_manifest["settings"]
            comparable_settings = all(
                maxdim_settings.get(key) == refined_settings.get(key)
                for key in (
                    "tstep",
                    "tmax",
                    "time_window",
                    "window_eta",
                    "fourier_normalization",
                    "omega_min",
                    "omega_max",
                    "omega_step",
                    "tebd_cutoff",
                    "trotter_order",
                )
            )
            actual_maxdim = float(
                maxdim_manifest.get("diagnostics", {}).get("tebd_actual_maxdim", 0.0)
            )
            cap_exercised = maxdim_cap_exercised(actual_maxdim, configured_maxdim)
            maxdim_comparable = (
                same_maxdim_instance
                and same_maxdim_grid
                and configured_maxdim != reference_maxdim
                and comparable_settings
                and cap_exercised
                and not maxdim_failures
            )
            if not maxdim_comparable:
                failures.append("第二档 maxdim 与 refined 不构成可比较的独立档位")
            maxdim_peak_delta = abs(peak(maxdim_omega, maxdim_values) - refined_peak)
            maxdim_weight_delta = abs(
                trapezoid(maxdim_omega, maxdim_values) - refined_weight
            ) / max(abs(refined_weight), 1e-30)
            maxdim_diagnostics.update(
                {
                    "same_instance": same_maxdim_instance,
                    "same_grid": same_maxdim_grid,
                    "same_evolution_settings": comparable_settings,
                    "configured_maxdim": configured_maxdim,
                    "reference_maxdim": reference_maxdim,
                    "actual_maxdim": actual_maxdim,
                    "cap_exercised": cap_exercised,
                    "spectrum_relative_l2": relative_l2(refined_values, maxdim_values),
                    "peak_delta": maxdim_peak_delta,
                    "weight_relative_delta": maxdim_weight_delta,
                }
            )
            gates["maxdim_peak_convergence"] = (
                maxdim_comparable and maxdim_peak_delta <= args.peak_budget
            )
            gates["maxdim_weight_convergence"] = (
                maxdim_comparable and maxdim_weight_delta <= args.weight_budget
            )

        cv_supplied = args.cv_dir is not None
        cv_diagnostics: dict[str, object] = {"cv_supplied": cv_supplied}
        cv_peak_covered = False
        cv_weight_covered = False
        cv_peak_delta: float | None = None
        cv_weight_delta: float | None = None
        cross_method_tag = "NotEvaluable"
        cross_method_gates = {
            "peak_delta_le_budget": False,
            "integrated_weight_delta_le_budget": False,
        }
        if cv_supplied:
            cv_dir = Path(args.cv_dir).resolve()
            cv_manifest, cv_points = read_cv_points(cv_dir)
            cv_params = cv_manifest["params"]
            cv_settings = cv_manifest["settings"]
            same_cv_instance = (
                math.isclose(float(cv_params["alpha"]), refined_instance[0], abs_tol=1e-12)
                and math.isclose(float(cv_params["beta"]), refined_instance[1], abs_tol=1e-12)
                and int(cv_params["L"]) == refined_instance[2]
                and math.isclose(float(cv_params["q_over_pi"]), 1.0, abs_tol=1e-12)
                and math.isclose(float(cv_settings["eta"]), eta, abs_tol=1e-12)
                and cv_settings.get("boundary") == "OBC"
                and cv_settings.get("sector") == "Sz=0"
                and cv_settings.get("momentum_normalization") == "1/sqrt(L)"
            )
            if not same_cv_instance:
                failures.append("CV 与 TEBD 物理实例不一致")
            cv_omegas = [point[0] for point in cv_points]
            cv_values = [point[1] for point in cv_points]
            tebd_at_cv = interpolate(refined_omega, refined_values, cv_omegas)
            cv_peak_index = max(range(len(cv_values)), key=cv_values.__getitem__)
            cv_peak_covered = (
                cv_peak_index not in (0, len(cv_values) - 1)
                and cv_omegas[0] < refined_peak < cv_omegas[-1]
            )
            cv_intensity_at_refined_peak = interpolate(
                cv_omegas, cv_values, [refined_peak]
            )[0] if cv_omegas[0] <= refined_peak <= cv_omegas[-1] else None
            cv_peak_delta = abs(
                cv_omegas[cv_peak_index] - refined_peak
            ) if cv_peak_covered else None
            weight_lower = args.cv_weight_window_min
            weight_upper = args.cv_weight_window_max
            cv_weight_covered = (
                cv_omegas[0] <= weight_lower + 1e-12
                and cv_omegas[-1] >= weight_upper - 1e-12
            )
            if cv_weight_covered:
                shared_omega, cv_shared = clip_to_window(
                    cv_omegas, cv_values, weight_lower, weight_upper
                )
                tebd_shared_on_cv = interpolate(refined_omega, refined_values, shared_omega)
                cv_weight = trapezoid(shared_omega, cv_shared)
                tebd_weight = trapezoid(shared_omega, tebd_shared_on_cv)
                cv_weight_delta = abs(tebd_weight - cv_weight) / max(abs(cv_weight), 1e-30)
            cross_method_tag, cross_method_gates = comparison_tag(
                same_cv_instance and cv_peak_covered and cv_weight_covered,
                cv_peak_delta,
                cv_weight_delta,
                args.cv_peak_budget,
                args.cv_weight_budget,
            )
            cv_diagnostics.update(
                {
                    "same_instance": same_cv_instance,
                    "omegas": cv_omegas,
                    "cv_intensities": cv_values,
                    "tebd_intensities_nearest_grid": tebd_at_cv,
                    "point_relative_differences": [
                        abs(tebd - cv) / max(abs(cv), 1e-30)
                        for cv, tebd in zip(cv_values, tebd_at_cv)
                    ],
                    "main_peak_bracketed": cv_peak_covered,
                    "full_weight_window_covered": cv_weight_covered,
                    "peak_delta": cv_peak_delta,
                    "integrated_weight_relative_delta": cv_weight_delta,
                    "cv_intensity_at_refined_peak": cv_intensity_at_refined_peak,
                    "weight_window": [weight_lower, weight_upper],
                }
            )

        coverage = {
            "dt_dt2": True,
            "two_tmax": args.short_tmax < full_tmax,
            "two_maxdim": maxdim_comparable,
            "cv_main_peak": cv_peak_covered,
            "cv_major_weight": cv_weight_covered,
            "q0_conservation": False,
            "momentum_inversion": False,
        }
        tebd_qpi_pass = all(gates.values())
        qpi_coverage = all(coverage[key] for key in ("dt_dt2", "two_tmax", "two_maxdim"))
        full_dynamic_coverage = all(coverage.values())
        if failures or not tebd_qpi_pass:
            qpi_status = "fail"
        elif qpi_coverage:
            qpi_status = "pass"
        else:
            qpi_status = "incomplete"
        if qpi_status == "fail" or cross_method_tag == "Disagreement":
            full_dynamic_status = "fail"
        elif qpi_status == "pass" and full_dynamic_coverage and cross_method_tag == "Agreement":
            full_dynamic_status = "pass"
        else:
            full_dynamic_status = "incomplete"
        result = {
            "schema_version": 1,
            "status": qpi_status,
            "qpi_production_status": qpi_status,
            "full_dynamic_status": full_dynamic_status,
            "tebd_qpi_tag": "Agreement" if tebd_qpi_pass else "Disagreement",
            "cross_method_tag": cross_method_tag,
            "params": {
                "alpha": refined_instance[0],
                "beta": refined_instance[1],
                "L": refined_instance[2],
                "q_over_pi": 1.0,
                "eta": eta,
                "boundary": "OBC",
                "sector": "Sz=0",
            },
            "instance": (
                f"alpha={refined_instance[0]:g},beta={refined_instance[1]:g},"
                f"L={refined_instance[2]},q/pi=1,eta={eta:g},OBC,Sz=0"
            ),
            "budgets": {
                "dt_peak_omega": args.peak_budget,
                "dt_integrated_weight_relative": args.weight_budget,
                "tmax_peak_omega": args.peak_budget,
                "maxdim_peak_omega": args.peak_budget,
                "maxdim_integrated_weight_relative": args.weight_budget,
                "cv_peak_omega": args.cv_peak_budget,
                "cv_integrated_weight_relative": args.cv_weight_budget,
                "cv_weight_window": [args.cv_weight_window_min, args.cv_weight_window_max],
            },
            "gates": gates,
            "cross_method_gates": cross_method_gates,
            "coverage": coverage,
            "diagnostics": {
                "coarse_peak_omega": coarse_peak,
                "refined_peak_omega": refined_peak,
                "short_tmax": args.short_tmax,
                "short_window_peak_omega": short_peak,
                "full_tmax": full_tmax,
                "dt_peak_delta": dt_peak_delta,
                "dt_weight_relative_delta": dt_weight_delta,
                "time_window_peak_delta": window_peak_delta,
                "coarse_spectrum_relative_l2_vs_refined": relative_l2(
                    refined_values, coarse_values
                ),
                "short_spectrum_relative_l2_vs_full": relative_l2(
                    refined_values, short_values
                ),
                "coarse_fourier_recompute_relative_l2": coarse_fourier_error,
                "refined_fourier_recompute_relative_l2": refined_fourier_error,
                "coarse_spectrum_min": min(coarse_values),
                "refined_spectrum_min": min(refined_values),
                "short_spectrum_min": min(short_values),
                "maxdim": maxdim_diagnostics,
                "cv": cv_diagnostics,
            },
            "failures": failures,
            "limitations": [
                "严格 q=pi 自相关不包含 q=0 守恒和动量反演检查",
                "第二档 maxdim 未实际触及上限时不计为独立收敛证据",
                "CV 未包围主峰并覆盖主要积分窗时不关闭方法交叉门",
            ],
            "evidence": {
                "coarse_manifest_sha256": sha256(coarse_dir / "manifest.json"),
                "refined_manifest_sha256": sha256(refined_dir / "manifest.json"),
                "negative_alpha_excluded": True,
                "figure_9_excluded": True,
            },
        }
        (output_dir / "summary.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        write_spectrum_comparison(
            output_dir / "spectrum_comparison.csv",
            refined_omega,
            coarse_values,
            refined_values,
            short_values,
            args.short_tmax,
            maxdim_values,
            maxdim_configured,
        )
        with (output_dir / "cross-method-check.csv").open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.writer(handle)
            writer.writerow(["method", "observable", "value", "uncertainty", "instance", "tag"])
            writer.writerow(
                ["tebd_dt", "peak_omega", coarse_peak, args.peak_budget, result["instance"], result["tebd_qpi_tag"]]
            )
            writer.writerow(
                ["tebd_dt2", "peak_omega", refined_peak, args.peak_budget, result["instance"], result["tebd_qpi_tag"]]
            )
            if cv_supplied:
                writer.writerow(
                    [
                        "correction_vector_dmrg",
                        "peak_omega",
                        cv_omegas[max(range(len(cv_values)), key=cv_values.__getitem__)],
                        args.cv_peak_budget,
                        result["instance"],
                        cross_method_tag,
                    ]
                )
                writer.writerow(
                    [
                        "finite_dmrg_tebd_qpi",
                        "peak_omega",
                        refined_peak,
                        args.cv_peak_budget,
                        result["instance"],
                        cross_method_tag,
                    ]
                )
        write_checksums(output_dir)
        print(json.dumps(result, ensure_ascii=False))
        if qpi_status == "incomplete":
            raise SystemExit(2)
        if qpi_status != "pass":
            raise SystemExit(1)
    except (FileNotFoundError, KeyError, TypeError, ValueError) as error:
        failure = {"schema_version": 1, "status": "fail", "failures": failures + [str(error)]}
        (output_dir / "summary.json").write_text(
            json.dumps(failure, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        write_checksums(output_dir)
        print(json.dumps(failure, ensure_ascii=False))
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
