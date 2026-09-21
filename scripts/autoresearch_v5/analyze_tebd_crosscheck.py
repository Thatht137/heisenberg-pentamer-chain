#!/usr/bin/env python3
"""比较两个正区 TEBD run 的 raw 频谱并执行交叉验收。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_matrix(path: Path) -> list[list[float]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = [[float(item) for item in row] for row in csv.reader(handle) if row]
    if not rows or any(len(row) != len(rows[0]) for row in rows):
        raise SystemExit(f"矩阵形状不规则: {path}")
    if not all(math.isfinite(value) for row in rows for value in row):
        raise SystemExit(f"矩阵含非有限值: {path}")
    return rows


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def peak(matrix: list[list[float]], omega_max: float) -> tuple[int, int, float, float]:
    q_points = len(matrix)
    omega_points = len(matrix[0])
    iq, iw = max(
        ((i, j) for i, row in enumerate(matrix) for j, _ in enumerate(row)),
        key=lambda index: matrix[index[0]][index[1]],
    )
    q = 2.0 * math.pi * iq / max(q_points - 1, 1)
    omega = omega_max * iw / max(omega_points - 1, 1)
    return iq, iw, q, omega


def row_peak(matrix: list[list[float]], row: int, omega_max: float) -> tuple[int, float]:
    iw = max(range(len(matrix[row])), key=lambda index: matrix[row][index])
    omega = omega_max * iw / max(len(matrix[row]) - 1, 1)
    return iw, omega


def low_weight(matrix: list[list[float]], omega_max: float, cutoff: float) -> float:
    omega_step = omega_max / max(len(matrix[0]) - 1, 1)
    last = min(len(matrix[0]) - 1, math.floor(cutoff / omega_step))
    return sum(sum(row[: last + 1]) for row in matrix) * omega_step


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coarse-dir", required=True)
    parser.add_argument("--refined-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--peak-tolerance", type=float, default=0.05)
    parser.add_argument("--weight-tolerance", type=float, default=0.05)
    parser.add_argument("--low-omega-cutoff", type=float, default=1.5)
    args = parser.parse_args()

    coarse = Path(args.coarse_dir).resolve()
    refined = Path(args.refined_dir).resolve()
    output = Path(args.output).resolve()
    coarse_manifest = read_json(coarse / "manifest.json")
    refined_manifest = read_json(refined / "manifest.json")
    for label, manifest in (("coarse", coarse_manifest), ("refined", refined_manifest)):
        params = manifest.get("params", {})
        if not 0.0 <= float(params.get("alpha", -1.0)) <= 1.0:
            raise SystemExit(f"{label} run 含负或越界 alpha")
        if not 0.0 <= float(params.get("beta", -1.0)) <= 1.0:
            raise SystemExit(f"{label} run 含负或越界 beta")
        if manifest.get("status") != "success" or manifest.get("accepted") is not True:
            raise SystemExit(f"{label} run 未通过单 run 验收")

    coarse_settings = coarse_manifest["settings"]
    refined_settings = refined_manifest["settings"]
    if coarse_manifest["params"] != refined_manifest["params"]:
        raise SystemExit("两个 run 的物理参数不一致")
    if coarse_settings["q_points"] != refined_settings["q_points"] or coarse_settings["omega_points"] != refined_settings["omega_points"]:
        raise SystemExit("两个 run 的频率/动量网格不一致")
    if coarse_settings.get("time_window") != refined_settings.get("time_window"):
        raise SystemExit("两个 run 的时间窗类型不一致")
    if not math.isclose(
        float(coarse_settings.get("window_eta", -1.0)),
        float(refined_settings.get("window_eta", -2.0)),
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise SystemExit("两个 run 的时间窗 eta 不一致")
    coarse_diag = coarse_manifest["diagnostics"]
    refined_diag = refined_manifest["diagnostics"]
    if not math.isclose(float(coarse_diag["tmax"]), float(refined_diag["tmax"]), rel_tol=0.0, abs_tol=1e-10):
        raise SystemExit("dt/dt2 检查要求相同 tmax")
    if float(refined_diag["tstep"]) > float(coarse_diag["tstep"]) / 2.0 + 1e-12:
        raise SystemExit("refined run 不是 dt/2")

    coarse_matrix = read_matrix(coarse / "spectrum_raw.csv")
    refined_matrix = read_matrix(refined / "spectrum_raw.csv")
    if (len(coarse_matrix), len(coarse_matrix[0])) != (len(refined_matrix), len(refined_matrix[0])):
        raise SystemExit("raw 频谱矩阵形状不一致")
    omega_max = float(coarse_settings["omega_max"])
    diff_sq = sum(
        (a - b) ** 2
        for row_a, row_b in zip(coarse_matrix, refined_matrix)
        for a, b in zip(row_a, row_b)
    )
    ref_sq = sum(value * value for row in coarse_matrix for value in row)
    rms_relative = math.sqrt(diff_sq) / max(math.sqrt(ref_sq), 1e-30)
    coarse_peak = peak(coarse_matrix, omega_max)
    refined_peak = peak(refined_matrix, omega_max)
    qpi_row = min(range(len(coarse_matrix)), key=lambda row: abs(2.0 * math.pi * row / max(len(coarse_matrix) - 1, 1) - math.pi))
    _, coarse_qpi_omega = row_peak(coarse_matrix, qpi_row, omega_max)
    _, refined_qpi_omega = row_peak(refined_matrix, qpi_row, omega_max)
    coarse_weight = low_weight(coarse_matrix, omega_max, args.low_omega_cutoff)
    refined_weight = low_weight(refined_matrix, omega_max, args.low_omega_cutoff)
    weight_delta = abs(refined_weight - coarse_weight) / max(abs(coarse_weight), 1e-30)
    peak_delta = abs(refined_peak[3] - coarse_peak[3])
    qpi_peak_delta = abs(refined_qpi_omega - coarse_qpi_omega)
    checks = {
        "dt_half": True,
        "global_peak_delta_le_tolerance": peak_delta <= args.peak_tolerance,
        "qpi_peak_delta_le_tolerance": qpi_peak_delta <= args.peak_tolerance,
        "low_weight_delta_le_tolerance": weight_delta <= args.weight_tolerance,
    }
    result = {
        "schema_version": 1,
        "status": "pass" if all(checks.values()) else "fail",
        "coarse_dir": str(coarse),
        "refined_dir": str(refined),
        "parameters": coarse_manifest["params"],
        "settings": {
            "q_points": coarse_settings["q_points"],
            "omega_points": coarse_settings["omega_points"],
            "omega_max": omega_max,
            "time_window": coarse_settings["time_window"],
            "window_eta": coarse_settings["window_eta"],
            "low_omega_cutoff": args.low_omega_cutoff,
        },
        "diagnostics": {
            "coarse_tstep": coarse_diag["tstep"],
            "refined_tstep": refined_diag["tstep"],
            "tmax": coarse_diag["tmax"],
            "global_peak_omega_coarse": coarse_peak[3],
            "global_peak_omega_refined": refined_peak[3],
            "global_peak_delta": peak_delta,
            "qpi_peak_omega_coarse": coarse_qpi_omega,
            "qpi_peak_omega_refined": refined_qpi_omega,
            "qpi_peak_delta": qpi_peak_delta,
            "low_weight_coarse": coarse_weight,
            "low_weight_refined": refined_weight,
            "low_weight_relative_delta": weight_delta,
            "normalized_rms": rms_relative,
        },
        "acceptance": checks,
        "evidence": {
            "coarse_manifest_sha256": sha256(coarse / "manifest.json"),
            "refined_manifest_sha256": sha256(refined / "manifest.json"),
            "coarse_raw_sha256": sha256(coarse / "spectrum_raw.csv"),
            "refined_raw_sha256": sha256(refined / "spectrum_raw.csv"),
            "negative_alpha_excluded": True,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
