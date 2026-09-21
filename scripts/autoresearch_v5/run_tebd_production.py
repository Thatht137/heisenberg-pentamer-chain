#!/usr/bin/env python3
"""封装正区 TEBD 计算、傅里叶变换和可复算验收。"""

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
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from progress import ProgressWriter


ROOT = Path(__file__).resolve().parents[2]
RESULTS = (ROOT / "results").resolve()
TEBD = ROOT / "scripts" / "05_tebd_pentamer_server.jl"
FOURIER = ROOT / "scripts" / "06_ft_tebd_pentamer_mapped_server.jl"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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


def finite_csv(
    path: Path, rows: int, columns: int
) -> tuple[bool, float | None, float | None, tuple[int, int], float | None]:
    values: list[float] = []
    shape = (0, 0)
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.reader(handle):
            if not row:
                continue
            shape = (shape[0] + 1, len(row))
            if len(row) != columns:
                return False, None, None, shape, None
            try:
                values.extend(float(item) for item in row)
            except ValueError:
                return False, None, None, shape, None
    if shape != (rows, columns) or not values or not all(math.isfinite(value) for value in values):
        return False, min(values) if values else None, max(values) if values else None, shape, None
    negative = sum(abs(value) for value in values if value < 0.0)
    positive = sum(value for value in values if value > 0.0)
    fraction = negative / max(negative + positive, 1e-30)
    return True, min(values), max(values), shape, fraction


def read_metrics(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["metric"]: row["value"] for row in csv.DictReader(handle)}


