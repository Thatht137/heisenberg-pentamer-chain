#!/usr/bin/env python3
"""执行并封装一个负 alpha 静态双扇区 DMRG cell。"""

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
from negative_dmrg_options import (
    EIGSOLVE_KRYLOVDIM_DEFAULT,
    EIGSOLVE_MAXITER,
    EIGSOLVE_TOL,
    parse_krylovdim_arg,
    validate_krylovdim,
)


ROOT = Path(__file__).resolve().parents[2]
JULIA_CELL = ROOT / "scripts" / "autoresearch_v5" / "negative_static_cell.jl"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_metrics(path: Path) -> dict[str, object]:
    values: dict[str, object] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                values[row["metric"]] = float(row["value"])
            except ValueError:
                values[row["metric"]] = row["value"]
    return values


def resolve_julia(value: str) -> str:
    if value != "auto":
        return value
    server = Path.home() / ".juliaup" / "bin" / "julia"
    local = shutil.which("julia")
    if server.exists():
        return str(server)
    if local:
        return local
    raise SystemExit("找不到 Julia")


def peak_rss(path: Path) -> int | None:
    if not path.exists():
        return None
    match = re.search(r"Maximum resident set size \(kbytes\):\s*(\d+)", path.read_text(errors="replace"))
    return int(match.group(1)) if match else None


