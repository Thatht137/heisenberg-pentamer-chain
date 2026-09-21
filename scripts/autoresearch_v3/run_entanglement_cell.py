#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在直连服务器上执行并封装一个纠缠熵 cell。"""

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


def read_metrics(path: Path) -> dict[str, object]:
    values: dict[str, object] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                values[row["metric"]] = float(row["value"])
            except ValueError:
                values[row["metric"]] = row["value"]
    return values


def peak_rss(path: Path) -> int | None:
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
    parser.add_argument("--model", choices=("pentamer", "heisenberg"), required=True)
    parser.add_argument("--alpha", type=float, required=True)
    parser.add_argument("--beta", type=float, required=True)
    parser.add_argument("--n-units", type=int, required=True)
    parser.add_argument("--maxdim", type=int, required=True)
    parser.add_argument("--nsweeps", type=int, required=True)
    parser.add_argument("--cutoff", type=float, required=True)
    parser.add_argument("--threads", type=int, default=16)
    parser.add_argument("--init-mode", choices=("center", "domain"), default="center")
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
    outdir.relative_to((ROOT / "results").resolve())
    if outdir.exists() and any(outdir.iterdir()):
        raise SystemExit(f"拒绝覆盖已有 cell: {outdir}")
    outdir.mkdir(parents=True, exist_ok=True)
    manifest_hash = sha256(ROOT / "Manifest.toml")
    if manifest_hash != args.expected_manifest_sha256:
        raise SystemExit("Manifest SHA-256 不匹配")
    julia = Path.home() / ".juliaup" / "bin" / "julia"
    version_result = subprocess.run(
        [str(julia), "+release", "--startup-file=no", "--version"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    julia_version = version_result.stdout.strip().removeprefix("julia version ")
    if version_result.returncode or julia_version != args.expected_julia_version:
        raise SystemExit(f"Julia 版本不匹配: {julia_version}")

    started = datetime.now(timezone.utc)
    write_json(outdir / "status.json", {"status": "running", "started_at": started.isoformat()})
    progress = ProgressWriter(
        outdir,
        {"job_type": "entanglement_dmrg", "cell_id": args.cell_id, "phase": "dmrg", "requested_sweeps": args.nsweeps},
        probe=lambda: progress_probe(outdir),
    )
    progress.start()
    atexit.register(lambda: progress.finish(status="aborted", returncode=1))
    resource_log = outdir / "resource.log"
    command = [
        "/usr/bin/time", "-v", "-o", str(resource_log), str(julia), "+release",
        f"--threads={args.threads}", "--startup-file=no", "--project=.",
        "scripts/autoresearch_v3/entanglement_cell.jl", str(outdir), args.model,
        str(args.alpha), str(args.beta), str(args.n_units), str(args.maxdim),
        str(args.nsweeps), str(args.cutoff), args.init_mode,
    ]
    environment = os.environ.copy()
    environment.update({
        "JULIA_PKG_OFFLINE": "true",
        "JULIA_PKG_SERVER": "",
        "HTTP_PROXY": "http://127.0.0.1:9",
        "HTTPS_PROXY": "http://127.0.0.1:9",
    })
    with (outdir / "stdout.log").open("w", encoding="utf-8") as stdout, (outdir / "stderr.log").open("w", encoding="utf-8") as stderr:
        result = subprocess.run(command, cwd=ROOT, env=environment, stdout=stdout, stderr=stderr, check=False)
    values = read_metrics(outdir / "metrics.csv") if (outdir / "metrics.csv").is_file() else {}
    finished = datetime.now(timezone.utc)
    source_files = [
        ROOT / "Project.toml", ROOT / "Manifest.toml", ROOT / "src" / "hamiltonian.jl",
        ROOT / "src" / "order_parameters.jl",
        ROOT / "scripts" / "autoresearch_v3" / "entanglement_cell.jl",
        ROOT / "scripts" / "autoresearch_v3" / "run_entanglement_cell.py",
        ROOT / "scripts" / "autoresearch_v5" / "progress.py",
    ]
    manifest = {
        "schema_version": 1,
        "cell_id": args.cell_id,
        "status": "success" if result.returncode == 0 and values else "failed",
        "params": {
            "model": args.model,
            "alpha": args.alpha,
            "beta": args.beta,
            "N_units": args.n_units,
            "L": 5 * args.n_units if args.model == "pentamer" else args.n_units,
            "target_sz": 0,
        },
        "settings": {
            "method": "finite_dmrg",
            "boundary": "OBC",
            "maxdim": args.maxdim,
            "nsweeps": args.nsweeps,
            "cutoff": args.cutoff,
            "threads": args.threads,
            "init_mode": args.init_mode,
            "entropy_log_base": "e",
        },
        "observables": {
            "energy": values.get("energy"),
            "energy_density": values.get("energy_density"),
            "midchain_entropy": values.get("midchain_entropy"),
            "total_sz": values.get("total_sz"),
        },
        "diagnostics": {
            "variance": values.get("variance"),
            "variance_per_site": values.get("variance_per_site"),
            "actual_maxdim": values.get("actual_maxdim"),
            "max_truncation_error": values.get("max_truncation_error"),
            "final_energy_change": values.get("final_energy_change"),
            "peak_rss_kb": peak_rss(resource_log),
            "algorithm_seconds": values.get("algorithm_seconds"),
        },
        "provenance": {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "julia_version": julia_version,
            "manifest_sha256": manifest_hash,
            "negative_alpha_excluded": True,
            "code_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in source_files},
        },
        "timing": {"started_at": started.isoformat(), "finished_at": finished.isoformat()},
        "returncode": result.returncode,
    }
    write_json(outdir / "manifest.json", manifest)
    write_json(outdir / "status.json", {"status": manifest["status"], "started_at": started.isoformat(), "finished_at": finished.isoformat(), "returncode": result.returncode})
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
