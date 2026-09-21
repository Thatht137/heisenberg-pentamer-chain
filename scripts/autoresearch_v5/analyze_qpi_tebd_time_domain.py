#!/usr/bin/env python3
"""逐时刻比较 L=10 精确相关函数与严格 q=pi TEBD。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from exact_dsf_oracle import bonds, hamiltonian, sector_basis, source_diagonal


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_correlation(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    times = np.array([float(row["time"]) for row in rows])
    values = np.array(
        [complex(float(row["real_corr"]), float(row["imag_corr"])) for row in rows]
    )
    if len(times) < 2 or not np.all(np.diff(times) > 0):
        raise SystemExit(f"时间网格无效: {path}")
    if not np.all(np.isfinite(values)):
        raise SystemExit(f"相关函数含非有限值: {path}")
    return times, values


def exact_correlation(
    length: int, alpha: float, beta: float, times: np.ndarray
) -> tuple[np.ndarray, float, float]:
    states, state_index = sector_basis(length)
    matrix = hamiltonian(states, state_index, bonds(length // 5, alpha, beta))
    energies, vectors = np.linalg.eigh(matrix)
    diagonal = source_diagonal(states, length, np.pi)
    source = diagonal * vectors[:, 0]
    amplitudes = vectors.conj().T @ source
    weights = np.abs(amplitudes) ** 2
    gaps = energies - energies[0]
    values = np.exp(-1j * np.outer(times, gaps)) @ weights
    return values, float(energies[0]), float(np.sum(weights))


def error_metrics(exact: np.ndarray, observed: np.ndarray) -> dict[str, float]:
    difference = observed - exact
    return {
        "relative_l2": float(np.linalg.norm(difference) / max(np.linalg.norm(exact), 1e-30)),
        "max_absolute": float(np.max(np.abs(difference))),
        "terminal_absolute": float(np.abs(difference[-1])),
    }


def window_metrics(
    times: np.ndarray, exact: np.ndarray, observed: np.ndarray
) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for stop in (5.0, 15.0, 30.0):
        mask = times <= stop + 1e-12
        result[f"t_le_{stop:g}"] = error_metrics(exact[mask], observed[mask])
    return result


def write_series(
    path: Path, times: np.ndarray, exact: np.ndarray, observed: np.ndarray
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "time",
                "exact_real",
                "exact_imag",
                "tebd_real",
                "tebd_imag",
                "absolute_error",
            ]
        )
        for time, reference, value in zip(times, exact, observed):
            writer.writerow(
                [
                    f"{time:.12g}",
                    f"{reference.real:.16e}",
                    f"{reference.imag:.16e}",
                    f"{value.real:.16e}",
                    f"{value.imag:.16e}",
                    f"{abs(value - reference):.16e}",
                ]
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-dir", required=True)
    parser.add_argument("--coarse-dir", required=True)
    parser.add_argument("--refined-dir", required=True)
    parser.add_argument("--output-dir", required=True)
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
    for manifest in (coarse_manifest, refined_manifest):
        params = manifest["params"]
        settings = manifest["settings"]
        if (
            float(params["alpha"]) != float(exact_summary["alpha"])
            or float(params["beta"]) != float(exact_summary["beta"])
            or int(params["L"]) != int(exact_summary["L"])
            or float(params["q_over_pi"]) != 1.0
            or settings["momentum_source"] != "O_q|GS>"
            or settings["fourier_normalization"] != "one_sided_trapezoid/pi"
        ):
            raise SystemExit("ED 与 TEBD 定义不一致")

    coarse_times, coarse_values = read_correlation(coarse_dir / "correlation.csv")
    refined_times, refined_values = read_correlation(refined_dir / "correlation.csv")
    if len(refined_times) != 2 * (len(coarse_times) - 1) + 1:
        raise SystemExit("refined 时间网格不是 coarse 的 dt/2")
    if not np.allclose(coarse_times, refined_times[::2], atol=1e-12, rtol=0.0):
        raise SystemExit("coarse 与 refined 时间点未对齐")

    exact_coarse, exact_energy, exact_weight = exact_correlation(
        int(exact_summary["L"]),
        float(exact_summary["alpha"]),
        float(exact_summary["beta"]),
        coarse_times,
    )
    exact_refined, _, _ = exact_correlation(
        int(exact_summary["L"]),
        float(exact_summary["alpha"]),
        float(exact_summary["beta"]),
        refined_times,
    )
    coarse_error = error_metrics(exact_coarse, coarse_values)
    refined_error = error_metrics(exact_refined, refined_values)
    dt_difference = error_metrics(refined_values[::2], coarse_values)

    write_series(output_dir / "coarse_time_domain.csv", coarse_times, exact_coarse, coarse_values)
    write_series(output_dir / "refined_time_domain.csv", refined_times, exact_refined, refined_values)
    summary = {
        "schema_version": 1,
        "status": "diagnostic",
        "instance": "alpha=0.23,beta=0.5,L=10,q/pi=1,OBC,Sz=0",
        "observable": "complex C_pi(t)",
        "budget_declared": False,
        "gate_effect": "none",
        "definition": {
            "source": "O_pi=(1/sqrt(L))*sum_j exp(i*pi*j)Sz_j",
            "correlation": "<O_pi GS|exp(-iHt)|O_pi GS>*exp(iE0t)",
            "t0_included": True,
        },
        "exact": {
            "ground_energy": exact_energy,
            "source_norm_squared": exact_weight,
        },
        "coarse": {
            "dt": float(coarse_manifest["settings"]["tstep"]),
            "samples": len(coarse_times),
            "full": coarse_error,
            "windows": window_metrics(coarse_times, exact_coarse, coarse_values),
        },
        "refined": {
            "dt": float(refined_manifest["settings"]["tstep"]),
            "samples": len(refined_times),
            "full": refined_error,
            "windows": window_metrics(refined_times, exact_refined, refined_values),
        },
        "dt_vs_dt2": dt_difference,
        "diagnosis": {
            "coarse_to_refined_l2_error_ratio": coarse_error["relative_l2"]
            / max(refined_error["relative_l2"], 1e-30),
            "interpretation": "时域仅作实现诊断；未声明预算，不改变生产准入。",
        },
        "evidence": {
            "exact_summary_sha256": sha256(exact_dir / "exact_summary.json"),
            "coarse_correlation_sha256": sha256(coarse_dir / "correlation.csv"),
            "refined_correlation_sha256": sha256(refined_dir / "correlation.csv"),
            "negative_alpha_excluded": True,
            "figure_9_excluded": True,
        },
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    files = sorted(path for path in output_dir.iterdir() if path.name != "checksums.sha256")
    (output_dir / "checksums.sha256").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in files), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
