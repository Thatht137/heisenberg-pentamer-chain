#!/usr/bin/env python3
"""在相同正区参数点独立验收 CV 与 TEBD 动态谱。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from pathlib import Path


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_cv(path: Path) -> list[dict[str, float]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = []
        for row in csv.DictReader(handle):
            # 忽略 source_run 等 provenance 字段，只读取数值列。
            rows.append({key: float(row[key]) for key in ("q_over_pi", "omega", "intensity", "relative_residual")})
    if len(rows) < 1:
        raise SystemExit("CV 缺少频率点")
    omegas = [row["omega"] for row in rows]
    values = [row["intensity"] for row in rows]
    if omegas != sorted(omegas) or len(set(omegas)) != len(omegas):
        raise SystemExit("CV omega 网格未严格递增")
    if not all(math.isfinite(value) for row in rows for value in row.values()):
        raise SystemExit("CV 数据含非有限值")
    if min(values) < -1e-10 * max(max(values), 1.0):
        raise SystemExit("CV 谱未通过非负性")
    return rows


def read_matrix(path: Path) -> list[list[float]]:
    with path.open(encoding="utf-8", newline="") as handle:
        matrix = [[float(value) for value in row] for row in csv.reader(handle) if row]
    if not matrix or any(len(row) != len(matrix[0]) for row in matrix):
        raise SystemExit("TEBD raw 谱矩阵形状不规则")
    if not all(math.isfinite(value) for row in matrix for value in row):
        raise SystemExit("TEBD raw 谱含非有限值")
    return matrix


def read_qpi_spectrum(path: Path) -> tuple[list[float], list[float]]:
    """读取历史 q=pi 单切片，作为 raw 矩阵缺失时的兼容路径。"""
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {"q_over_pi", "omega", "intensity"}
    if not rows or not required.issubset(rows[0]):
        raise SystemExit("TEBD spectrum.csv 缺少 q_over_pi/omega/intensity")
    parsed = [(float(row["q_over_pi"]), float(row["omega"]), float(row["intensity"])) for row in rows]
    if any(abs(q - 1.0) > 1e-12 for q, _, _ in parsed):
        raise SystemExit("历史 TEBD spectrum.csv 不是 q=pi 单切片")
    parsed.sort(key=lambda item: item[1])
    omegas = [item[1] for item in parsed]
    values = [item[2] for item in parsed]
    if len(set(omegas)) != len(omegas) or not all(math.isfinite(x) for x in omegas + values):
        raise SystemExit("历史 TEBD spectrum.csv 网格或数值无效")
    if min(values) < -1e-10:
        raise SystemExit("历史 TEBD spectrum.csv 含负谱")
    return omegas, values


def interpolate(grid: list[float], values: list[float], point: float) -> float:
    if point < grid[0] or point > grid[-1]:
        raise SystemExit(f"CV 频率 {point:g} 超出 TEBD 网格")
    for index in range(len(grid) - 1):
        left, right = grid[index], grid[index + 1]
        if left <= point <= right:
            fraction = (point - left) / max(right - left, 1e-30)
            return values[index] * (1.0 - fraction) + values[index + 1] * fraction
    return values[-1]


def trapezoid(omegas: list[float], values: list[float]) -> float:
    return sum(
        0.5 * (values[index] + values[index + 1]) * (omegas[index + 1] - omegas[index])
        for index in range(len(omegas) - 1)
    )


def tebd_total_sz(run_dir: Path) -> float:
    # 兼容生产驱动器的两种 stdout 命名。
    log_text = None
    for name in ("tebd.stdout.log", "julia.stdout.log", "stdout.log"):
        path = run_dir / name
        if path.is_file():
            log_text = path.read_text(encoding="utf-8", errors="replace")
            break
    if log_text is not None:
        match = re.search(r"Total Sz\s*=\s*([-+0-9.eE]+)", log_text)
        if match is not None:
            return float(match.group(1))
    manifest = run_dir / "manifest.json"
    if manifest.is_file():
        diagnostics = read_json(manifest).get("diagnostics", {})
        if isinstance(diagnostics, dict) and "total_sz" in diagnostics:
            return float(diagnostics["total_sz"])
    raise SystemExit("TEBD 日志和 manifest 都缺少 Total Sz")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cv-dir", required=True)
    parser.add_argument("--tebd-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--peak-budget", type=float, default=0.1)
    parser.add_argument("--weight-budget", type=float, default=0.15)
    parser.add_argument("--weight-window-min", type=float, default=0.0)
    parser.add_argument("--weight-window-max", type=float, default=1.5)
    args = parser.parse_args()

    cv_dir = Path(args.cv_dir).resolve()
    tebd_dir = Path(args.tebd_dir).resolve()
    output = Path(args.output).resolve()
    cv_manifest = read_json(cv_dir / "manifest.json")
    tebd_manifest = read_json(tebd_dir / "manifest.json")
    cv_params = cv_manifest.get("params", {})
    tebd_params = tebd_manifest.get("params", {})
    cv_settings = cv_manifest.get("settings", {})
    tebd_settings = tebd_manifest.get("settings", {})

    if cv_manifest.get("status") != "success" or cv_manifest.get("acceptance", {}).get("status") != "pass":
        raise SystemExit("CV run 未通过单 run 验收")
    if tebd_manifest.get("status") != "success" or tebd_manifest.get("accepted") is not True:
        raise SystemExit("TEBD run 未通过单 run 验收")
    for label, params in (("CV", cv_params), ("TEBD", tebd_params)):
        if not 0.0 <= float(params.get("alpha", -1.0)) <= 1.0:
            raise SystemExit(f"{label} run 含负或越界 alpha")
        if not 0.0 <= float(params.get("beta", -1.0)) <= 1.0:
            raise SystemExit(f"{label} run 含负或越界 beta")
    for key in ("alpha", "beta", "L"):
        if not math.isclose(float(cv_params[key]), float(tebd_params[key]), rel_tol=0.0, abs_tol=1e-12):
            raise SystemExit(f"CV/TEBD 参数 {key} 不一致")
    if cv_settings.get("boundary") != "OBC" or tebd_settings.get("boundary") != "OBC":
        raise SystemExit("CV/TEBD 边界条件不是 OBC")
    if cv_settings.get("sector") != "Sz=0" or abs(tebd_total_sz(tebd_dir)) > 1e-8:
        raise SystemExit("CV/TEBD 自旋扇区不一致")
    if not math.isclose(float(cv_params.get("q_over_pi", -1.0)), 1.0, rel_tol=0.0, abs_tol=1e-12):
        raise SystemExit("CV run 不是 q=pi")
    if cv_settings.get("momentum_normalization") != "1/sqrt(L)":
        raise SystemExit("CV 动量归一化不匹配")
    if tebd_settings.get("time_window") != "exponential":
        raise SystemExit("TEBD 未使用指数时间窗")
    cv_eta = float(cv_settings.get("eta", -1.0))
    tebd_eta = float(tebd_settings.get("window_eta", -2.0))
    if not math.isclose(cv_eta, tebd_eta, rel_tol=0.0, abs_tol=1e-12):
        raise SystemExit("CV eta 与 TEBD 时间窗 eta 不一致")

    cv_rows = read_cv(cv_dir / "spectrum.csv")
    raw_path = tebd_dir / "spectrum_raw.csv"
    if raw_path.is_file():
        matrix = read_matrix(raw_path)
        q_points = int(tebd_settings["q_points"])
        omega_points = int(tebd_settings["omega_points"])
        if (len(matrix), len(matrix[0])) != (q_points, omega_points):
            raise SystemExit("TEBD raw 谱矩阵与 manifest 形状不一致")
        if min(value for row in matrix for value in row) < -1e-10:
            raise SystemExit("TEBD raw 谱未通过非负性")
        omega_grid = [float(tebd_settings["omega_max"]) * index / max(omega_points - 1, 1) for index in range(omega_points)]
        qpi_row = min(range(q_points), key=lambda index: abs(2.0 * math.pi * index / max(q_points - 1, 1) - math.pi))
        tebd_qpi = [value / math.pi for value in matrix[qpi_row]]
        raw_provenance = "full_q_matrix"
    else:
        omega_grid, stored_qpi = read_qpi_spectrum(tebd_dir / "spectrum.csv")
        tebd_qpi = [value for value in stored_qpi]
        raw_path = tebd_dir / "spectrum.csv"
        raw_provenance = "historical_qpi_slice"
    cv_omegas = [row["omega"] for row in cv_rows]
    cv_values = [row["intensity"] for row in cv_rows]
    tebd_shared = [interpolate(omega_grid, tebd_qpi, omega) for omega in cv_omegas]
    point_relative = [
        abs(tebd - cv) / max(abs(cv), 1e-30)
        for cv, tebd in zip(cv_values, tebd_shared)
    ]

    cv_peak_index = max(range(len(cv_values)), key=cv_values.__getitem__)
    tebd_peak_index = max(range(len(tebd_shared)), key=tebd_shared.__getitem__)
    peak_covered = cv_peak_index not in (0, len(cv_values) - 1) and tebd_peak_index not in (0, len(tebd_shared) - 1)
    peak_delta = abs(cv_omegas[cv_peak_index] - cv_omegas[tebd_peak_index]) if peak_covered else None
    weight_covered = cv_omegas[0] <= args.weight_window_min + 1e-12 and cv_omegas[-1] >= args.weight_window_max - 1e-12
    shared_cv_weight = trapezoid(cv_omegas, cv_values)
    shared_tebd_weight = trapezoid(cv_omegas, tebd_shared)
    shared_weight_delta = abs(shared_tebd_weight - shared_cv_weight) / max(abs(shared_cv_weight), 1e-30)

    coverage = {
        "main_peak_bracketed_by_cv_grid": peak_covered,
        "major_weight_window_covered_by_cv_grid": weight_covered,
    }
    comparable = all(coverage.values())
    checks = {
        "peak_delta_le_budget": peak_delta is not None and peak_delta <= args.peak_budget,
        "major_weight_delta_le_budget": weight_covered and shared_weight_delta <= args.weight_budget,
    }
    if not comparable:
        status, tag = "incomplete", "NotEvaluable"
    elif all(checks.values()):
        status, tag = "pass", "Agreement"
    else:
        status, tag = "fail", "Disagreement"

    instance = (
        f"alpha={float(cv_params['alpha']):g},beta={float(cv_params['beta']):g},"
        f"L={int(cv_params['L'])},q/pi=1,eta={cv_eta:g},OBC,Sz=0"
    )
    result = {
        "schema_version": 1,
        "status": status,
        "tag": tag,
        "instance": instance,
        "methods": ["correction_vector_dmrg", "finite_dmrg_tebd_szz"],
        "observable": "Szz(q=pi,omega)",
        "budgets": {
            "peak_omega": args.peak_budget,
            "major_integrated_weight_relative": args.weight_budget,
            "weight_window": [args.weight_window_min, args.weight_window_max],
        },
        "normalization": {
            "cv": "O_q=(1/sqrt(L))*sum_j exp(iqj)Sz_j; intensity=-Im(G)/pi",
            "tebd_stored": "center-source sum_r integral_0^tmax dt exp(i(omega*t-q*r))C(r,t)",
            "tebd_transform": "stored_raw/pi",
            "tebd_scale_factor": 1.0 / math.pi,
            "finite_obc_caveat": "center-source and 37-site spatial window approximate the all-site O_q average",
            "tebd_spectrum_provenance": raw_provenance,
        },
        "coverage": coverage,
        "checks": checks,
        "diagnostics": {
            "cv_omegas": cv_omegas,
            "cv_intensities": cv_values,
            "tebd_shared_intensities_after_divide_pi": tebd_shared,
            "shared_point_relative_differences": point_relative,
            "cv_shared_window_weight": shared_cv_weight,
            "tebd_shared_window_weight": shared_tebd_weight,
            "shared_window_weight_relative_delta": shared_weight_delta,
            "cv_shared_peak_omega": cv_omegas[cv_peak_index],
            "tebd_shared_peak_omega": cv_omegas[tebd_peak_index],
            "peak_delta": peak_delta,
            "tebd_total_sz": tebd_total_sz(tebd_dir),
        },
        "limitations": [
            "共享窗口权重只作诊断，不等同于标准要求的主要积分权重",
            (
                "CV 网格已包围主峰并覆盖主要积分区间；Agreement 仍限定于当前 alpha、beta、L、q 和归一化协议"
                if coverage["main_peak_bracketed_by_cv_grid"] and coverage["major_weight_window_covered_by_cv_grid"]
                else "CV 网格未包围主峰或未覆盖主要积分区间时，不允许关闭最终动态门"
            ),
        ],
        "evidence": {
            "cv_manifest_sha256": sha256(cv_dir / "manifest.json"),
            "cv_spectrum_sha256": sha256(cv_dir / "spectrum.csv"),
            "tebd_manifest_sha256": sha256(tebd_dir / "manifest.json"),
            "tebd_raw_sha256": sha256(raw_path),
            "negative_alpha_excluded": True,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (output.parent / "cross-method-check.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["method", "observable", "value", "uncertainty", "instance", "tag"])
        writer.writerow(["correction_vector_dmrg", "shared_window_weight", shared_cv_weight, args.weight_budget * abs(shared_cv_weight), instance, tag])
        writer.writerow(["finite_dmrg_tebd_szz", "shared_window_weight", shared_tebd_weight, args.weight_budget * abs(shared_cv_weight), instance, tag])
    print(json.dumps(result, ensure_ascii=False))
    if status == "incomplete":
        raise SystemExit(2)
    if status != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