def progress_probe(outdir: Path) -> dict[str, object]:
    stdout = outdir / "stdout.log"
    if not stdout.is_file():
        return {}
    text = stdout.read_text(encoding="utf-8", errors="replace")
    sweeps = re.findall(r"After sweep\s+(\d+)", text)
    return {"last_sweep": int(sweeps[-1]) if sweeps else None, "stdout_bytes": stdout.stat().st_size}


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
    parser.add_argument("--init-mode", choices=("center", "center_random", "domain", "ferro_j2"), default="center")
    parser.add_argument("--noise-profile", choices=("legacy", "repair"), default="legacy")
    parser.add_argument("--random-seed", type=int, default=20260811)
    parser.add_argument("--energy-change-max", type=float)
    parser.add_argument("--variance-max", type=float, default=1e-8)
    parser.add_argument("--string-margin", type=int, default=3)
    parser.add_argument("--schmidt-levels", type=int, default=16)
    parser.add_argument("--q-count", type=int, default=401)
    parser.add_argument("--save-state", action="store_true")
    parser.add_argument("--enriched-diagnostics", action="store_true")
    parser.add_argument("--source-commit", default="unknown")
    parser.add_argument("--standard-sha256", required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--expected-julia-version", required=True)
    parser.add_argument("--julia", default="auto")
    parser.add_argument("--eigsolve-krylovdim", type=parse_krylovdim_arg, default=EIGSOLVE_KRYLOVDIM_DEFAULT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    args.eigsolve_krylovdim = validate_krylovdim(args.eigsolve_krylovdim)

    if not -1.0 <= args.alpha < 0.0:
        raise SystemExit("alpha 必须位于 [-1,0)")
    if not 0.0 <= args.beta <= 1.0:
        raise SystemExit("beta 必须位于 [0,1]")
    if args.n_units <= 0 or args.n_units % 2:
        raise SystemExit("N_UNITS 必须为正偶数")
    if not 1 <= args.threads <= 16 or args.q_count < 401:
        raise SystemExit("线程必须为 [1,16]，Q_COUNT 至少为 401")
    if args.random_seed < 0:
        raise SystemExit("random-seed 必须非负")
    if args.energy_change_max is not None and (not math.isfinite(args.energy_change_max) or args.energy_change_max <= 0):
        raise SystemExit("energy-change-max 必须为有限正数")
    if not math.isfinite(args.variance_max) or args.variance_max <= 0:
        raise SystemExit("variance-max 必须为有限正数")
    outdir = Path(args.outdir).resolve()
    try:
        outdir.relative_to((ROOT / "results").resolve())
    except ValueError as error:
        raise SystemExit(f"输出目录不在 results 下: {outdir}") from error
    if outdir.exists() and any(outdir.iterdir()):
        raise SystemExit(f"拒绝覆盖已有 cell: {outdir}")
    if sha256(ROOT / "Manifest.toml") != args.expected_manifest_sha256:
        raise SystemExit("Manifest SHA-256 不匹配")
    if not JULIA_CELL.is_file():
        raise SystemExit(f"找不到 Julia cell: {JULIA_CELL}")

    julia = resolve_julia(args.julia)
    version_command = [julia, "+release", "--startup-file=no", "--version"]
    if ".juliaup" not in julia.replace("\\", "/"):
        version_command = [julia, "--startup-file=no", "--version"]
    version = subprocess.run(version_command, cwd=ROOT, text=True, capture_output=True, check=False)
    julia_version = version.stdout.strip().removeprefix("julia version ")
    if version.returncode or julia_version != args.expected_julia_version:
        raise SystemExit(f"Julia 版本不匹配: {julia_version or version.stderr.strip()}")
    julia_command = [julia]
    if ".juliaup" in julia.replace("\\", "/"):
        julia_command.append("+release")
    julia_command.extend([
        f"--threads={args.threads}", "--project=.", str(JULIA_CELL), str(outdir), str(args.alpha), str(args.beta),
        str(args.n_units), str(args.maxdim), str(args.nsweeps), str(args.cutoff), args.init_mode,
        str(args.string_margin), str(args.schmidt_levels), str(args.q_count), "1" if args.save_state else "0",
        args.noise_profile, str(args.random_seed),
        "1" if args.enriched_diagnostics else "0",
        str(args.eigsolve_krylovdim),
    ])
    resource_log = outdir / "resource.log"
    command = ["/usr/bin/time", "-v", "-o", str(resource_log), *julia_command] if Path("/usr/bin/time").exists() else julia_command
    if args.dry_run:
        print(json.dumps({"cell_id": args.cell_id, "command": command}, ensure_ascii=False))
        return

    outdir.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    write_json(outdir / "status.json", {"status": "running", "started_at": started.isoformat()})
    progress = ProgressWriter(outdir, {"job_type": "negative_static_cell", "cell_id": args.cell_id, "phase": "dmrg_two_sectors", "requested_sweeps": args.nsweeps, "eigsolve_krylovdim": args.eigsolve_krylovdim, "eigsolve_maxiter": EIGSOLVE_MAXITER, "eigsolve_tol": EIGSOLVE_TOL}, probe=lambda: progress_probe(outdir))
    progress.start()
    atexit.register(lambda: progress.finish(status="aborted", returncode=1))
    environment = os.environ.copy()
    environment.update({"JULIA_PKG_OFFLINE": "true", "JULIA_PKG_SERVER": "", "HTTP_PROXY": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9"})
    with (outdir / "stdout.log").open("w", encoding="utf-8") as stdout, (outdir / "stderr.log").open("w", encoding="utf-8") as stderr:
        result = subprocess.run(command, cwd=ROOT, env=environment, stdout=stdout, stderr=stderr, check=False)
    values = read_metrics(outdir / "metrics.csv") if (outdir / "metrics.csv").is_file() else {}
    finite_keys = ("energy_sz0", "energy_sz1", "spin_gap", "variance_per_site_sz0", "variance_per_site_sz1", "final_truncation_error_sz0", "final_truncation_error_sz1", "final_energy_change_sz0", "final_energy_change_sz1", "structure_factor_ratio", "structure_factor_peak_q_over_pi", "structure_factor_peak", "dominant_structure_factor_ratio")
    finite = bool(values) and all(isinstance(values.get(key), float) and math.isfinite(float(values[key])) for key in finite_keys)
    variance_label = f"{args.variance_max:.0e}"
    acceptance = {
        "execution_success": result.returncode == 0 and finite,
        f"variance_sz0_per_site_le_{variance_label}": float(values.get("variance_per_site_sz0", math.inf)) <= args.variance_max,
        f"variance_sz1_per_site_le_{variance_label}": float(values.get("variance_per_site_sz1", math.inf)) <= args.variance_max,
        "truncation_sz0_le_1e-9": float(values.get("final_truncation_error_sz0", math.inf)) <= 1e-9,
        "truncation_sz1_le_1e-9": float(values.get("final_truncation_error_sz1", math.inf)) <= 1e-9,
        "sz0_sector": abs(float(values.get("total_sz0", math.inf))) <= 1e-8,
        "sz1_sector": abs(float(values.get("total_sz1", math.inf)) - 1.0) <= 1e-8,
        "nonnegative_gap": float(values.get("spin_gap", -math.inf)) >= -1e-8,
        "all_sweeps_completed": int(values.get("nsweeps_completed_sz0", -1)) == args.nsweeps and int(values.get("nsweeps_completed_sz1", -1)) == args.nsweeps,
        "fullq_file": (outdir / "structure_factor_fullq.csv").is_file(),
        "fullq_count": int(values.get("structure_factor_q_count", 0)) >= args.q_count,
        "measurement_files": all((outdir / name).is_file() for name in ("string_profile.csv", "bond_correlations.csv", "schmidt_spectrum.csv")),
    }
    if args.save_state:
        acceptance["state_saved"] = (outdir / "state_sz0.jld2").is_file()
    if args.enriched_diagnostics:
        acceptance["enriched_measurement_files"] = all(
            (outdir / name).is_file() for name in ("entropy_profile_full.csv", "bond_bond_connected.csv")
        )
    if args.energy_change_max is not None:
        acceptance.update({
            "energy_plateau_sz0": float(values.get("final_energy_change_sz0", math.inf)) <= args.energy_change_max,
            "energy_plateau_sz1": float(values.get("final_energy_change_sz1", math.inf)) <= args.energy_change_max,
        })
    source_files = [ROOT / "Project.toml", ROOT / "Manifest.toml", ROOT / "src" / "hamiltonian.jl", ROOT / "src" / "order_parameters.jl", JULIA_CELL, Path(__file__).resolve(), ROOT / "scripts" / "autoresearch_v5" / "negative_dmrg_options.py", ROOT / "scripts" / "autoresearch_v5" / "progress.py"]
    finished = datetime.now(timezone.utc)
    manifest = {
        "schema_version": 1, "cell_id": args.cell_id, "status": "success" if result.returncode == 0 and finite else "failed", "accepted": all(acceptance.values()),
        "params": {"path_id": args.path_id, "group": args.group, "role": args.role, "alpha": args.alpha, "beta": args.beta, "L": 5 * args.n_units, "n_units": args.n_units},
        "settings": {"method": "finite_dmrg", "boundary": "OBC", "sectors": ["Sz=0", "Sz=1"], "maxdim": args.maxdim, "nsweeps": args.nsweeps, "cutoff": args.cutoff, "threads": args.threads, "init_mode_sz0": args.init_mode, "init_mode_sz1": "center", "q_count": args.q_count, "noise_profile": args.noise_profile, "random_seed": args.random_seed, "variance_per_site_max": args.variance_max, "save_state": args.save_state, "enriched_diagnostics": args.enriched_diagnostics, "eigsolve_krylovdim": args.eigsolve_krylovdim, "eigsolve_maxiter": EIGSOLVE_MAXITER, "eigsolve_tol": EIGSOLVE_TOL} | ({"energy_change_max": args.energy_change_max} if args.energy_change_max is not None else {}),
        "observables": {key: values.get(key) for key in ("energy_sz0", "energy_sz1", "spin_gap", "structure_factor_ratio", "structure_factor_pi", "structure_factor_q1", "structure_factor_window_sites", "structure_factor_peak_q", "structure_factor_peak_q_over_pi", "structure_factor_peak", "dominant_structure_factor_ratio", "structure_factor_peak_ratio", "dominant_structure_factor_ratio_mode")},
        "diagnostics": {key: values.get(key) for key in ("variance_per_site_sz0", "variance_per_site_sz1", "actual_maxdim_sz0", "actual_maxdim_sz1", "max_truncation_error_sz0", "max_truncation_error_sz1", "final_truncation_error_sz0", "final_truncation_error_sz1", "final_energy_change_sz0", "final_energy_change_sz1", "total_sz0", "total_sz1", "algorithm_seconds_sz0", "algorithm_seconds_sz1", "measurement_seconds", "initial_seed_sz0", "initial_seed_sz1") } | {"peak_rss_kb": peak_rss(resource_log)},
        "acceptance": acceptance,
        "provenance": {"source_commit": args.source_commit, "standard_sha256": args.standard_sha256, "manifest_sha256": sha256(ROOT / "Manifest.toml"), "hostname": socket.gethostname(), "platform": platform.platform(), "python": platform.python_version(), "julia_version": julia_version, "julia_pkg_offline": True, "negative_alpha_included": True, "negative_alpha_bounds": [-1.0, 0.0], "noise_protocol": args.noise_profile, "acceptance_policy": "practical_v2" if args.variance_max != 1e-8 else "strict_v1", "code_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in source_files}},
        "timing": {"started_at": started.isoformat(), "finished_at": finished.isoformat()}, "returncode": result.returncode,
    }
    write_json(outdir / "manifest.json", manifest)
    write_json(outdir / "status.json", {"status": manifest["status"], "accepted": manifest["accepted"], "returncode": result.returncode, "started_at": started.isoformat(), "finished_at": finished.isoformat()})
    progress.finish(status=manifest["status"], returncode=result.returncode, phase="finished", accepted=manifest["accepted"])
    files = sorted(path for path in outdir.iterdir() if path.is_file() and path.name != "checksums.sha256")
    (outdir / "checksums.sha256").write_text("".join(f"{sha256(path)}  {path.name}\n" for path in files), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))
    if result.returncode:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
