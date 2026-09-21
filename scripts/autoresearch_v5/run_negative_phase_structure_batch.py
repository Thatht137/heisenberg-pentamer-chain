#!/usr/bin/env python3
"""在无调度器服务器顺序执行并恢复负 alpha 相图 cells。"""

from __future__ import annotations

import argparse
import hashlib
import json
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from negative_dmrg_options import (
    EIGSOLVE_KRYLOVDIM_DEFAULT,
    EIGSOLVE_MAXITER,
    EIGSOLVE_TOL,
    parse_krylovdim_arg,
    validate_krylovdim,
)


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "autoresearch_v5" / "run_negative_phase_structure_cell.py"
ACTIVE_CHILD: subprocess.Popen[str] | None = None


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def checksums_valid(cell_dir: Path) -> bool:
    checksum = cell_dir / "checksums.sha256"
    if not checksum.is_file():
        return False
    for line in checksum.read_text(encoding="utf-8").splitlines():
        expected, name = line.split("  ", 1)
        if not (cell_dir / name).is_file() or sha256(cell_dir / name) != expected:
            return False
    return True


def completed(cell_dir: Path) -> bool:
    manifest = cell_dir / "manifest.json"
    return manifest.is_file() and checksums_valid(cell_dir) and read_json(manifest).get("status") == "success" and bool(read_json(manifest).get("accepted"))


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
    parser.add_argument("--eigsolve-krylovdim", type=parse_krylovdim_arg)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run_spec_path = Path(args.run_spec).resolve()
    run_spec = read_json(run_spec_path)
    if not bool(run_spec.get("provenance", {}).get("negative_alpha_included")):
        raise SystemExit("run spec 必须显式声明 negative_alpha_included=true")
    cells = list(run_spec.get("cells", []))
    if not cells:
        raise SystemExit("run spec 没有 cell")
    if args.max_cells is not None:
        if args.max_cells <= 0:
            raise SystemExit("max-cells 必须为正数")
        cells = cells[:args.max_cells]
    for cell in cells:
        params = cell.get("params", {})
        if not -1.0 <= float(params.get("alpha", 1.0)) < 0.0 or not 0.0 <= float(params.get("beta", -1.0)) <= 1.0:
            raise SystemExit("每个 cell 必须满足 -1<=alpha<0 与 0<=beta<=1")
    settings = run_spec.get("settings", {})
    eigsolve_krylovdim = validate_krylovdim(
        args.eigsolve_krylovdim if args.eigsolve_krylovdim is not None else settings.get("eigsolve_krylovdim", EIGSOLVE_KRYLOVDIM_DEFAULT)
    )
    required = ("maxdim_by_L", "nsweeps", "cutoff", "threads")
    if any(key not in settings for key in required) or not RUNNER.is_file():
        raise SystemExit("run spec 设置不完整或找不到负区 runner")
    init_modes = settings.get("init_modes", ["center", "ferro_j2"])
    if not isinstance(init_modes, list) or len(init_modes) < 2 or any(not isinstance(mode, str) for mode in init_modes):
        raise SystemExit("init_modes 必须是至少两个字符串")
    noise_profile = str(settings.get("noise_profile", "legacy"))
    if noise_profile not in {"legacy", "repair"}:
        raise SystemExit("noise_profile 必须为 legacy 或 repair")
    random_seed = int(settings.get("random_seed", 20260811))
    energy_change_max = settings.get("energy_change_max")
    if energy_change_max is not None and float(energy_change_max) <= 0:
        raise SystemExit("energy_change_max 必须为正数")
    energy_spread_max = settings.get("energy_spread_max")
    if energy_spread_max is not None and float(energy_spread_max) <= 0:
        raise SystemExit("energy_spread_max 必须为正数")
    variance_max = float(settings.get("variance_per_site_max", 1e-8))
    if variance_max <= 0:
        raise SystemExit("variance_per_site_max 必须为正数")
    outdir = Path(args.outdir).resolve()
    try:
        outdir.relative_to((ROOT / "results").resolve())
    except ValueError as error:
        raise SystemExit(f"输出目录不在 results 下: {outdir}") from error
    commands: list[tuple[dict[str, object], list[str]]] = []
    for cell in cells:
        params = dict(cell["params"])
        length = int(params["L"])
        maxdim = int(settings["maxdim_by_L"][str(length)])
        command = [
            sys.executable, str(RUNNER), "--cell-id", str(cell["cell_id"]), "--outdir", str(outdir / "cells" / str(cell["cell_id"])),
            "--alpha", str(params["alpha"]), "--beta", str(params["beta"]), "--n-units", str(params.get("n_units", length // 5)),
            "--maxdim", str(maxdim), "--nsweeps", str(int(cell.get("budget", settings["nsweeps"]))), "--cutoff", str(settings["cutoff"]),
            "--threads", str(settings["threads"]), "--q-count", str(int(settings.get("q_count", 401))), "--standard-sha256", args.standard_sha256,
            "--expected-manifest-sha256", args.expected_manifest_sha256, "--expected-julia-version", args.expected_julia_version,
            "--source-commit", args.source_commit, "--julia", args.julia, "--eigsolve-krylovdim", str(eigsolve_krylovdim),
            "--variance-max", str(variance_max),
        ]
        command.extend(["--init-modes", ",".join(init_modes), "--noise-profile", noise_profile, "--random-seed", str(random_seed)])
        if energy_change_max is not None:
            command.extend(["--energy-change-max", str(float(energy_change_max))])
        if energy_spread_max is not None:
            command.extend(["--energy-spread-max", str(float(energy_spread_max))])
        if bool(settings.get("save_state", False)):
            command.append("--save-state")
        if bool(settings.get("enriched_diagnostics", False)):
            command.append("--enriched-diagnostics")
        commands.append((cell, command))
    if args.dry_run:
        for cell, command in commands:
            print(json.dumps({"cell_id": cell["cell_id"], "command": command}, ensure_ascii=False))
        print(f"DRY_RUN_OK cells={len(commands)}")
        return
    outdir.mkdir(parents=True, exist_ok=True)
    cells_dir = outdir / "cells"
    cells_dir.mkdir(parents=True, exist_ok=True)
    signal.signal(signal.SIGTERM, stop_child)
    signal.signal(signal.SIGINT, stop_child)
    status_path = outdir / "run_status.json"
    completed_ids: list[str] = []
    write_json(status_path, {"status": "running", "started_at": now(), "completed": completed_ids, "eigsolve_krylovdim": eigsolve_krylovdim, "eigsolve_maxiter": EIGSOLVE_MAXITER, "eigsolve_tol": EIGSOLVE_TOL})
    for cell, command in commands:
        cell_id = str(cell["cell_id"])
        cell_dir = cells_dir / cell_id
        if completed(cell_dir):
            completed_ids.append(cell_id)
            continue
        if cell_dir.exists() and any(cell_dir.iterdir()):
            raise SystemExit(f"存在未通过校验的 cell，拒绝覆盖: {cell_dir}")
        write_json(status_path, {"status": "running", "updated_at": now(), "current_cell": cell_id, "completed": completed_ids, "eigsolve_krylovdim": eigsolve_krylovdim, "eigsolve_maxiter": EIGSOLVE_MAXITER, "eigsolve_tol": EIGSOLVE_TOL})
        global ACTIVE_CHILD
        ACTIVE_CHILD = subprocess.Popen(command, cwd=ROOT, text=True)
        returncode = ACTIVE_CHILD.wait()
        ACTIVE_CHILD = None
        if returncode != 0 or not completed(cell_dir):
            write_json(status_path, {"status": "failed", "updated_at": now(), "failed_cell": cell_id, "returncode": returncode, "completed": completed_ids})
            raise SystemExit(returncode or 1)
        completed_ids.append(cell_id)
    write_json(status_path, {"status": "success", "finished_at": now(), "completed": completed_ids, "cell_count": len(completed_ids), "eigsolve_krylovdim": eigsolve_krylovdim, "eigsolve_maxiter": EIGSOLVE_MAXITER, "eigsolve_tol": EIGSOLVE_TOL})
    write_json(outdir / "run.json", {"schema_version": 1, "run_id": run_spec.get("run_id"), "source_run_spec": str(run_spec_path), "cell_count": len(completed_ids), "settings": {"eigsolve_krylovdim": eigsolve_krylovdim, "eigsolve_maxiter": EIGSOLVE_MAXITER, "eigsolve_tol": EIGSOLVE_TOL}, "provenance": {"source_commit": args.source_commit, "standard_sha256": args.standard_sha256, "manifest_sha256": args.expected_manifest_sha256, "julia_version": args.expected_julia_version, "offline": True, "negative_alpha_included": True, "code_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in (Path(__file__).resolve(), RUNNER, ROOT / "scripts" / "autoresearch_v5" / "run_negative_static_cell.py", ROOT / "scripts" / "autoresearch_v5" / "negative_dmrg_options.py", ROOT / "scripts" / "autoresearch_v5" / "negative_static_cell.jl")}}})


if __name__ == "__main__":
    main()
