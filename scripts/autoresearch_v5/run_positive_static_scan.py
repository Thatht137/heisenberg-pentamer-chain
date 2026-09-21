#!/usr/bin/env python3
"""顺序执行并恢复正区静态生产扫描。"""

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
    parser.add_argument("--paths", required=True)
    parser.add_argument("--mode", choices=("pilot", "full"), default="full")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    run_spec_path = Path(args.run_spec).resolve()
    run_spec = json.loads(run_spec_path.read_text(encoding="utf-8"))
    paths_payload = json.loads(Path(args.paths).resolve().read_text(encoding="utf-8"))
    if "variants" in paths_payload:
        scan_key = "variant_id"
        path_index = {row[scan_key]: row for row in paths_payload["variants"]}
    else:
        scan_key = "path_id"
        path_index = {row[scan_key]: row for row in paths_payload["paths"]}
    run_dir = (ROOT / str(run_spec["run_dir"]).replace("\\", "/")).resolve()
    run_dir.relative_to((ROOT / "results").resolve())
    cells_dir = run_dir / "cells"
    status_path = run_dir / "round_status.json"
    settings = run_spec["settings"]
    provenance = run_spec["provenance"]
    completed_ids: list[str] = []
    if not args.dry_run:
        cells_dir.mkdir(parents=True, exist_ok=True)
        write_json(status_path, {"status": "running", "started_at": now(), "completed": []})

    signal.signal(signal.SIGTERM, stop_child)
    signal.signal(signal.SIGINT, stop_child)
    selected_cells = []
    for cell in run_spec["cells"]:
        path = path_index[str(cell["params"][scan_key])]
        if args.mode == "pilot" and not (
            int(cell["params"]["L"]) == 40 and path["role"] == "ridge"
        ):
            continue
        selected_cells.append(cell)

    for cell in selected_cells:
        cell_id = cell["cell_id"]
        cell_dir = cells_dir / cell_id
        if completed(cell_dir):
            completed_ids.append(cell_id)
            continue
        if cell_dir.exists() and any(cell_dir.iterdir()):
            raise SystemExit(f"存在未通过校验的 cell，拒绝覆盖: {cell_dir}")

        scan_id = str(cell["params"][scan_key])
        length = int(cell["params"]["L"])
        if scan_id not in path_index:
            raise SystemExit(f"未知 {scan_key}: {scan_id}")
        path = path_index[scan_id]
        path_id = str(path["path_id"])
        alpha = float(path["alpha"])
        beta = float(path["beta"])
        if alpha < 0 or beta < 0:
            raise SystemExit("禁止负耦合任务")
        if length % 10:
            raise SystemExit(f"L 必须对应偶数个五聚体: {length}")
        maxdim = int(settings["maxdim_by_L"][str(length)])
        cell_settings = {**settings, **cell.get("settings", {})}
        init_mode = str(path.get(
            "init_mode",
            cell_settings.get("init_mode_sz0", settings.get("init_mode_sz0_default", "center")),
        ))
        if init_mode not in {"center", "domain"}:
            raise SystemExit(f"未知初态模式: {init_mode}")
        command = [
            "nice", "-n", "10", sys.executable,
            "scripts/autoresearch_v5/run_positive_static_cell.py",
            "--cell-id", cell_id,
            "--outdir", str(cell_dir),
            "--path-id", path_id,
            "--group", str(path["group"]),
            "--role", str(path["role"]),
            "--alpha", str(alpha),
            "--beta", str(beta),
            "--n-units", str(length // 5),
            "--maxdim", str(maxdim),
            "--nsweeps", str(settings["nsweeps"]),
            "--cutoff", str(settings["cutoff"]),
            "--threads", str(settings["threads"]),
            "--init-mode", init_mode,
            "--string-margin", str(settings["string_margin"]),
            "--schmidt-levels", str(settings["schmidt_levels"]),
            "--source-commit", str(provenance["source_commit"]),
            "--standard-sha256", str(provenance["standard_sha256"]),
            "--expected-manifest-sha256", str(provenance["manifest_sha256"]),
            "--expected-julia-version", str(provenance["server_julia_version"]),
        ]
        if length == 80 and path["role"] == "ridge" and init_mode == "center":
            command.append("--save-state")
        if args.dry_run:
            print(json.dumps({
                "cell_id": cell_id,
                scan_key: scan_id,
                "path": path,
                "L": length,
                "init_mode": init_mode,
                "command": command,
            }, ensure_ascii=False))
            continue

        write_json(status_path, {
            "status": "running",
            "updated_at": now(),
            "current_cell": cell_id,
            "completed": completed_ids,
        })
        global ACTIVE_CHILD
        ACTIVE_CHILD = subprocess.Popen(command, cwd=ROOT, text=True)
        returncode = ACTIVE_CHILD.wait()
        ACTIVE_CHILD = None
        if returncode != 0 or not completed(cell_dir):
            write_json(status_path, {
                "status": "failed",
                "updated_at": now(),
                "failed_cell": cell_id,
                "returncode": returncode,
                "completed": completed_ids,
            })
            raise SystemExit(returncode or 1)
        completed_ids.append(cell_id)

    if args.dry_run:
        print(f"DRY_RUN_OK mode={args.mode} cells={len(selected_cells)}")
        return
    write_json(status_path, {
        "status": "pilot_success" if args.mode == "pilot" else "success",
        "mode": args.mode,
        "finished_at": now(),
        "completed": completed_ids,
    })


if __name__ == "__main__":
    main()
