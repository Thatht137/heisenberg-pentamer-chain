#!/usr/bin/env python3
"""用 ED oracle 和 dt/dt2 验收严格 q=pi TEBD smoke。"""

from __future__ import annotations

import argparse
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


def read_spectrum(path: Path) -> tuple[list[float], list[float]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    omegas = [float(row["omega"]) for row in rows]
    values = [float(row["intensity"]) for row in rows]
    if len(omegas) < 2 or omegas != sorted(omegas) or len(set(omegas)) != len(omegas):
        raise SystemExit(f"频率网格无效: {path}")
    if not all(math.isfinite(value) for value in omegas + values):
        raise SystemExit(f"谱含非有限值: {path}")
    return omegas, values


def trapezoid(grid: list[float], values: list[float]) -> float:
    return sum(
        0.5 * (values[index] + values[index + 1]) * (grid[index + 1] - grid[index])
        for index in range(len(grid) - 1)
    )


def relative_l2(left: list[float], right: list[float]) -> float:
    numerator = math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right)))
    denominator = math.sqrt(sum(a * a for a in left))
    return numerator / max(denominator, 1e-30)


def peak(grid: list[float], values: list[float]) -> float:
    return grid[max(range(len(values)), key=values.__getitem__)]


def verify_checksums(run: Path) -> bool:
    checksum_path = run / "checksums.sha256"
    if not checksum_path.is_file():
        return False
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split(maxsplit=1)
        if sha256(run / relative.strip()) != expected:
            return False
    return True


