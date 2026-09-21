#!/usr/bin/env python3
"""在直连服务器封装可恢复的 CV-DSF q 切片。"""

from __future__ import annotations

import argparse
import atexit
import csv
import hashlib
import json
import os
import platform
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from progress import ProgressWriter


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_MANIFEST_SHA256 = "37a53ffd73db57b9db9c4ce11f6265a9a41ac2035dc421b01f9a633d893ba12c"
MUTABLE_OUTPUTS = {
    "checkpoint_latest.jld2",
    "manifest.json",
    "metrics.csv",
    "spectrum.csv",
    "spectrum.jld2",
    "status.json",
    "progress.json",
    "stderr.log",
    "stdout.log",
    "sweep_history.csv",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_text(path: Path, content: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.unlink(missing_ok=True)
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def write_json(path: Path, payload: dict[str, object]) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))


def read_metrics(path: Path) -> dict[str, object]:
    values: dict[str, object] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            value = row["value"]
            if value.lower() in {"true", "false"}:
                values[row["metric"]] = value.lower() == "true"
                continue
            try:
                values[row["metric"]] = float(value)
            except ValueError:
                values[row["metric"]] = value
    return values


def read_intensities(path: Path) -> list[float]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [float(row["intensity"]) for row in csv.DictReader(handle)]


def progress_probe(outdir: Path) -> dict[str, object]:
    points = sorted((outdir / "points").glob("omega-*.csv")) if (outdir / "points").is_dir() else []
    stdout = outdir / "stdout.log"
    result: dict[str, object] = {"completed_points": len(points)}
    if stdout.is_file():
        stat = stdout.stat()
        result["stdout_bytes"] = stat.st_size
        result["stdout_last_change"] = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
    return result


def ordered_omegas(
    omega_min: float, omega_max: float, omega_step: float, omega_order: str
) -> list[float]:
    if omega_step <= 0 or omega_min > omega_max:
        raise ValueError("频率网格参数无效")
    if omega_order not in {"ascending", "descending"}:
        raise ValueError("频率顺序无效")
    count = int(round((omega_max - omega_min) / omega_step)) + 1
    grid = [round(omega_min + index * omega_step, 12) for index in range(count)]
    if abs(grid[-1] - omega_max) > 1e-10:
        raise ValueError("频率范围不能被步长整除")
    return list(reversed(grid)) if omega_order == "descending" else grid


