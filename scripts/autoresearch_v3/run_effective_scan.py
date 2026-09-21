#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""顺序执行有效理论验证清单并支持成功 cell 续算。"""

from __future__ import annotations

import argparse
import hashlib
import json
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ACTIVE: subprocess.Popen[str] | None = None


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def valid(cell: Path) -> bool:
    status = cell / "status.json"
    checksums = cell / "checksums.sha256"
    if not status.is_file() or not checksums.is_file():
        return False
    if json.loads(status.read_text(encoding="utf-8")).get("status") != "success":
        return False
    for line in checksums.read_text(encoding="utf-8").splitlines():
        expected, name = line.split("  ", 1)
        if not (cell / name).is_file() or sha256(cell / name) != expected:
            return False
    return True


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def stop(signum: int, _frame: object) -> None:
    if ACTIVE is not None and ACTIVE.poll() is None:
        ACTIVE.send_signal(signum)
    raise SystemExit(128 + signum)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-spec", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    spec = json.loads(Path(args.run_spec).read_text(encoding="utf-8"))
    run_dir = (ROOT / spec["run_dir"]).resolve()
    run_dir.relative_to((ROOT / "results").resolve())
    settings = spec["settings"]
    cells_dir = run_dir / "cells"
    if not args.dry_run:
        cells_dir.mkdir(parents=True, exist_ok=True)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    completed: list[str] = []
    for cell in spec["cells"]:
        cell_dir = cells_dir / cell["cell_id"]
        if valid(cell_dir):
            completed.append(cell["cell_id"])
            continue
        if cell_dir.exists() and any(cell_dir.iterdir()):
            raise SystemExit(f"拒绝覆盖未通过校验的 cell: {cell_dir}")
        command = [
            "nice", "-n", "10", sys.executable,
            "scripts/autoresearch_v3/run_effective_sector_cell.py",
            "--cell-id", cell["cell_id"], "--outdir", str(cell_dir),
            "--alpha", str(cell["alpha"]), "--beta", str(cell["beta"]),
            "--n-units", str(cell["N_units"]), "--target-sz", str(cell["target_sz"]),
            "--maxdim", str(settings["maxdim"]), "--nsweeps", str(settings["nsweeps"]),
            "--cutoff", str(settings["cutoff"]), "--threads", str(settings["threads"]),
            "--init-mode", str(settings["init_mode"]),
            "--expected-manifest-sha256", spec["provenance"]["manifest_sha256"],
            "--expected-julia-version", spec["provenance"]["server_julia_version"],
        ]
        if args.dry_run:
            print(json.dumps({"cell_id": cell["cell_id"], "command": command}, ensure_ascii=False))
            continue
        write_json(run_dir / "round_status.json", {"status": "running", "updated_at": now(), "current_cell": cell["cell_id"], "completed": completed})
        global ACTIVE
        ACTIVE = subprocess.Popen(command, cwd=ROOT, text=True)
        returncode = ACTIVE.wait()
        ACTIVE = None
        if returncode or not valid(cell_dir):
            write_json(run_dir / "round_status.json", {"status": "failed", "updated_at": now(), "failed_cell": cell["cell_id"], "completed": completed})
            raise SystemExit(returncode or 1)
        completed.append(cell["cell_id"])
    if args.dry_run:
        print(f"DRY_RUN_OK cells={len(spec['cells'])}")
    else:
        write_json(run_dir / "round_status.json", {"status": "success", "finished_at": now(), "completed": completed})


if __name__ == "__main__":
    main()
