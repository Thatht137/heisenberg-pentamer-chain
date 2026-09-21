#!/usr/bin/env python3
"""在直连服务器运行并封装一个 CV-DSF cell。"""

from __future__ import annotations

import argparse
import atexit
import csv
import hashlib
import json
import os
import platform
import re
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from progress import ProgressWriter


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_MANIFEST_SHA256 = "37a53ffd73db57b9db9c4ce11f6265a9a41ac2035dc421b01f9a633d893ba12c"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_metrics(path: Path) -> dict[str, object]:
    values: dict[str, object] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                values[row["metric"]] = float(row["value"])
            except ValueError:
                values[row["metric"]] = row["value"]
    return values


def read_intensities(path: Path) -> list[float]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [float(row["intensity"]) for row in csv.DictReader(handle)]


def progress_probe(outdir: Path) -> dict[str, object]:
    stdout = outdir / "stdout.log"
    result: dict[str, object] = {"completed_points": 0}
    if stdout.is_file():
        text = stdout.read_text(encoding="utf-8", errors="replace")
        matches = re.findall(r"omega\s+[-+0-9.eE]+\s+\((\d+)/(\d+)\)", text)
        if matches:
            current, total = matches[-1]
            result.update(completed_points=int(current), total_points=int(total))
        stat = stdout.stat()
        result["stdout_bytes"] = stat.st_size
        result["stdout_last_change"] = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
    return result


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
    parser.add_argument("--dmrg-maxdim", type=int, required=True)
    parser.add_argument("--cv-maxdim", type=int, required=True)
    parser.add_argument("--nsweeps", type=int, required=True)
    parser.add_argument("--cutoff", type=float, required=True)
    parser.add_argument("--cv-cutoff", type=float)
    parser.add_argument("--max-cv-residual", type=float, default=1e-5)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--expected-julia-version", default="1.12.3")
    args = parser.parse_args()
    if not 0.0 <= args.alpha <= 1.0:
        raise SystemExit("alpha 必须位于 [0,1]")
    if not 0.0 <= args.beta <= 1.0:
        raise SystemExit("beta 必须位于 [0,1]")
    if not 1 <= args.threads <= 16:
        raise SystemExit("线程数必须位于 [1,16]")
    cv_cutoff = args.cv_cutoff if args.cv_cutoff is not None else args.cutoff
    if args.cutoff <= 0 or cv_cutoff <= 0 or args.max_cv_residual <= 0:
        raise SystemExit("截断阈值和残差门槛必须为正数")

    outdir = Path(args.outdir).resolve()
    outdir.relative_to((ROOT / "results").resolve())
    if outdir.exists() and any(outdir.iterdir()):
        raise SystemExit(f"拒绝覆盖已有 cell: {outdir}")
    manifest_hash = sha256(ROOT / "Manifest.toml")
    if manifest_hash != EXPECTED_MANIFEST_SHA256:
        raise SystemExit(
            f"Manifest SHA-256 不匹配: path={ROOT / 'Manifest.toml'} "
            f"actual={manifest_hash} expected={EXPECTED_MANIFEST_SHA256}"
        )

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

    outdir.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    write_json(outdir / "status.json", {"status": "running", "started_at": started.isoformat()})
    total_points = int(round((args.omega_max - args.omega_min) / args.omega_step)) + 1
    progress = ProgressWriter(
        outdir,
        {
            "job_type": "cv_dsf_cell",
            "cell_id": args.cell_id,
            "phase": "julia_linsolve",
            "total_points": total_points,
        },
        probe=lambda: progress_probe(outdir),
    )
    progress.start()
    atexit.register(lambda: progress.finish(status="aborted", returncode=1))
    command = [
        "/usr/bin/time", "-v", "-o", str(outdir / "resource.log"),
        "nice", "-n", "10", str(julia), "+release", f"--threads={args.threads}",
        "--startup-file=no", "--project=.", "scripts/autoresearch_v5/cv_dsf_cell.jl",
        str(outdir), str(args.alpha), str(args.beta), str(args.n_units),
        str(args.q_over_pi), str(args.eta), str(args.omega_min), str(args.omega_max),
        str(args.omega_step), str(args.dmrg_maxdim), str(args.cv_maxdim),
        str(args.nsweeps), str(args.cutoff), str(cv_cutoff),
    ]
    environment = os.environ.copy()
    environment.update({
        "JULIA_PKG_OFFLINE": "true",
        "JULIA_PKG_SERVER": "",
        "HTTP_PROXY": "http://127.0.0.1:9",
        "HTTPS_PROXY": "http://127.0.0.1:9",
    })
    with (outdir / "stdout.log").open("w", encoding="utf-8") as stdout, \
            (outdir / "stderr.log").open("w", encoding="utf-8") as stderr:
        result = subprocess.run(
            command, cwd=ROOT, env=environment, stdout=stdout, stderr=stderr, check=False
        )
    metrics = read_metrics(outdir / "metrics.csv") if (outdir / "metrics.csv").is_file() else {}
    intensities = (
        read_intensities(outdir / "spectrum.csv")
        if (outdir / "spectrum.csv").is_file()
        else []
    )
    variance = metrics.get("variance_per_site")
    residual = metrics.get("max_cv_residual")
    truncation = metrics.get("max_dmrg_truncation")
    acceptance_checks = {
        "ground_variance": isinstance(variance, float) and variance <= 1e-8,
        "dmrg_truncation": isinstance(truncation, float) and truncation <= 1e-8,
        "cv_residual": isinstance(residual, float) and residual <= args.max_cv_residual,
        "nonnegative": bool(intensities) and min(intensities) >= -1e-10 * max(intensities),
    }
    finished = datetime.now(timezone.utc)
    source_files = [
        ROOT / "Project.toml",
        ROOT / "Manifest.toml",
        ROOT / "src" / "PentamerChain.jl",
        ROOT / "src" / "hamiltonian.jl",
        ROOT / "scripts" / "autoresearch_v5" / "cv_dsf_cell.jl",
        ROOT / "scripts" / "autoresearch_v5" / "run_cv_dsf_cell.py",
        ROOT / "scripts" / "autoresearch_v5" / "progress.py",
    ]
    manifest = {
        "schema_version": 1,
        "cell_id": args.cell_id,
        "status": "success" if result.returncode == 0 and metrics else "failed",
        "params": {
            "alpha": args.alpha,
            "beta": args.beta,
            "N_units": args.n_units,
            "L": 5 * args.n_units,
            "q_over_pi": args.q_over_pi,
            "omega_min": args.omega_min,
            "omega_max": args.omega_max,
            "omega_step": args.omega_step,
        },
        "settings": {
            "method": "krylov_correction_vector_dmrg",
            "boundary": "OBC",
            "sector": "Sz=0",
            "eta": args.eta,
            "dmrg_maxdim": args.dmrg_maxdim,
            "cv_maxdim": args.cv_maxdim,
            "nsweeps": args.nsweeps,
            "dmrg_cutoff": args.cutoff,
            "cv_cutoff": cv_cutoff,
            "threads": args.threads,
            "momentum_normalization": "1/sqrt(L)",
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
        },
        "acceptance": {
            "status": "pass" if all(acceptance_checks.values()) else "fail",
            "checks": acceptance_checks,
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
            "julia_pkg_offline": True,
            "negative_alpha_excluded": True,
            "code_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in source_files},
        },
        "timing": {"started_at": started.isoformat(), "finished_at": finished.isoformat()},
        "returncode": result.returncode,
    }
    write_json(outdir / "manifest.json", manifest)
    write_json(outdir / "status.json", {
        "status": manifest["status"],
        "accepted": manifest["acceptance"]["status"] == "pass",
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "returncode": result.returncode,
    })
    progress.finish(status=manifest["status"], returncode=result.returncode, phase="finished")
    files = [path for path in outdir.iterdir() if path.is_file() and path.name != "checksums.sha256"]
    (outdir / "checksums.sha256").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in sorted(files)), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False))
    if result.returncode:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
