#!/usr/bin/env python3
"""执行并封装一个正区静态双扇区 DMRG cell。"""

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
from datetime import datetime, timezone
from pathlib import Path

from progress import ProgressWriter


ROOT = Path(__file__).resolve().parents[2]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_metrics(path: Path) -> dict[str, object]:
    values: dict[str, object] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            value = row["value"]
            try:
                values[row["metric"]] = float(value)
            except ValueError:
                values[row["metric"]] = value
    return values


def peak_rss(path: Path) -> int | None:
    if not path.exists():
        return None
    match = re.search(r"Maximum resident set size \(kbytes\):\s*(\d+)", path.read_text(errors="replace"))
    return int(match.group(1)) if match else None


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_julia(value: str) -> str:
    if value != "auto":
        return value
    server = Path.home() / ".juliaup" / "bin" / "julia"
    if server.exists():
        return str(server)
    local = shutil.which("julia")
    if local:
        return local
    raise SystemExit("找不到 Julia")


def progress_probe(outdir: Path) -> dict[str, object]:
    result: dict[str, object] = {}
    stdout = outdir / "stdout.log"
    if stdout.is_file():
        text = stdout.read_text(encoding="utf-8", errors="replace")
        matches = re.findall(r"After sweep\s+(\d+)", text)
        if matches:
            result["last_sweep"] = int(matches[-1])
        stat = stdout.stat()
        result["stdout_bytes"] = stat.st_size
        result["stdout_last_change"] = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cell-id", required=True)
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--path-id", required=True)
    parser.add_argument("--group", type=int, required=True)
    parser.add_argument("--role", choices=("left", "ridge", "right"), required=True)
    parser.add_argument("--alpha", type=float, required=True)
    parser.add_argument("--beta", type=float, required=True)
    parser.add_argument("--n-units", type=int, required=True)
    parser.add_argument("--maxdim", type=int, required=True)
    parser.add_argument("--nsweeps", type=int, required=True)
    parser.add_argument("--cutoff", type=float, required=True)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--init-mode", choices=("center", "domain"), default="center")
    parser.add_argument("--string-margin", type=int, default=3)
    parser.add_argument("--schmidt-levels", type=int, default=16)
    parser.add_argument("--save-state", action="store_true")
    parser.add_argument("--source-commit", default="unknown")
    parser.add_argument("--standard-sha256", required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--expected-julia-version", required=True)
    parser.add_argument("--julia", default="auto")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not 0.0 <= args.alpha <= 1.0:
        raise SystemExit("禁止 alpha<0 或 alpha>1")
    if not 0.0 <= args.beta <= 1.0:
        raise SystemExit("beta 必须位于 [0,1]")
    if args.n_units <= 0 or args.n_units % 2:
        raise SystemExit("N_UNITS 必须为正偶数")
    if not 1 <= args.threads <= 16:
        raise SystemExit("线程数必须位于 [1,16]")

    outdir = Path(args.outdir).resolve()
    try:
        outdir.relative_to((ROOT / "results").resolve())
    except ValueError as error:
        raise SystemExit(f"输出目录不在 results 下: {outdir}") from error
    if outdir.exists() and any(outdir.iterdir()):
        raise SystemExit(f"拒绝覆盖已有 cell: {outdir}")

    manifest_hash = sha256(ROOT / "Manifest.toml")
    if manifest_hash != args.expected_manifest_sha256:
        raise SystemExit("Manifest SHA-256 不匹配")
    julia = resolve_julia(args.julia)
    version_command = [julia, "+release", "--startup-file=no", "--version"]
    if Path(julia).name.lower().startswith("julia") and ".juliaup" not in julia.replace("\\", "/"):
        version_command = [julia, "--startup-file=no", "--version"]
    version_result = subprocess.run(version_command, cwd=ROOT, capture_output=True, text=True, check=False)
    julia_version = version_result.stdout.strip().removeprefix("julia version ")
    if version_result.returncode or julia_version != args.expected_julia_version:
        raise SystemExit(f"Julia 版本不匹配: {julia_version or version_result.stderr.strip()}")

    julia_command = [julia]
    if ".juliaup" in julia.replace("\\", "/"):
        julia_command.append("+release")
    julia_command.extend([
        f"--threads={args.threads}",
        "--project=.",
        "scripts/autoresearch_v5/positive_static_cell.jl",
        str(outdir),
        str(args.alpha),
        str(args.beta),
        str(args.n_units),
        str(args.maxdim),
        str(args.nsweeps),
        str(args.cutoff),
        args.init_mode,
        str(args.string_margin),
        str(args.schmidt_levels),
        "1" if args.save_state else "0",
    ])
    resource_log = outdir / "resource.log"
    time_binary = Path("/usr/bin/time")
    command = (
        [str(time_binary), "-v", "-o", str(resource_log), *julia_command]
        if time_binary.exists()
        else julia_command
    )
    if args.dry_run:
        print(json.dumps({"cell_id": args.cell_id, "command": command}, ensure_ascii=False))
        return

    outdir.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    write_json(outdir / "status.json", {"status": "running", "started_at": started.isoformat()})
    progress = ProgressWriter(
        outdir,
        {
            "job_type": "positive_static_cell",
            "cell_id": args.cell_id,
            "phase": "dmrg_two_sectors",
            "requested_sweeps": args.nsweeps,
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
    })
    with (outdir / "stdout.log").open("w", encoding="utf-8") as stdout, (
        outdir / "stderr.log"
    ).open("w", encoding="utf-8") as stderr:
        result = subprocess.run(command, cwd=ROOT, env=environment, stdout=stdout, stderr=stderr, check=False)

    metrics_path = outdir / "metrics.csv"
    values = read_metrics(metrics_path) if metrics_path.exists() else {}
    finished = datetime.now(timezone.utc)
    finite_keys = (
        "energy_sz0", "energy_sz1", "spin_gap", "variance_per_site_sz0",
        "variance_per_site_sz1", "max_truncation_error_sz0", "max_truncation_error_sz1",
        "final_truncation_error_sz0", "final_truncation_error_sz1",
        "structure_factor_ratio",
    )
    finite_metrics = bool(values) and all(
        key in values and isinstance(values[key], float) and math.isfinite(values[key]) for key in finite_keys
    )
    acceptance = {
        "execution_success": result.returncode == 0 and finite_metrics,
        "variance_sz0_per_site_le_1e-8": float(values.get("variance_per_site_sz0", math.inf)) <= 1e-8,
        "variance_sz1_per_site_le_1e-8": float(values.get("variance_per_site_sz1", math.inf)) <= 1e-8,
        "truncation_sz0_le_1e-9": float(values.get("final_truncation_error_sz0", math.inf)) <= 1e-9,
        "truncation_sz1_le_1e-9": float(values.get("final_truncation_error_sz1", math.inf)) <= 1e-9,
        "sz0_sector": abs(float(values.get("total_sz0", math.inf))) <= 1e-8,
        "sz1_sector": abs(float(values.get("total_sz1", math.inf)) - 1.0) <= 1e-8,
        "nonnegative_gap": float(values.get("spin_gap", -math.inf)) >= -1e-8,
        "all_sweeps_completed": (
            int(values.get("nsweeps_completed_sz0", -1)) == args.nsweeps
            and int(values.get("nsweeps_completed_sz1", -1)) == args.nsweeps
        ),
        "measurement_files": all(
            (outdir / name).is_file()
            for name in (
                "string_profile.csv",
                "bond_correlations.csv",
                "schmidt_spectrum.csv",
                "structure_factor.csv",
            )
        ),
    }
    accepted = all(acceptance.values())
    source_files = [
        ROOT / "Project.toml",
        ROOT / "Manifest.toml",
        ROOT / "src" / "hamiltonian.jl",
        ROOT / "src" / "order_parameters.jl",
        ROOT / "scripts" / "autoresearch_v5" / "positive_static_cell.jl",
        ROOT / "scripts" / "autoresearch_v5" / "run_positive_static_cell.py",
        ROOT / "scripts" / "autoresearch_v5" / "progress.py",
    ]
    manifest = {
        "schema_version": 1,
        "cell_id": args.cell_id,
        "status": "success" if result.returncode == 0 and finite_metrics else "failed",
        "accepted": accepted,
        "params": {
            "path_id": args.path_id,
            "group": args.group,
            "role": args.role,
            "alpha": args.alpha,
            "beta": args.beta,
            "L": 5 * args.n_units,
            "n_units": args.n_units,
        },
        "settings": {
            "method": "finite_dmrg",
            "boundary": "OBC",
            "sectors": ["Sz=0", "Sz=1"],
            "maxdim": args.maxdim,
            "nsweeps": args.nsweeps,
            "cutoff": args.cutoff,
            "threads": args.threads,
            "init_mode_sz0": args.init_mode,
            "init_mode_sz1": "center",
            "string_margin": args.string_margin,
            "schmidt_levels": args.schmidt_levels,
            "save_state": args.save_state,
        },
        "observables": {
            "energy_sz0": values.get("energy_sz0"),
            "energy_sz1": values.get("energy_sz1"),
            "spin_gap": values.get("spin_gap"),
            "structure_factor_ratio": values.get("structure_factor_ratio"),
            "structure_factor_pi": values.get("structure_factor_pi"),
            "structure_factor_q1": values.get("structure_factor_q1"),
            "structure_factor_window_sites": values.get("structure_factor_window_sites"),
        },
        "diagnostics": {
            "variance_per_site_sz0": values.get("variance_per_site_sz0"),
            "variance_per_site_sz1": values.get("variance_per_site_sz1"),
            "actual_maxdim_sz0": values.get("actual_maxdim_sz0"),
            "actual_maxdim_sz1": values.get("actual_maxdim_sz1"),
            "max_truncation_error_sz0": values.get("max_truncation_error_sz0"),
            "max_truncation_error_sz1": values.get("max_truncation_error_sz1"),
            "final_truncation_error_sz0": values.get("final_truncation_error_sz0"),
            "final_truncation_error_sz1": values.get("final_truncation_error_sz1"),
            "total_sz0": values.get("total_sz0"),
            "total_sz1": values.get("total_sz1"),
            "peak_rss_kb": peak_rss(resource_log),
            "algorithm_seconds_sz0": values.get("algorithm_seconds_sz0"),
            "algorithm_seconds_sz1": values.get("algorithm_seconds_sz1"),
            "measurement_seconds": values.get("measurement_seconds"),
        },
        "acceptance": acceptance,
        "provenance": {
            "source_commit": args.source_commit,
            "standard_sha256": args.standard_sha256,
            "manifest_sha256": manifest_hash,
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "julia_version": julia_version,
            "julia_pkg_offline": True,
            "negative_alpha_excluded": True,
            "code_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in source_files},
        },
        "timing": {"started_at": started.isoformat(), "finished_at": finished.isoformat()},
        "returncode": result.returncode,
    }
    write_json(outdir / "manifest.json", manifest)
    write_json(
        outdir / "status.json",
        {
            "status": manifest["status"],
            "accepted": accepted,
            "started_at": started.isoformat(),
            "finished_at": finished.isoformat(),
            "returncode": result.returncode,
        },
    )
    progress.finish(status=manifest["status"], returncode=result.returncode, phase="finished", accepted=accepted)
    files = sorted(path for path in outdir.iterdir() if path.is_file() and path.name != "checksums.sha256")
    (outdir / "checksums.sha256").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in files), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False))
    if result.returncode:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