def same_instance(manifest: dict[str, object], expected: dict[str, float]) -> bool:
    params = manifest.get("params", {})
    settings = manifest.get("settings", {})
    return (
        all(
            math.isclose(float(params[key]), value, rel_tol=0.0, abs_tol=1e-12)
            for key, value in expected.items()
        )
        and settings.get("boundary") == "OBC"
        and settings.get("sector") == "Sz=0"
        and settings.get("momentum_source") == "O_q|GS>"
        and settings.get("momentum_normalization") == "1/sqrt(L)"
        and settings.get("fourier_normalization") == "one_sided_trapezoid/pi"
        and settings.get("t0_included") is True
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-dir", required=True)
    parser.add_argument("--coarse-dir", required=True)
    parser.add_argument("--refined-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--peak-budget", type=float, default=0.1)
    parser.add_argument("--weight-budget", type=float, default=0.15)
    parser.add_argument("--dt-peak-budget", type=float, default=0.05)
    parser.add_argument("--dt-weight-budget", type=float, default=0.05)
    args = parser.parse_args()

    exact_dir = Path(args.exact_dir).resolve()
    coarse_dir = Path(args.coarse_dir).resolve()
    refined_dir = Path(args.refined_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise SystemExit(f"拒绝覆盖已有分析: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    exact_summary = read_json(exact_dir / "exact_summary.json")
    coarse_manifest = read_json(coarse_dir / "manifest.json")
    refined_manifest = read_json(refined_dir / "manifest.json")
    expected = {
        "alpha": float(exact_summary["alpha"]),
        "beta": float(exact_summary["beta"]),
        "L": float(exact_summary["L"]),
        "q_over_pi": 1.0,
    }
    if not same_instance(coarse_manifest, expected) or not same_instance(refined_manifest, expected):
        raise SystemExit("ED 与 TEBD 的参数、边界、扇区或归一化不一致")
    coarse_dt = float(coarse_manifest["settings"]["tstep"])
    refined_dt = float(refined_manifest["settings"]["tstep"])
    if not math.isclose(coarse_dt, 2 * refined_dt, rel_tol=0.0, abs_tol=1e-12):
        raise SystemExit("两个 TEBD run 不是 dt/dt2")
    if not math.isclose(
        float(coarse_manifest["settings"]["tmax"]),
        float(refined_manifest["settings"]["tmax"]),
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise SystemExit("两个 TEBD run 的 tmax 不一致")

    exact_omega, exact_values = read_spectrum(exact_dir / "exact_spectrum.csv")
    coarse_omega, coarse_values = read_spectrum(coarse_dir / "spectrum.csv")
    refined_omega, refined_values = read_spectrum(refined_dir / "spectrum.csv")
    grids_match = (
        len(exact_omega) == len(coarse_omega) == len(refined_omega)
        and all(
            math.isclose(exact, coarse, rel_tol=0.0, abs_tol=1e-12)
            and math.isclose(exact, refined, rel_tol=0.0, abs_tol=1e-12)
            for exact, coarse, refined in zip(exact_omega, coarse_omega, refined_omega)
        )
    )
    if not grids_match:
        raise SystemExit("ED 与 TEBD 频率网格不一致")

    exact_peak = peak(exact_omega, exact_values)
    coarse_peak = peak(coarse_omega, coarse_values)
    refined_peak = peak(refined_omega, refined_values)
    exact_weight = trapezoid(exact_omega, exact_values)
    coarse_weight = trapezoid(coarse_omega, coarse_values)
    refined_weight = trapezoid(refined_omega, refined_values)
    coarse_weight_error = abs(coarse_weight - exact_weight) / max(abs(exact_weight), 1e-30)
    refined_weight_error = abs(refined_weight - exact_weight) / max(abs(exact_weight), 1e-30)
    dt_weight_delta = abs(refined_weight - coarse_weight) / max(abs(refined_weight), 1e-30)

    exact_source_norm = float(exact_summary["source_norm_squared"])
    coarse_source_norm = float(coarse_manifest["diagnostics"]["source_norm_squared"])
    refined_source_norm = float(refined_manifest["diagnostics"]["source_norm_squared"])
    coarse_source_norm_error = abs(coarse_source_norm - exact_source_norm) / max(
        abs(exact_source_norm), 1e-30
    )
    refined_source_norm_error = abs(refined_source_norm - exact_source_norm) / max(
        abs(exact_source_norm), 1e-30
    )
    coarse_checksums = verify_checksums(coarse_dir)
    refined_checksums = verify_checksums(refined_dir)
    checks = {
        "coarse_checksum": coarse_checksums,
        "refined_checksum": refined_checksums,
        "coarse_source_sum_rule": coarse_source_norm_error <= args.weight_budget,
        "refined_source_sum_rule": refined_source_norm_error <= args.weight_budget,
        "coarse_nonnegative": min(coarse_values) >= -1e-10 * max(max(coarse_values), 1.0),
        "refined_nonnegative": min(refined_values) >= -1e-10 * max(max(refined_values), 1.0),
        "coarse_peak_vs_ed": abs(coarse_peak - exact_peak) <= args.peak_budget,
        "refined_peak_vs_ed": abs(refined_peak - exact_peak) <= args.peak_budget,
        "coarse_weight_vs_ed": coarse_weight_error <= args.weight_budget,
        "refined_weight_vs_ed": refined_weight_error <= args.weight_budget,
        "dt_peak_convergence": abs(refined_peak - coarse_peak) <= args.dt_peak_budget,
        "dt_weight_convergence": dt_weight_delta <= args.dt_weight_budget,
    }
    tag = "Agreement" if all(checks.values()) else "Disagreement"
    status = "pass" if tag == "Agreement" else "fail"
    instance = (
        f"alpha={expected['alpha']:g},beta={expected['beta']:g},L={int(expected['L'])},"
        f"q/pi=1,eta={float(exact_summary['eta']):g},OBC,Sz=0"
    )
    summary = {
        "schema_version": 1,
        "status": status,
        "tag": tag,
        "instance": instance,
        "methods": ["exact_diagonalization", "finite_dmrg_tebd_qpi_autocorrelation"],
        "observable": "Szz(q=pi,omega)",
        "budgets": {
            "ed_peak_omega": 0.0,
            "ed_integrated_weight": 0.0,
            "tebd_peak_omega": args.peak_budget,
            "tebd_integrated_weight_relative": args.weight_budget,
            "dt_peak_omega": args.dt_peak_budget,
            "dt_integrated_weight_relative": args.dt_weight_budget,
        },
        "checks": checks,
        "diagnostics": {
            "exact_peak_omega": exact_peak,
            "coarse_peak_omega": coarse_peak,
            "refined_peak_omega": refined_peak,
            "exact_integrated_weight": exact_weight,
            "coarse_integrated_weight": coarse_weight,
            "refined_integrated_weight": refined_weight,
            "coarse_weight_relative_error": coarse_weight_error,
            "refined_weight_relative_error": refined_weight_error,
            "dt_weight_relative_delta": dt_weight_delta,
            "coarse_spectrum_relative_l2": relative_l2(exact_values, coarse_values),
            "refined_spectrum_relative_l2": relative_l2(exact_values, refined_values),
            "exact_source_norm_squared": exact_source_norm,
            "coarse_source_norm_squared": coarse_source_norm,
            "refined_source_norm_squared": refined_source_norm,
            "coarse_source_norm_relative_error": coarse_source_norm_error,
            "refined_source_norm_relative_error": refined_source_norm_error,
            "coarse_spectrum_min": min(coarse_values),
            "refined_spectrum_min": min(refined_values),
        },
        "normalization": {
            "source": "O_q=(1/sqrt(L))*sum_j exp(i*pi*j)Sz_j",
            "correlation": "C_q(t)=<O_q GS|exp(-iHt)|O_q GS>*exp(iE0t)",
            "fourier": "Re integral_0^tmax exp((i*omega-eta)t)C_q(t)dt/pi",
            "quadrature": "trapezoid including t=0",
        },
        "evidence": {
            "exact_spectrum_sha256": sha256(exact_dir / "exact_spectrum.csv"),
            "coarse_manifest_sha256": sha256(coarse_dir / "manifest.json"),
            "refined_manifest_sha256": sha256(refined_dir / "manifest.json"),
            "negative_alpha_excluded": True,
            "figure_9_excluded": True,
        },
    }
    summary_path = output_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (output_dir / "cross-method-check.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(["method", "observable", "value", "uncertainty", "instance", "tag"])
        writer.writerow(["exact_diagonalization", "peak_omega", exact_peak, 0.0, instance, tag])
        writer.writerow(["tebd_dt", "peak_omega", coarse_peak, args.peak_budget, instance, tag])
        writer.writerow(["tebd_dt2", "peak_omega", refined_peak, args.peak_budget, instance, tag])
        writer.writerow(["exact_diagonalization", "integrated_weight", exact_weight, 0.0, instance, tag])
        writer.writerow(["tebd_dt", "integrated_weight", coarse_weight, args.weight_budget * abs(exact_weight), instance, tag])
        writer.writerow(["tebd_dt2", "integrated_weight", refined_weight, args.weight_budget * abs(exact_weight), instance, tag])
    files = sorted(path for path in output_dir.iterdir() if path.is_file() and path.name != "checksums.sha256")
    (output_dir / "checksums.sha256").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in files), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))
    if status != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
