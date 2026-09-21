#!/usr/bin/env python3
"""在无调度器服务器上顺序执行并恢复 phase cells。"""

from __future__ import annotations

import argparse
import hashlib
import json
import signal
import shutil
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


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def checksums_valid(cell_dir: Path) -> bool:
    checksum = cell_dir / "checksums.sha256"
    if not checksum.is_file():
        return False
    for line in checksum.read_text(encoding="utf-8").splitlines():
        expected, name = line.split("  ", 1)
        target = cell_dir / name
        if not target.is_file() or sha256(target) != expected:
            return False
    return True


def completed(cell_dir: Path) -> bool:
    manifest = cell_dir / "manifest.json"
    return (
        manifest.is_file()
        and checksums_valid(cell_dir)
        and read_json(manifest).get("status") == "success"
        and bool(read_json(manifest).get("accepted"))
    )


def stop_child(signum: int, _frame: object) -> None:
    if ACTIVE_CHILD is not None and ACTIVE_CHILD.poll() is None:
        ACTIVE_CHILD.send_signal(signum)
    raise SystemExit(128 + signum)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-spec", required=True)
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--standard-sha256", required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--expected-julia-version", required=True)
    parser.add_argument("--source-commit", default="uploaded-bundle")
    parser.add_argument("--julia", default="auto")
    parser.add_argument("--max-cells", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    run_spec_path = Path(args.run_spec).resolve()
    run_spec = read_json(run_spec_path)
    outdir = Path(args.outdir).resolve()
    try:
        outdir.relative_to((ROOT / "results").resolve())
    except ValueError as error:
        raise SystemExit(f"输出目录不在 results 下: {outdir}") from error
    if not run_spec.get("cells"):
        raise SystemExit("run spec 没有 cell")
    settings = run_spec["settings"]
    cells = list(run_spec["cells"])
    if args.max_cells is not None:
        if args.max_cells <= 0:
            raise SystemExit("max-cells 必须为正数")
        cells = cells[: args.max_cells]
    if any(float(cell["params"]["alpha"]) < 0 or float(cell["params"]["beta"]) < 0 for cell in cells):
        raise SystemExit("禁止生成负耦合任务")
    runner = ROOT / "scripts" / "autoresearch_v5" / "run_phase_structure_ratio_cell.py"
    if not runner.is_file():
        raise SystemExit(f"找不到 phase runner: {runner}")
    if not args.dry_run:
        outdir.mkdir(parents=True, exist_ok=True)
    cells_dir = outdir / "cells"
    if not args.dry_run:
        cells_dir.mkdir(parents=True, exist_ok=True)
    signal.signal(signal.SIGTERM, stop_child)
    signal.signal(signal.SIGINT, stop_child)

    commands = []
    for cell in cells:
        params = cell["params"]
        length = int(params["L"])
        maxdim = int(settings["maxdim_by_L"][str(length)])
        command = [
            sys.executable,
            str(runner),
            "--cell-id", str(cell["cell_id"]),
            "--outdir", str(cells_dir / str(cell["cell_id"])),
            "--alpha", str(params["alpha"]),
            "--beta", str(params["beta"]),
            "--n-units", str(params.get("n_units", length // 5)),
            "--maxdim", str(maxdim),
            "--nsweeps", str(int(cell.get("budget", settings["nsweeps"]))),
            "--cutoff", str(settings["cutoff"]),
            "--threads", str(settings["threads"]),
            "--standard-sha256", args.standard_sha256,
            "--expected-manifest-sha256", args.expected_manifest_sha256,
            "--expected-julia-version", args.expected_julia_version,
            "--source-commit", args.source_commit,
            "--julia", args.julia,
        ]
        if shutil.which("nice"):
            command = ["nice", "-n", "10", *command]
        commands.append((cell, command))

    if args.dry_run:
        for cell, command in commands:
            print(json.dumps({"cell_id": cell["cell_id"], "command": command}, ensure_ascii=False))
        print(f"DRY_RUN_OK cells={len(commands)}")
        return

    status_path = outdir / "run_status.json"
    completed_ids: list[str] = []
    write_json(status_path, {"status": "running", "started_at": now(), "completed": completed_ids})
    for cell, command in commands:
        cell_id = str(cell["cell_id"])
        cell_dir = cells_dir / cell_id
        if completed(cell_dir):
            completed_ids.append(cell_id)
            continue
        if cell_dir.exists() and any(cell_dir.iterdir()):
            raise SystemExit(f"存在未通过校验的 cell，拒绝覆盖: {cell_dir}")
        write_json(status_path, {"status": "running", "updated_at": now(), "current_cell": cell_id, "completed": completed_ids})
        global ACTIVE_CHILD
        ACTIVE_CHILD = subprocess.Popen(command, cwd=ROOT, text=True)
        returncode = ACTIVE_CHILD.wait()
        ACTIVE_CHILD = None
        if returncode != 0 or not completed(cell_dir):
            write_json(status_path, {"status": "failed", "updated_at": now(), "failed_cell": cell_id, "returncode": returncode, "completed": completed_ids})
            raise SystemExit(returncode or 1)
        completed_ids.append(cell_id)

    write_json(status_path, {"status": "success", "finished_at": now(), "completed": completed_ids, "cell_count": len(completed_ids)})
    write_json(outdir / "run.json", {
        "schema_version": 1,
        "run_id": run_spec.get("run_id"),
        "source_run_spec": str(run_spec_path),
        "cell_count": len(completed_ids),
        "provenance": {
            "source_commit": args.source_commit,
            "standard_sha256": args.standard_sha256,
            "manifest_sha256": args.expected_manifest_sha256,
            "julia_version": args.expected_julia_version,
            "offline": True,
            "negative_alpha_excluded": True,
        },
    })


if __name__ == "__main__":
    main()