def verify_checksums(outdir: Path) -> None:
    checksum_path = outdir / "checksums.sha256"
    status_path = outdir / "status.json"
    status = (
        json.loads(status_path.read_text(encoding="utf-8")).get("status")
        if status_path.is_file()
        else None
    )
    interrupted = status in {None, "running"}
    if not checksum_path.is_file():
        if interrupted:
            return
        raise SystemExit("已结束的恢复任务缺少 checksums.sha256")
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split(maxsplit=1)
        path = (outdir / relative).resolve()
        path.relative_to(outdir)
        mutable = path.name in MUTABLE_OUTPUTS or path.name.startswith("resource-attempt-")
        if interrupted and mutable:
            continue
        if not path.is_file() or sha256(path) != expected:
            raise SystemExit(f"恢复校验失败: {relative}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cell-id", required=True)
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--alpha", type=float, required=True)
    parser.add_argument("--beta", type=float, required=True)
    parser.add_argument("--n-units", type=int, required=True)
    parser.add_argument("--q-over-pi", type=float, required=True)
    parser.add_argument("--eta", type=float, required=True)
    parser.add_argument("--omega-min", type=float, required=True)
    parser.add_argument("--omega-max", type=float, required=True)
    parser.add_argument("--omega-step", type=float, required=True)
    parser.add_argument(
        "--omega-order", choices=("ascending", "descending"), default="ascending"
    )
    parser.add_argument("--dmrg-maxdim", type=int, required=True)
    parser.add_argument("--cv-maxdim", type=int, required=True)
    parser.add_argument("--nsweeps", type=int, required=True)
    parser.add_argument("--cutoff", type=float, required=True)
    parser.add_argument("--cv-cutoff", type=float, required=True)
    parser.add_argument("--max-cv-residual", type=float, default=1e-5)
    parser.add_argument("--max-new-points", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--expected-julia-version", default="1.12.3")
    args = parser.parse_args()
    if not 0.0 <= args.alpha <= 1.0 or not 0.0 <= args.beta <= 1.0:
        raise SystemExit("alpha 和 beta 必须位于 [0,1]")
    if args.n_units <= 0 or args.n_units % 2:
        raise SystemExit("n_units 必须为正偶数")
    if not 0.0 <= args.q_over_pi <= 2.0:
        raise SystemExit("q_over_pi 必须位于 [0,2]")
    if args.eta <= 0 or args.omega_min < 0:
        raise SystemExit("eta 必须为正数且 omega_min 不得为负数")
    if not 1 <= args.threads <= 16:
        raise SystemExit("线程数必须位于 [1,16]")
    if min(args.dmrg_maxdim, args.cv_maxdim, args.nsweeps) <= 0:
        raise SystemExit("维数上限和 sweep 数必须为正整数")
    if min(args.cutoff, args.cv_cutoff, args.max_cv_residual, args.omega_step) <= 0:
        raise SystemExit("截断阈值、残差门槛和频率步长必须为正数")
    if args.omega_min > args.omega_max:
        raise SystemExit("omega_min 不得大于 omega_max")
    if args.max_new_points < 0:
        raise SystemExit("max_new_points 不得为负数")

    try:
        omegas = ordered_omegas(
            args.omega_min, args.omega_max, args.omega_step, args.omega_order
        )
    except ValueError as error:
        raise SystemExit(str(error)) from error

    outdir = Path(args.outdir).resolve()
    outdir.relative_to((ROOT / "results").resolve())
    source_files = [
        ROOT / "Project.toml",
        ROOT / "Manifest.toml",
        ROOT / "src" / "PentamerChain.jl",
        ROOT / "src" / "hamiltonian.jl",
        ROOT / "scripts" / "autoresearch_v5" / "cv_dsf_resumable.jl",
        ROOT / "scripts" / "autoresearch_v5" / "run_cv_dsf_resumable.py",
        ROOT / "scripts" / "autoresearch_v5" / "progress.py",
    ]
    manifest_hash = sha256(ROOT / "Manifest.toml")
    if manifest_hash != EXPECTED_MANIFEST_SHA256:
        raise SystemExit(f"Manifest SHA-256 不匹配: {manifest_hash}")
    julia = Path.home() / ".juliaup" / "bin" / "julia"
    version = subprocess.run(
        [str(julia), "+release", "--startup-file=no", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    julia_version = version.stdout.strip().removeprefix("julia version ")
    if version.returncode or julia_version != args.expected_julia_version:
        raise SystemExit(f"Julia 版本不匹配: {julia_version}")
    config = {
        "schema_version": 2,
        "cell_id": args.cell_id,
        "alpha": args.alpha,
        "beta": args.beta,
        "n_units": args.n_units,
        "q_over_pi": args.q_over_pi,
        "eta": args.eta,
        "omega_min": args.omega_min,
        "omega_max": args.omega_max,
        "omega_step": args.omega_step,
        "omega_order": args.omega_order,
        "dmrg_maxdim": args.dmrg_maxdim,
        "cv_maxdim": args.cv_maxdim,
        "nsweeps": args.nsweeps,
        "dmrg_cutoff": args.cutoff,
        "cv_cutoff": args.cv_cutoff,
        "max_cv_residual": args.max_cv_residual,
        "threads": args.threads,
        "julia_version": julia_version,
        "manifest_sha256": manifest_hash,
        "code_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in source_files},
    }
    config_path = outdir / "run_config.json"
    if args.resume:
        if not config_path.is_file():
            raise SystemExit("恢复任务缺少 run_config.json")
        existing = json.loads(config_path.read_text(encoding="utf-8"))
        if existing != config:
            raise SystemExit("恢复配置与原任务不一致")
        verify_checksums(outdir)
        (outdir / "checksums.sha256.tmp").unlink(missing_ok=True)
    else:
        if outdir.exists() and any(outdir.iterdir()):
            raise SystemExit(f"拒绝覆盖已有 cell: {outdir}")
        outdir.mkdir(parents=True, exist_ok=True)
        write_json(config_path, config)

    attempt = len(list(outdir.glob("attempt-*.json"))) + 1
    started = datetime.now(timezone.utc)
    write_json(outdir / "status.json", {
        "status": "running",
        "attempt": attempt,
        "started_at": started.isoformat(),
    })
    attempt_path = outdir / f"attempt-{attempt:04d}.json"
    write_json(attempt_path, {
        "attempt": attempt,
        "resume": args.resume,
        "max_new_points": args.max_new_points,
        "status": "running",
        "started_at": started.isoformat(),
    })
    total_points = len(omegas)
    progress = ProgressWriter(
        outdir,
        {
            "job_type": "cv_dsf_resumable",
            "cell_id": args.cell_id,
            "phase": "julia_linsolve",
            "total_points": total_points,
            "max_new_points": args.max_new_points,
        },
        probe=lambda: progress_probe(outdir),
    )
    progress.start()
    atexit.register(lambda: progress.finish(status="aborted", returncode=1))
    resource_path = outdir / f"resource-attempt-{attempt:04d}.log"
    command = [
        "/usr/bin/time", "-v", "-o", str(resource_path),
        "nice", "-n", "10", str(julia), "+release", f"--threads={args.threads}",
        "--startup-file=no", "--project=.",
        "scripts/autoresearch_v5/cv_dsf_resumable.jl",
        str(outdir), str(args.alpha), str(args.beta), str(args.n_units),
        str(args.q_over_pi), str(args.eta), str(args.omega_min), str(args.omega_max),
        str(args.omega_step), str(args.dmrg_maxdim), str(args.cv_maxdim),
        str(args.nsweeps), str(args.cutoff), str(args.cv_cutoff),
        str(args.max_new_points), args.omega_order,
    ]
    environment = os.environ.copy()
    environment.update({
        "JULIA_PKG_OFFLINE": "true",
        "JULIA_PKG_SERVER": "",
        "HTTP_PROXY": "http://127.0.0.1:9",
        "HTTPS_PROXY": "http://127.0.0.1:9",
    })
    with (outdir / "stdout.log").open("a", encoding="utf-8") as stdout, \
            (outdir / "stderr.log").open("a", encoding="utf-8") as stderr:
        stdout.write(f"\n=== attempt {attempt} started {started.isoformat()} ===\n")
        stdout.flush()
        result = subprocess.run(
            command, cwd=ROOT, env=environment, stdout=stdout, stderr=stderr, check=False
        )

    metrics = read_metrics(outdir / "metrics.csv") if (outdir / "metrics.csv").is_file() else {}
    intensities = (
        read_intensities(outdir / "spectrum.csv")
        if (outdir / "spectrum.csv").is_file()
        else []
    )
    complete = metrics.get("complete") is True
    checks = {
        "ground_variance": isinstance(metrics.get("variance_per_site"), float)
        and metrics["variance_per_site"] <= 1e-8,
        "dmrg_truncation": isinstance(metrics.get("max_dmrg_truncation"), float)
        and metrics["max_dmrg_truncation"] <= 1e-8,
        "cv_residual": complete and isinstance(metrics.get("max_cv_residual"), float)
        and metrics["max_cv_residual"] <= args.max_cv_residual,
        "nonnegative": complete and bool(intensities)
        and min(intensities) >= -1e-10 * max(intensities),
    }
    finished = datetime.now(timezone.utc)
    if result.returncode:
        run_status = "failed"
    elif complete:
        run_status = "success"
    else:
        run_status = "partial"
    attempt_record = {
        "attempt": attempt,
        "resume": args.resume,
        "max_new_points": args.max_new_points,
        "status": run_status,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "returncode": result.returncode,
        "resource_log": resource_path.name,
        "completed_points": metrics.get("completed_points"),
        "total_points": metrics.get("total_points"),
        "cv_seconds_this_attempt": metrics.get("cv_seconds_this_attempt"),
    }
    write_json(attempt_path, attempt_record)
    manifest = {
        "schema_version": 2,
        "cell_id": args.cell_id,
        "status": run_status,
        "params": {
            "alpha": args.alpha,
            "beta": args.beta,
            "N_units": args.n_units,
            "L": 5 * args.n_units,
            "q_over_pi": args.q_over_pi,
            "omega_min": args.omega_min,
            "omega_max": args.omega_max,
            "omega_step": args.omega_step,
            "omega_order": args.omega_order,
        },
        "settings": {
            "method": "krylov_correction_vector_dmrg_resumable",
            "boundary": "OBC",
            "sector": "Sz=0",
            "eta": args.eta,
            "dmrg_maxdim": args.dmrg_maxdim,
            "cv_maxdim": args.cv_maxdim,
            "nsweeps": args.nsweeps,
            "dmrg_cutoff": args.cutoff,
            "cv_cutoff": args.cv_cutoff,
            "threads": args.threads,
            "momentum_normalization": "1/sqrt(L)",
            "checkpoint_mode": "atomic_latest_solution_and_unique_frequency_files",
            "solve_order": args.omega_order,
        },
        "observables": {
            "energy": metrics.get("energy"),
            "source_norm_squared": metrics.get("source_norm_squared"),
            "source_maxdim": metrics.get("source_maxdim"),
        },
        "diagnostics": {
            "variance_per_site": metrics.get("variance_per_site"),
            "total_sz": metrics.get("total_sz"),
            "dmrg_actual_maxdim": metrics.get("dmrg_actual_maxdim"),
            "max_dmrg_truncation": metrics.get("max_dmrg_truncation"),
            "final_dmrg_energy_delta": metrics.get("final_dmrg_energy_delta"),
            "max_cv_relative_residual": metrics.get("max_cv_residual"),
            "max_solution_dim": metrics.get("max_solution_dim"),
            "dmrg_seconds": metrics.get("dmrg_seconds"),
            "cv_seconds": metrics.get("cv_seconds"),
            "completed_points": metrics.get("completed_points"),
            "total_points": metrics.get("total_points"),
            "ground_reused_last_attempt": metrics.get("ground_reused"),
            "source_reused_last_attempt": metrics.get("source_reused"),
        },
        "acceptance": {
            "status": "pass" if complete and all(checks.values()) else "pending",
            "checks": checks,
            "budgets": {
                "variance_per_site": 1e-8,
                "max_dmrg_truncation": 1e-8,
                "max_cv_relative_residual": args.max_cv_residual,
                "relative_negative_tolerance": 1e-10,
            },
            "min_intensity": min(intensities) if intensities else None,
        },
        "provenance": {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "julia_version": julia_version,
            "manifest_sha256": manifest_hash,
            "run_config_sha256": sha256(config_path),
            "julia_pkg_offline": True,
            "negative_alpha_excluded": True,
            "code_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in source_files},
        },
        "attempts": attempt,
        "timing": {"last_started_at": started.isoformat(), "last_finished_at": finished.isoformat()},
        "returncode": result.returncode,
    }
    write_json(outdir / "manifest.json", manifest)
    write_json(outdir / "status.json", {
        "status": run_status,
        "accepted": manifest["acceptance"]["status"] == "pass",
        "attempt": attempt,
        "finished_at": finished.isoformat(),
        "returncode": result.returncode,
    })
    progress.finish(
        status=run_status,
        returncode=result.returncode,
        phase="finished",
        completed_points=metrics.get("completed_points"),
        total_points=metrics.get("total_points"),
    )
    files = [
        path for path in outdir.rglob("*")
        if path.is_file() and path.name != "checksums.sha256"
    ]
    atomic_write_text(
        outdir / "checksums.sha256",
        "".join(
            f"{sha256(path)}  {path.relative_to(outdir).as_posix()}\n"
            for path in sorted(files)
        ),
    )
    temporary_files = list(outdir.rglob("*.tmp"))
    if temporary_files:
        raise SystemExit(f"发现未提交的临时文件: {temporary_files}")
    print(json.dumps(manifest, ensure_ascii=False))
    if result.returncode:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
