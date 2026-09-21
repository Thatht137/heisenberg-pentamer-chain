#!/usr/bin/env python3
"""顺序执行一个五轮计算清单。"""

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
ACTIVE_CHILD: subprocess.Popen[str] | None = None


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def verify_checksums(cell_dir: Path) -> bool:
    checksum_path = cell_dir / "checksums.sha256"
    if not checksum_path.is_file():
        return False
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        expected, name = line.split("  ", 1)
        target = cell_dir / name
        if not target.is_file() or sha256(target) != expected:
            return False
    return True


def completed(cell_dir: Path) -> bool:
    status_path = cell_dir / "status.json"
    if not status_path.is_file() or not verify_checksums(cell_dir):
        return False
    return json.loads(status_path.read_text(encoding="utf-8")).get("status") == "success"


def stop_child(signum: int, _frame: object) -> None:
    if ACTIVE_CHILD is not None and ACTIVE_CHILD.poll() is None:
        ACTIVE_CHILD.send_signal(signum)
    raise SystemExit(128 + signum)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-spec", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    run_spec_path = Path(args.run_spec).resolve()
    run_spec = json.loads(run_spec_path.read_text(encoding="utf-8"))
    run_dir_value = str(run_spec["run_dir"]).replace("\\", "/")
    run_dir = (ROOT / run_dir_value).resolve()
    run_dir.relative_to((ROOT / "results").resolve())
    cells_dir = run_dir / "cells"
    if not args.dry_run:
        cells_dir.mkdir(parents=True, exist_ok=True)
    status_path = run_dir / "round_status.json"
    settings = run_spec["settings"]
    provenance = run_spec["provenance"]
    completed_ids: list[str] = []

    signal.signal(signal.SIGTERM, stop_child)
    signal.signal(signal.SIGINT, stop_child)
    if not args.dry_run:
        write_json(status_path, {"status": "running", "started_at": now(), "completed": []})

    for cell in run_spec["cells"]:
        cell_id = cell["cell_id"]
        cell_dir = cells_dir / cell_id
        if completed(cell_dir):
            completed_ids.append(cell_id)
            continue
        if cell_dir.exists() and any(cell_dir.iterdir()):
            raise SystemExit(f"存在未通过校验的 cell，拒绝覆盖: {cell_dir}")

        config = {**settings, **cell.get("params", {}), **cell.get("settings", {})}
        alpha = float(config["alpha"])
        beta = float(config["beta"])
        length = int(config["L"])
        if not 0.0 <= alpha <= 1.0:
            raise SystemExit(f"禁止 alpha<0 或 alpha>1: {alpha}")
        if length % 5 != 0 or (length // 5) % 2 != 0:
            raise SystemExit(f"L 必须对应偶数个五聚体: {length}")

        command = [
            "nice",
            "-n",
            "10",
            sys.executable,
            "scripts/five_rounds/run_dmrg_cell.py",
            "--cell-id",
            cell_id,
            "--outdir",
            str(cell_dir),
            "--alpha",
            str(alpha),
            "--beta",
            str(beta),
            "--n-units",
            str(length // 5),
            "--maxdim",
            str(int(config["maxdim"])),
            "--nsweeps",
            str(int(config["nsweeps"])),
            "--cutoff",
            str(float(config["cutoff"])),
            "--init-mode",
            str(config["init_mode"]),
            "--threads",
            str(int(config["threads"])),
            "--source-commit",
            str(provenance["source_commit"]),
            "--standard-sha256",
            str(provenance["standard_sha256"]),
            "--expected-manifest-sha256",
            str(provenance["manifest_sha256"]),
            "--expected-julia-version",
            str(provenance["server_julia_version"]),
        ]
        if config.get("save_mps"):
            command.append("--save-mps")

        if args.dry_run:
            print(json.dumps({"cell_id": cell_id, "command": command}, ensure_ascii=False))
            continue

        write_json(
            status_path,
            {
                "status": "running",
                "updated_at": now(),
                "current_cell": cell_id,
                "completed": completed_ids,
            },
        )
        global ACTIVE_CHILD
        ACTIVE_CHILD = subprocess.Popen(command, cwd=ROOT, text=True)
        returncode = ACTIVE_CHILD.wait()
        ACTIVE_CHILD = None
        if returncode != 0 or not completed(cell_dir):
            write_json(
                status_path,
                {
                    "status": "failed",
                    "updated_at": now(),
                    "failed_cell": cell_id,
                    "returncode": returncode,
                    "completed": completed_ids,
                },
            )
            raise SystemExit(returncode or 1)
        completed_ids.append(cell_id)

    if args.dry_run:
        print(f"DRY_RUN_OK cells={len(run_spec['cells'])}")
        return

    write_json(
        status_path,
        {"status": "success", "finished_at": now(), "completed": completed_ids},
    )


if __name__ == "__main__":
    main()