def progress_probe(outdir: Path) -> dict[str, object]:
    result: dict[str, object] = {}
    tebd_log = outdir / "tebd.stdout.log"
    if tebd_log.is_file():
        text = tebd_log.read_text(encoding="utf-8", errors="replace")
        matches = re.findall(r"step\s+(\d+)/(\d+)\s+\(([0-9.]+)%\).*?ETA=([0-9.]+)s", text)
        if matches:
            step, total, percent, eta = matches[-1]
            result.update(
                tebd_step=int(step),
                tebd_total_steps=int(total),
                tebd_percent=float(percent),
                tebd_eta_seconds=float(eta),
            )
    fourier_log = outdir / "fourier.stdout.log"
    if fourier_log.is_file():
        text = fourier_log.read_text(encoding="utf-8", errors="replace")
        matches = re.findall(r"q progress:\s*(\d+)/(\d+)", text)
        if matches:
            current, total = matches[-1]
            result.update(fourier_q=int(current), fourier_total_q=int(total))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cell-id", required=True)
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--alpha", type=float, required=True)
    parser.add_argument("--beta", type=float, required=True)
    parser.add_argument("--n-units", type=int, required=True)
    parser.add_argument("--tstep", type=float, required=True)
    parser.add_argument("--n-steps", type=int, required=True)
    parser.add_argument("--dmrg-maxdim", type=int, required=True)
    parser.add_argument("--tebd-maxdim", type=int, required=True)
    parser.add_argument("--dmrg-cutoff", type=float, required=True)
    parser.add_argument("--tebd-cutoff", type=float, required=True)
    parser.add_argument("--nsweeps", type=int, required=True)
    parser.add_argument("--q-points", type=int, required=True)
    parser.add_argument("--omega-points", type=int, required=True)
    parser.add_argument("--omega-max", type=float, required=True)
    parser.add_argument("--space-window", type=int, required=True)
    parser.add_argument("--time-window", choices=("sin2", "exponential"), required=True)
    parser.add_argument("--window-eta", type=float, required=True)
    parser.add_argument("--max-negative-weight-fraction", type=float, default=0.15)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--standard-sha256", required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--expected-julia-version", default="1.12.3")
    parser.add_argument("--source-commit", default="unknown")
    parser.add_argument("--julia", default="auto")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not 0.0 <= args.alpha <= 1.0 or not 0.0 <= args.beta <= 1.0:
        raise SystemExit("只允许 alpha,beta 位于 [0,1]")
    if args.n_units <= 0 or args.n_units % 2:
        raise SystemExit("n_units 必须为正偶数")
    if not 1 <= args.threads <= 16:
        raise SystemExit("threads 必须位于 [1,16]")
    if min(args.tstep, args.dmrg_cutoff, args.tebd_cutoff, args.omega_max, args.window_eta) <= 0:
        raise SystemExit("步长、截断和频率上限必须为正数")
    if min(args.n_steps, args.dmrg_maxdim, args.tebd_maxdim, args.nsweeps, args.q_points, args.omega_points) <= 0:
        raise SystemExit("计算规模参数必须为正整数")
    if not 0.0 <= args.max_negative_weight_fraction <= 1.0:
        raise SystemExit("负谱权比例门槛必须位于 [0,1]")
    outdir = Path(args.outdir).resolve()
    outdir.relative_to(RESULTS)
    if not TEBD.is_file() or not FOURIER.is_file():
        raise SystemExit("缺少 TEBD 或傅里叶变换脚本")
    if outdir.exists() and any(outdir.iterdir()) and not args.resume:
        raise SystemExit(f"拒绝覆盖已有 run: {outdir}")

    manifest_hash = sha256(ROOT / "Manifest.toml")
    if manifest_hash != args.expected_manifest_sha256:
        raise SystemExit(f"Manifest SHA-256 不匹配: {manifest_hash}")
    julia = resolve_julia(args.julia)
    version_result = subprocess.run(
        julia_command(julia, "--startup-file=no", "--version"),
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    julia_version = version_result.stdout.strip().removeprefix("julia version ")
    if version_result.returncode or julia_version != args.expected_julia_version:
        raise SystemExit(f"Julia 版本不匹配: {julia_version}")

    tag = args.cell_id.replace("/", "_").replace("\\", "_")
    alpha_text = str(args.alpha)
    beta_text = str(args.beta)
    total_sites = 5 * args.n_units
    data_dir = ROOT / "data"
    raw_corr = data_dir / f"NDSF_pentamer_alpha={alpha_text}_beta={beta_text}_L={total_sites}_{tag}.jld2"
    raw_spectrum = data_dir / f"Sqw_tebd_pentamer_alpha={alpha_text}_beta={beta_text}_{tag}.jld2"
    raw_csv = data_dir / f"Sqw_tebd_pentamer_alpha={alpha_text}_beta={beta_text}_{tag}.csv"
    raw_spectrum_csv = data_dir / f"Sqw_tebd_pentamer_alpha={alpha_text}_beta={beta_text}_raw_{tag}.csv"
    raw_metrics = data_dir / f"NDSF_pentamer_alpha={alpha_text}_beta={beta_text}_L={total_sites}_{tag}_metrics.csv"
    checkpoint = data_dir / f"CKPT_pentamer_alpha={alpha_text}_beta={beta_text}_L={total_sites}_{tag}.jld2"
    for path in (raw_corr, raw_spectrum, raw_csv, raw_spectrum_csv, raw_metrics, checkpoint):
        if path.exists() and not args.resume:
            raise SystemExit(f"拒绝复用已有输出: {path}")

    tebd_command = julia_command(
        julia,
        "--threads=" + str(args.threads),
        "--startup-file=no",
        "--project=.",
        str(TEBD.relative_to(ROOT)),
    )
    fourier_command = julia_command(
        julia,
        "--threads=" + str(args.threads),
        "--startup-file=no",
        "--project=.",
        str(FOURIER.relative_to(ROOT)),
    )
    if args.dry_run:
        print(json.dumps({"cell_id": args.cell_id, "tebd": tebd_command, "fourier": fourier_command}, ensure_ascii=False))
        return

    outdir.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    write_json(outdir / "run_config.json", {
        "schema_version": 1,
        "cell_id": args.cell_id,
        "alpha": args.alpha,
        "beta": args.beta,
        "n_units": args.n_units,
        "L": total_sites,
        "tstep": args.tstep,
        "n_steps": args.n_steps,
        "tmax": args.tstep * args.n_steps,
        "dmrg_maxdim": args.dmrg_maxdim,
        "tebd_maxdim": args.tebd_maxdim,
        "dmrg_cutoff": args.dmrg_cutoff,
        "tebd_cutoff": args.tebd_cutoff,
        "nsweeps": args.nsweeps,
        "q_points": args.q_points,
        "omega_points": args.omega_points,
        "omega_max": args.omega_max,
        "space_window": args.space_window,
        "time_window": args.time_window,
        "window_eta": args.window_eta,
        "max_negative_weight_fraction": args.max_negative_weight_fraction,
        "threads": args.threads,
        "output_tag": tag,
        "manifest_sha256": manifest_hash,
    })
    write_json(outdir / "status.json", {"status": "running", "started_at": started.isoformat()})
    progress = ProgressWriter(
        outdir,
        {
            "job_type": "tebd_production",
            "cell_id": args.cell_id,
            "phase": "tebd",
            "tebd_total_steps": args.n_steps,
            "fourier_total_q": args.q_points,
        },
        probe=lambda: progress_probe(outdir),
    )
    progress.start()
    atexit.register(lambda: progress.finish(status="aborted", returncode=1))

    environment = os.environ.copy()
    environment.update({
        "JULIA_PKG_OFFLINE": "true",
        "JULIA_PKG_SERVER": "",
        "HTTP_PROXY": "http://127.0.0.1:9",
        "HTTPS_PROXY": "http://127.0.0.1:9",
        "JULIA_NUM_THREADS": str(args.threads),
        "PENTAMER_N_UNITS": str(args.n_units),
        "PENTAMER_ALPHA": alpha_text,
        "PENTAMER_BETA": beta_text,
        "PENTAMER_TSTEP": str(args.tstep),
        "PENTAMER_N_STEPS": str(args.n_steps),
        "PENTAMER_DMRG_MAXDIM": str(args.dmrg_maxdim),
        "PENTAMER_TEBD_MAXDIM": str(args.tebd_maxdim),
        "PENTAMER_DMRG_CUTOFF": str(args.dmrg_cutoff),
        "PENTAMER_TEBD_CUTOFF": str(args.tebd_cutoff),
        "PENTAMER_NSWEEPS": str(args.nsweeps),
        "PENTAMER_OUTPUT_TAG": tag,
        "PENTAMER_Q_POINTS": str(args.q_points),
        "PENTAMER_OMEGA_POINTS": str(args.omega_points),
        "PENTAMER_OMEGA_MAX": str(args.omega_max),
        "PENTAMER_SPACE_WINDOW": str(args.space_window),
        "PENTAMER_TIME_WINDOW": args.time_window,
        "PENTAMER_WINDOW_ETA": str(args.window_eta),
    })
    tebd_start = time.monotonic()
    with (outdir / "tebd.stdout.log").open("w", encoding="utf-8") as stdout, (outdir / "tebd.stderr.log").open("w", encoding="utf-8") as stderr:
        tebd_result = subprocess.run(tebd_command, cwd=ROOT, env=environment, stdout=stdout, stderr=stderr, check=False)
    tebd_seconds = time.monotonic() - tebd_start
    progress.update(phase="fourier", tebd_returncode=tebd_result.returncode)
    fourier_result = subprocess.CompletedProcess(fourier_command, 1)
    fourier_seconds = 0.0
    if tebd_result.returncode == 0:
        fourier_start = time.monotonic()
        with (outdir / "fourier.stdout.log").open("w", encoding="utf-8") as stdout, (outdir / "fourier.stderr.log").open("w", encoding="utf-8") as stderr:
            fourier_result = subprocess.run(fourier_command, cwd=ROOT, env=environment, stdout=stdout, stderr=stderr, check=False)
        fourier_seconds = time.monotonic() - fourier_start
    progress.update(phase="postprocess", fourier_returncode=fourier_result.returncode)

    copied: list[Path] = []
    for source, name in (
        (raw_corr, "correlation.jld2"),
        (raw_spectrum, "spectrum.jld2"),
        (raw_csv, "spectrum.csv"),
        (raw_spectrum_csv, "spectrum_raw.csv"),
        (raw_metrics, "metrics.csv"),
    ):
        if source.is_file():
            target = outdir / name
            shutil.copy2(source, target)
            copied.append(target)

    csv_ok = False
    csv_min = None
    csv_max = None
    csv_shape = (0, 0)
    spectrum_csv = outdir / "spectrum.csv"
    if spectrum_csv.is_file():
        csv_ok, csv_min, csv_max, csv_shape, _ = finite_csv(
            spectrum_csv, args.q_points, args.omega_points
        )
    raw_csv_ok = False
    raw_csv_min = None
    raw_csv_max = None
    raw_csv_shape = (0, 0)
    raw_negative_fraction = None
    raw_spectrum_csv_path = outdir / "spectrum_raw.csv"
    if raw_spectrum_csv_path.is_file():
        raw_csv_ok, raw_csv_min, raw_csv_max, raw_csv_shape, raw_negative_fraction = finite_csv(
            raw_spectrum_csv_path, args.q_points, args.omega_points
        )
    metrics = read_metrics(outdir / "metrics.csv") if (outdir / "metrics.csv").is_file() else {}
    variance_per_site = float(metrics.get("variance_per_site", "inf"))
    total_sz = float(metrics.get("total_sz", "inf"))
    t0_included = metrics.get("t0_included") == "true"
    accepted_checks = {
        "tebd_execution": tebd_result.returncode == 0,
        "fourier_execution": fourier_result.returncode == 0,
        "correlation_artifact": (outdir / "correlation.jld2").is_file(),
        "spectrum_artifact": (outdir / "spectrum.jld2").is_file(),
        "raw_spectrum_csv_artifact": raw_spectrum_csv_path.is_file(),
        "spectrum_csv_shape": csv_ok,
        "spectrum_finite": csv_ok,
        "spectrum_nonnegative": csv_ok and csv_min is not None and csv_min >= -1e-10,
        "raw_spectrum_csv_shape": raw_csv_ok,
        "raw_spectrum_finite": raw_csv_ok,
        "t0_included": t0_included,
        "ground_variance": variance_per_site <= 1e-8,
        "sector_sz0": abs(total_sz) <= 1e-8,
        "raw_negative_weight_fraction": raw_csv_ok
        and raw_negative_fraction is not None
        and raw_negative_fraction <= args.max_negative_weight_fraction,
    }
    accepted = all(accepted_checks.values())
    finished = datetime.now(timezone.utc)
    manifest = {
        "schema_version": 1,
        "cell_id": args.cell_id,
        "status": "success" if tebd_result.returncode == 0 and fourier_result.returncode == 0 else "failed",
        "accepted": accepted,
        "params": {"alpha": args.alpha, "beta": args.beta, "N_units": args.n_units, "L": total_sites},
        "settings": {
            "method": "finite_dmrg_tebd_szz",
            "boundary": "OBC",
            "q_points": args.q_points,
            "omega_points": args.omega_points,
            "omega_max": args.omega_max,
            "space_window": args.space_window,
            "time_window": args.time_window,
            "window_eta": args.window_eta,
            "time_integration": "trapezoid",
            "t0_included": True,
            "max_negative_weight_fraction": args.max_negative_weight_fraction,
            "threads": args.threads,
        },
        "diagnostics": {
            "tstep": args.tstep,
            "tmax": args.tstep * args.n_steps,
            "dmrg_maxdim": args.dmrg_maxdim,
            "tebd_maxdim": args.tebd_maxdim,
            "nsweeps": args.nsweeps,
            "tebd_seconds": tebd_seconds,
            "fourier_seconds": fourier_seconds,
            "spectrum_shape": list(csv_shape),
            "spectrum_min": csv_min,
            "spectrum_max": csv_max,
            "raw_spectrum_shape": list(raw_csv_shape),
            "raw_spectrum_min": raw_csv_min,
            "raw_spectrum_max": raw_csv_max,
            "raw_negative_weight_fraction": raw_negative_fraction,
            "variance_per_site": variance_per_site,
            "total_sz": total_sz,
            "dmrg_actual_maxdim": float(metrics.get("dmrg_actual_maxdim", "nan")),
        },
        "acceptance": accepted_checks,
        "provenance": {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "julia_version": julia_version,
            "manifest_sha256": manifest_hash,
            "standard_sha256": args.standard_sha256,
            "source_commit": args.source_commit,
            "julia_pkg_offline": True,
            "negative_alpha_excluded": True,
            "figure_9_excluded": True,
            "code_sha256": {
                str(path.relative_to(ROOT)): sha256(path)
                for path in (ROOT / "Project.toml", ROOT / "Manifest.toml", ROOT / "src" / "PentamerChain.jl", TEBD, FOURIER, ROOT / "scripts" / "autoresearch_v5" / "progress.py", Path(__file__))
            },
        },
        "timing": {"started_at": started.isoformat(), "finished_at": finished.isoformat()},
        "returncode": 0 if accepted else 1,
    }
    write_json(outdir / "manifest.json", manifest)
    write_json(outdir / "status.json", {"status": manifest["status"], "accepted": accepted, "returncode": manifest["returncode"], "finished_at": finished.isoformat()})
    progress.finish(
        status=manifest["status"],
        returncode=manifest["returncode"],
        phase="finished",
        accepted=accepted,
        tebd_seconds=tebd_seconds,
        fourier_seconds=fourier_seconds,
    )
    files = sorted(path for path in outdir.rglob("*") if path.is_file() and path.name != "checksums.sha256")
    (outdir / "checksums.sha256").write_text("".join(f"{sha256(path)}  {path.relative_to(outdir).as_posix()}\n" for path in files), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))
    if not accepted:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
