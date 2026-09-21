#!/usr/bin/env python3
"""在直连服务器上安全执行一个 DMRG cell。"""

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
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "autoresearch_v5"))
from progress import ProgressWriter


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_metrics(path: Path) -> dict[str, object]:
    metrics: dict[str, object] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            key = row["metric"]
            value = row["value"]
            try:
                number = float(value)
                metrics[key] = int(number) if number.is_integer() and key in {
                    "n_units",
                    "L",
                    "requested_maxdim",
                    "actual_maxdim",
                    "nsweeps_requested",
                    "nsweeps_completed",
                    "threads",
                } else number
            except ValueError:
                metrics[key] = value
    return metrics


def parse_peak_rss(path: Path) -> int | None:
    if not path.exists():
        return None
    match = re.search(r"Maximum resident set size \(kbytes\):\s*(\d+)", path.read_text(errors="replace"))
    return int(match.group(1)) if match else None


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def progress_probe(outdir: Path) -> dict[str, object]:
    stdout = outdir / "stdout.log"
    result: dict[str, object] = {}
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
    parser.add_argument("--alpha", required=True, type=float)
    parser.add_argument("--beta", required=True, type=float)
    parser.add_argument("--n-units", required=True, type=int)
    parser.add_argument("--maxdim", required=True, type=int)
    parser.add_argument("--nsweeps", required=True, type=int)
    parser.add_argument("--cutoff", default=1e-10, type=float)
    parser.add_argument("--init-mode", default="neel", choices=("neel", "shifted"))
    parser.add_argument("--threads", default=8, type=int)
    parser.add_argument("--save-mps", action="store_true")
    parser.add_argument("--source-commit", default="unknown")
    parser.add_argument("--standard-sha256", required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--expected-julia-version", default="1.12.3")
    args = parser.parse_args()

    if not 0.0 <= args.alpha <= 1.0:
        raise SystemExit("禁止 alpha<0 或 alpha>1")
    if not 0.0 <= args.beta <= 1.0:
        raise SystemExit("beta 必须位于 [0,1]")
    if not 1 <= args.threads <= 16:
        raise SystemExit("线程数必须位于 [1,16]")

    outdir = Path(args.outdir).resolve()
    allowed_root = (ROOT / "results").resolve()
    try:
        outdir.relative_to(allowed_root)
    except ValueError as error:
        raise SystemExit(f"输出目录不在 results 下: {outdir}") from error
    if outdir.exists() and any(outdir.iterdir()):
        raise SystemExit(f"拒绝覆盖已有 cell: {outdir}")
    outdir.mkdir(parents=True, exist_ok=True)

    manifest_source = ROOT / "Manifest.toml"
    manifest_sha256 = sha256(manifest_source)
    if manifest_sha256 != args.expected_manifest_sha256:
        raise SystemExit(
            f"Manifest 哈希不匹配: {manifest_sha256} != {args.expected_manifest_sha256}"
        )

    started = datetime.now(timezone.utc)
    status_path = outdir / "status.json"
    write_json(status_path, {"status": "running", "started_at": started.isoformat()})
    progress = ProgressWriter(
        outdir,
        {"job_type": "five_rounds_dmrg", "cell_id": args.cell_id, "phase": "dmrg", "requested_sweeps": args.nsweeps},
        probe=lambda: progress_probe(outdir),
    )
    progress.start()
    atexit.register(lambda: progress.finish(status="aborted", returncode=1))

    julia = Path.home() / ".juliaup" / "bin" / "julia"
    julia_version_result = subprocess.run(
        [str(julia), "+release", "--startup-file=no", "--version"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    julia_version = julia_version_result.stdout.strip().removeprefix("julia version ")
    if julia_version_result.returncode != 0 or julia_version != args.expected_julia_version:
        raise SystemExit(
            f"Julia 版本不匹配: {julia_version or julia_version_result.stderr.strip()}"
        )
    resource_log = outdir / "resource.log"
    command = [
        "/usr/bin/time",
        "-v",
        "-o",
        str(resource_log),
        str(julia),
        "+release",
        f"--threads={args.threads}",
        "--project=.",
        "scripts/five_rounds/dmrg_cell.jl",
        str(outdir),
        str(args.alpha),
        str(args.beta),
        str(args.n_units),
        str(args.maxdim),
        str(args.nsweeps),
        str(args.cutoff),
        args.init_mode,
        "1" if args.save_mps else "0",
    ]
    environment = os.environ.copy()
    environment.update(
        {
            "JULIA_PKG_OFFLINE": "true",
            "JULIA_PKG_SERVER": "",
            "HTTPS_PROXY": "http://127.0.0.1:9",
            "HTTP_PROXY": "http://127.0.0.1:9",
        }
    )
    with (outdir / "stdout.log").open("w", encoding="utf-8") as stdout, (
        outdir / "stderr.log"
    ).open("w", encoding="utf-8") as stderr:
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=environment,
            stdout=stdout,
            stderr=stderr,
            check=False,
        )

    metrics_path = outdir / "metrics.csv"
    metrics = load_metrics(metrics_path) if metrics_path.exists() else {}
    finished = datetime.now(timezone.utc)
    code_files = [
        ROOT / "Project.toml",
        ROOT / "Manifest.toml",
        ROOT / "src" / "hamiltonian.jl",
        ROOT / "src" / "dmrg_solver.jl",
        ROOT / "src" / "order_parameters.jl",
        ROOT / "scripts" / "five_rounds" / "dmrg_cell.jl",
        ROOT / "scripts" / "five_rounds" / "run_dmrg_cell.py",
        ROOT / "scripts" / "autoresearch_v5" / "progress.py",
    ]
    manifest = {
        "schema_version": 1,
        "cell_id": args.cell_id,
        "status": "success" if result.returncode == 0 and metrics else "failed",
        "params": {
            "alpha": args.alpha,
            "beta": args.beta,
            "L": 5 * args.n_units,
            "n_units": args.n_units,
            "maxdim": args.maxdim,
        },
        "settings": {
            "method": "finite_dmrg",
            "boundary": "OBC",
            "sector": "Sz=0",
            "cutoff": args.cutoff,
            "nsweeps": args.nsweeps,
            "init_mode": args.init_mode,
            "threads": args.threads,
            "save_mps": args.save_mps,
        },
        "observables": {
            "energy": metrics.get("energy"),
            "energy_density": metrics.get("energy_density"),
            "variance_per_site": metrics.get("variance_per_site"),
            "string_order": metrics.get("string_order"),
            "center_entropy": metrics.get("center_entropy"),
            "total_sz": metrics.get("total_sz"),
        },
        "diagnostics": {
            "actual_maxdim": metrics.get("actual_maxdim"),
            "max_truncation_error": metrics.get("max_truncation_error"),
            "final_energy_change": metrics.get("final_energy_change"),
            "nsweeps_completed": metrics.get("nsweeps_completed"),
            "peak_rss_kb": parse_peak_rss(resource_log),
            "algorithm_seconds": metrics.get("algorithm_seconds"),
            "measurement_seconds": metrics.get("measurement_seconds"),
        },
        "provenance": {
            "source_commit": args.source_commit,
            "standard_sha256": args.standard_sha256,
            "manifest_sha256": manifest_sha256,
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "julia_channel": "release",
            "julia_version": julia_version,
            "julia_pkg_offline": True,
            "negative_alpha_excluded": True,
            "code_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in code_files},
        },
        "timing": {"started_at": started.isoformat(), "finished_at": finished.isoformat()},
        "returncode": result.returncode,
    }
    write_json(outdir / "manifest.json", manifest)
    write_json(
        status_path,
        {
            "status": manifest["status"],
            "started_at": started.isoformat(),
            "finished_at": finished.isoformat(),
            "returncode": result.returncode,
        },
    )
    progress.finish(status=manifest["status"], returncode=result.returncode, phase="finished")
    outputs = [path for path in outdir.iterdir() if path.is_file() and path.name != "checksums.sha256"]
    (outdir / "checksums.sha256").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in sorted(outputs)),
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
