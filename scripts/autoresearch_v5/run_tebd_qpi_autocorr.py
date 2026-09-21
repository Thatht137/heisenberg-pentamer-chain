#!/usr/bin/env python3
"""封装严格 q=pi 自相关 TEBD、进度和验收。"""

from __future__ import annotations

import argparse
import atexit
import csv
import hashlib
import json
import math
import os
import platform
import re
import shutil
import socket
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from progress import ProgressWriter


ROOT = Path(__file__).resolve().parents[2]
RESULTS = (ROOT / "results").resolve()
SCRIPT = ROOT / "scripts" / "autoresearch_v5" / "tebd_qpi_autocorr.jl"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def resolve_julia(value: str) -> str:
    if value != "auto":
        return value
    server = Path.home() / ".juliaup" / "bin" / "julia"
    if server.is_file():
        return str(server)
    found = shutil.which("julia")
    if found:
        return found
    raise SystemExit("找不到 Julia")


def julia_command(julia: str, *args: str) -> list[str]:
    command = [julia]
    if ".juliaup" in julia.replace("\\", "/"):
        command.append("+release")
    command.extend(args)
    return command


def read_metrics(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {row["metric"]: row["value"] for row in rows}


def read_spectrum(path: Path) -> list[dict[str, float]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [
            {key: float(value) for key, value in row.items()}
            for row in csv.DictReader(handle)
        ]


def read_correlation(path: Path) -> list[dict[str, float]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [
            {key: float(value) for key, value in row.items()}
            for row in csv.DictReader(handle)
        ]


def progress_probe(outdir: Path) -> dict[str, object]:
    log = outdir / "julia.stdout.log"
    if not log.is_file():
        return {}
    text = log.read_text(encoding="utf-8", errors="replace")
    matches = re.findall(
        r"step\s+(\d+)/(\d+)\s+\(([0-9.]+)%\).*?ETA=([0-9.]+)s", text
    )
    if not matches:
        return {"phase": "dmrg"}
    step, total, percent, eta = matches[-1]
    return {
        "phase": "tebd",
        "completed_steps": int(step),
        "total_steps": int(total),
        "percent": float(percent),
        "eta_seconds": float(eta),
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--cell-id", required=True)
    result.add_argument("--outdir", required=True)
    result.add_argument("--alpha", type=float, required=True)
    result.add_argument("--beta", type=float, required=True)
    result.add_argument("--n-units", type=int, required=True)
    result.add_argument("--eta", type=float, default=0.1)
    result.add_argument("--omega-min", type=float, default=0.0)
    result.add_argument("--omega-max", type=float, default=3.0)
    result.add_argument("--omega-step", type=float, default=0.05)
    result.add_argument("--tstep", type=float, required=True)
    result.add_argument("--n-steps", type=int, required=True)
    result.add_argument("--dmrg-maxdim", type=int, required=True)
    result.add_argument("--tebd-maxdim", type=int, required=True)
    result.add_argument("--nsweeps", type=int, required=True)
    result.add_argument("--dmrg-cutoff", type=float, required=True)
    result.add_argument("--tebd-cutoff", type=float, required=True)
    result.add_argument("--checkpoint-interval", type=int, default=100)
    result.add_argument("--threads", type=int, default=4)
    result.add_argument("--expected-julia-version")
    result.add_argument("--expected-manifest-sha256")
    result.add_argument("--standard-sha256")
    result.add_argument("--source-commit", default="working-tree")
    result.add_argument("--julia", default="auto")
    result.add_argument("--resume", action="store_true")
    result.add_argument("--stop-after-step", type=int, default=0)
    result.add_argument("--dry-run", action="store_true")
    return result


def main() -> None:
    args = parser().parse_args()
    if not 0.0 <= args.alpha <= 1.0 or not 0.0 <= args.beta <= 1.0:
        raise SystemExit("只允许 alpha,beta 位于 [0,1]")
    if args.n_units <= 0 or args.n_units % 2:
        raise SystemExit("n_units 必须为正偶数")
    if not 1 <= args.threads <= 16:
        raise SystemExit("threads 必须位于 [1,16]")
    if min(
        args.eta,
        args.omega_step,
        args.tstep,
        args.dmrg_cutoff,
        args.tebd_cutoff,
    ) <= 0:
        raise SystemExit("步长、展宽和截断必须为正数")
    if min(
        args.n_steps,
        args.dmrg_maxdim,
        args.tebd_maxdim,
        args.nsweeps,
        args.checkpoint_interval,
    ) <= 0:
        raise SystemExit("计算规模必须为正整数")
    if args.omega_min < 0 or args.omega_max <= args.omega_min:
        raise SystemExit("omega 网格无效")
    if not 0 <= args.stop_after_step < args.n_steps:
        raise SystemExit("stop-after-step 必须位于 [0,n_steps)")

    outdir = Path(args.outdir).resolve()
    outdir.relative_to(RESULTS)
    if outdir.exists() and any(outdir.iterdir()) and not args.resume:
        raise SystemExit(f"拒绝覆盖已有 run: {outdir}")
    if not SCRIPT.is_file():
        raise SystemExit("缺少严格 q=pi Julia 脚本")

    manifest_hash = sha256(ROOT / "Manifest.toml")
    if (
        args.expected_manifest_sha256
        and manifest_hash != args.expected_manifest_sha256
    ):
        raise SystemExit(f"Manifest SHA-256 不匹配: {manifest_hash}")
    standard = ROOT / "docs" / "pentamer_reproduction_standard.md"
    standard_hash = sha256(standard)
    if args.standard_sha256 and standard_hash != args.standard_sha256:
        raise SystemExit(f"研究标准 SHA-256 不匹配: {standard_hash}")

    julia = resolve_julia(args.julia)
    version_result = subprocess.run(
        julia_command(julia, "--startup-file=no", "--version"),
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    julia_version = version_result.stdout.strip().removeprefix("julia version ")
    if version_result.returncode:
        raise SystemExit("Julia 版本检查失败")
    if args.expected_julia_version and julia_version != args.expected_julia_version:
        raise SystemExit(f"Julia 版本不匹配: {julia_version}")

    total_sites = 5 * args.n_units
    config = {
        "schema_version": 1,
        "cell_id": args.cell_id,
        "alpha": args.alpha,
        "beta": args.beta,
        "n_units": args.n_units,
        "L": total_sites,
        "q_over_pi": 1.0,
        "eta": args.eta,
        "omega_min": args.omega_min,
        "omega_max": args.omega_max,
        "omega_step": args.omega_step,
        "tstep": args.tstep,
        "n_steps": args.n_steps,
        "tmax": args.tstep * args.n_steps,
        "dmrg_maxdim": args.dmrg_maxdim,
        "tebd_maxdim": args.tebd_maxdim,
        "nsweeps": args.nsweeps,
        "dmrg_cutoff": args.dmrg_cutoff,
        "tebd_cutoff": args.tebd_cutoff,
        "checkpoint_interval": args.checkpoint_interval,
        "threads": args.threads,
        "manifest_sha256": manifest_hash,
        "standard_sha256": standard_hash,
    }
    existing_config = outdir / "run_config.json"
    if args.resume and existing_config.is_file():
        previous = json.loads(existing_config.read_text(encoding="utf-8"))
        if previous != config:
            raise SystemExit("恢复参数与已有 run_config.json 不一致")

    command = julia_command(
        julia,
        f"--threads={args.threads}",
        "--startup-file=no",
        "--project=.",
        str(SCRIPT.relative_to(ROOT)),
        str(outdir),
        str(args.alpha),
        str(args.beta),
        str(args.n_units),
        str(args.eta),
        str(args.omega_min),
        str(args.omega_max),
        str(args.omega_step),
        str(args.tstep),
        str(args.n_steps),
        str(args.dmrg_maxdim),
        str(args.tebd_maxdim),
        str(args.nsweeps),
        str(args.dmrg_cutoff),
        str(args.tebd_cutoff),
        str(args.checkpoint_interval),
    )
    if args.dry_run:
        print(
            json.dumps(
                {
                    "cell_id": args.cell_id,
                    "command": command,
                    "config": config,
                    "offline": True,
                },
                ensure_ascii=False,
            )
        )
        return

    outdir.mkdir(parents=True, exist_ok=True)
    write_json(existing_config, config)
    started = datetime.now(timezone.utc)
    write_json(outdir / "status.json", {"status": "running", "started_at": started.isoformat()})
    progress = ProgressWriter(
        outdir,
        {
            "job_type": "tebd_qpi_autocorrelation",
            "cell_id": args.cell_id,
            "phase": "dmrg",
            "total_steps": args.n_steps,
        },
        probe=lambda: progress_probe(outdir),
    )
    progress.start()
    atexit.register(lambda: progress.finish(status="aborted", returncode=1))

    environment = os.environ.copy()
    environment.update(
        {
            "JULIA_PKG_OFFLINE": "true",
            "JULIA_PKG_SERVER": "",
            "HTTP_PROXY": "http://127.0.0.1:9",
            "HTTPS_PROXY": "http://127.0.0.1:9",
            "JULIA_NUM_THREADS": str(args.threads),
        }
    )
    if args.stop_after_step:
        environment["PENTAMER_STOP_AFTER_STEP"] = str(args.stop_after_step)
    run_start = time.monotonic()
    with (outdir / "julia.stdout.log").open(
        "a" if args.resume else "w", encoding="utf-8"
    ) as stdout, (outdir / "julia.stderr.log").open(
        "a" if args.resume else "w", encoding="utf-8"
    ) as stderr:
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=environment,
            stdout=stdout,
            stderr=stderr,
            check=False,
        )
    wall_seconds = time.monotonic() - run_start

    metrics_path = outdir / "metrics.csv"
    spectrum_path = outdir / "spectrum.csv"
    correlation_path = outdir / "correlation.csv"
    metrics = read_metrics(metrics_path) if metrics_path.is_file() else {}
    spectrum = read_spectrum(spectrum_path) if spectrum_path.is_file() else []
    correlation = read_correlation(correlation_path) if correlation_path.is_file() else []
    intensities = [row["intensity"] for row in spectrum]
    finite_spectrum = bool(intensities) and all(math.isfinite(value) for value in intensities)
    spectrum_max = max(intensities) if intensities else None
    spectrum_min = min(intensities) if intensities else None
    source_norm = float(metrics.get("source_norm_squared", "nan"))
    correlation_t0 = complex(
        float(metrics.get("correlation_t0_real", "nan")),
        float(metrics.get("correlation_t0_imag", "nan")),
    )
    t0_tolerance = 1e-10 * max(abs(source_norm), 1.0)
    expected_omega_points = round((args.omega_max - args.omega_min) / args.omega_step) + 1
    checks = {
        "julia_execution": result.returncode == 0,
        "correlation_artifact": correlation_path.is_file(),
        "spectrum_artifact": spectrum_path.is_file(),
        "jld2_artifacts": (outdir / "correlation.jld2").is_file() and (outdir / "spectrum.jld2").is_file(),
        "t0_included": len(correlation) == args.n_steps + 1 and bool(correlation) and abs(correlation[0]["time"]) <= 1e-15,
        "t0_sum_rule": math.isfinite(source_norm) and abs(correlation_t0 - source_norm) <= t0_tolerance,
        "spectrum_grid_complete": len(spectrum) == expected_omega_points,
        "spectrum_finite": finite_spectrum,
        "spectrum_nonnegative": finite_spectrum and spectrum_min is not None and spectrum_max is not None and spectrum_min >= -1e-10 * max(spectrum_max, 1.0),
        "ground_variance": float(metrics.get("variance_per_site", "inf")) <= 1e-8,
        "sector_sz0": abs(float(metrics.get("total_sz", "inf"))) <= 1e-8,
        "qpi_normalization": metrics.get("momentum_normalization") == "1/sqrt(L)" and metrics.get("fourier_normalization") == "one_sided_trapezoid/pi",
    }
    accepted = all(checks.values())
    finished = datetime.now(timezone.utc)
    manifest = {
        "schema_version": 1,
        "cell_id": args.cell_id,
        "status": "success" if result.returncode == 0 else "failed",
        "accepted": accepted,
        "params": {
            "alpha": args.alpha,
            "beta": args.beta,
            "N_units": args.n_units,
            "L": total_sites,
            "q_over_pi": 1.0,
        },
        "settings": {
            "method": "finite_dmrg_tebd_qpi_autocorrelation",
            "boundary": "OBC",
            "sector": "Sz=0",
            "momentum_source": "O_q|GS>",
            "momentum_normalization": "1/sqrt(L)",
            "t0_included": True,
            "trotter_order": 2,
            "tstep": args.tstep,
            "tmax": args.tstep * args.n_steps,
            "time_window": "exponential",
            "window_eta": args.eta,
            "fourier_normalization": "one_sided_trapezoid/pi",
            "omega_min": args.omega_min,
            "omega_max": args.omega_max,
            "omega_step": args.omega_step,
            "dmrg_maxdim": args.dmrg_maxdim,
            "tebd_maxdim": args.tebd_maxdim,
            "dmrg_cutoff": args.dmrg_cutoff,
            "tebd_cutoff": args.tebd_cutoff,
            "nsweeps": args.nsweeps,
            "threads": args.threads,
        },
        "diagnostics": {
            "source_norm_squared": source_norm,
            "correlation_t0_real": correlation_t0.real,
            "correlation_t0_imag": correlation_t0.imag,
            "relative_norm_drift": float(metrics.get("relative_norm_drift", "nan")),
            "variance_per_site": float(metrics.get("variance_per_site", "nan")),
            "total_sz": float(metrics.get("total_sz", "nan")),
            "dmrg_actual_maxdim": float(metrics.get("dmrg_actual_maxdim", "nan")),
            "tebd_actual_maxdim": float(metrics.get("tebd_actual_maxdim", "nan")),
            "spectrum_min": spectrum_min,
            "spectrum_max": spectrum_max,
            "wall_seconds": wall_seconds,
            "dmrg_seconds": float(metrics.get("dmrg_seconds", "nan")),
            "tebd_seconds": float(metrics.get("tebd_seconds", "nan")),
            "fourier_seconds": float(metrics.get("fourier_seconds", "nan")),
        },
        "acceptance": checks,
        "provenance": {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "julia_version": julia_version,
            "manifest_sha256": manifest_hash,
            "standard_sha256": standard_hash,
            "source_commit": args.source_commit,
            "julia_pkg_offline": True,
            "negative_alpha_excluded": True,
            "figure_9_excluded": True,
            "code_sha256": {
                str(path.relative_to(ROOT)): sha256(path)
                for path in (
                    ROOT / "Project.toml",
                    ROOT / "Manifest.toml",
                    ROOT / "src" / "PentamerChain.jl",
                    ROOT / "src" / "hamiltonian.jl",
                    SCRIPT,
                    ROOT / "scripts" / "autoresearch_v5" / "progress.py",
                    Path(__file__),
                )
            },
        },
        "timing": {"started_at": started.isoformat(), "finished_at": finished.isoformat()},
        "returncode": 0 if accepted else 1,
    }
    write_json(outdir / "manifest.json", manifest)
    write_json(
        outdir / "status.json",
        {
            "status": manifest["status"],
            "accepted": accepted,
            "returncode": manifest["returncode"],
            "finished_at": finished.isoformat(),
        },
    )
    progress.finish(
        status=manifest["status"],
        returncode=manifest["returncode"],
        phase="finished",
        accepted=accepted,
        completed_steps=args.n_steps if result.returncode == 0 else None,
        wall_seconds=wall_seconds,
    )
    files = sorted(
        path
        for path in outdir.rglob("*")
        if path.is_file() and path.name != "checksums.sha256"
    )
    (outdir / "checksums.sha256").write_text(
        "".join(
            f"{sha256(path)}  {path.relative_to(outdir).as_posix()}\n"
            for path in files
        ),
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False))
    if not accepted:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
