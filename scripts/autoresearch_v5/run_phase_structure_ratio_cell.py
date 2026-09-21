#!/usr/bin/env python3
"""执行一个相图 cell，并用双初态生成结构因子比值误差。"""

from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from progress import ProgressWriter


ROOT = Path(__file__).resolve().parents[2]
SINGLE_CELL = ROOT / "scripts" / "autoresearch_v5" / "run_positive_static_cell.py"


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


def progress_probe(outdir: Path) -> dict[str, object]:
    result: dict[str, object] = {}
    for mode in ("center", "domain"):
        path = outdir / f"start_{mode}" / "progress.json"
        if path.is_file():
            try:
                result[f"child_{mode}"] = read_json(path)
            except (OSError, json.JSONDecodeError):
                result[f"child_{mode}"] = {"status": "unreadable"}
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cell-id", required=True)
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--alpha", type=float, required=True)
    parser.add_argument("--beta", type=float, required=True)
    parser.add_argument("--n-units", type=int, required=True)
    parser.add_argument("--maxdim", type=int, required=True)
    parser.add_argument("--nsweeps", type=int, required=True)
    parser.add_argument("--cutoff", type=float, required=True)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--standard-sha256", required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--expected-julia-version", required=True)
    parser.add_argument("--source-commit", default="unknown")
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
    if not SINGLE_CELL.is_file():
        raise SystemExit(f"找不到单 cell runner: {SINGLE_CELL}")

    starts = ("center", "domain")
    commands: list[list[str]] = []
    for mode in starts:
        start_dir = outdir / f"start_{mode}"
        commands.append([
            sys.executable,
            str(SINGLE_CELL),
            "--cell-id", f"{args.cell_id}-{mode}",
            "--outdir", str(start_dir),
            "--path-id", args.cell_id,
            "--group", "0",
            "--role", "ridge",
            "--alpha", str(args.alpha),
            "--beta", str(args.beta),
            "--n-units", str(args.n_units),
            "--maxdim", str(args.maxdim),
            "--nsweeps", str(args.nsweeps),
            "--cutoff", str(args.cutoff),
            "--threads", str(args.threads),
            "--init-mode", mode,
            "--string-margin", "3",
            "--schmidt-levels", "16",
            "--standard-sha256", args.standard_sha256,
            "--expected-manifest-sha256", args.expected_manifest_sha256,
            "--expected-julia-version", args.expected_julia_version,
            "--source-commit", args.source_commit,
            "--julia", args.julia,
        ])

    if args.dry_run:
        print(json.dumps({"cell_id": args.cell_id, "commands": commands}, ensure_ascii=False))
        return

    outdir.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    write_json(outdir / "status.json", {"status": "running", "started_at": started.isoformat()})
    progress = ProgressWriter(
        outdir,
        {"job_type": "positive_static_multistart", "cell_id": args.cell_id, "phase": "starting", "children": 2},
        probe=lambda: progress_probe(outdir),
    )
    progress.start()
    atexit.register(lambda: progress.finish(status="aborted", returncode=1))
    results: dict[str, dict[str, object]] = {}
    returncodes: dict[str, int] = {}
    for mode, command in zip(starts, commands):
        progress.update(phase=f"child_{mode}", current_child=mode)
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
        returncodes[mode] = result.returncode
        (outdir / f"runner_{mode}.stdout.log").write_text(result.stdout, encoding="utf-8")
        (outdir / f"runner_{mode}.stderr.log").write_text(result.stderr, encoding="utf-8")
        manifest_path = outdir / f"start_{mode}" / "manifest.json"
        if manifest_path.is_file():
            results[mode] = read_json(manifest_path)
        else:
            results[mode] = {"status": "failed", "error": result.stderr[-2000:]}

    values: list[float] = []
    truncations: list[float] = []
    for mode in starts:
        manifest = results[mode]
        observables = manifest.get("observables", {})
        diagnostics = manifest.get("diagnostics", {})
        value = observables.get("structure_factor_ratio")
        truncation = max(
            float(diagnostics.get("final_truncation_error_sz0", math.inf)),
            float(diagnostics.get("final_truncation_error_sz1", math.inf)),
        )
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            values.append(float(value))
        truncations.append(truncation)

    accepted_children = all(bool(results[mode].get("accepted")) for mode in starts)
    complete = len(values) == 2 and all(code == 0 for code in returncodes.values())
    value = sum(values) / len(values) if values else math.nan
    spread_error = abs(values[0] - values[1]) / 2 if len(values) == 2 else math.inf
    # 误差为双初态半差与截断误差下限的较大者。
    error = max(spread_error, 10 * max(truncations, default=math.inf), 1e-4)
    status = "success" if complete and accepted_children else "failed"
    finished = datetime.now(timezone.utc)
    manifest = {
        "schema_version": 1,
        "cell_id": args.cell_id,
        "status": status,
        "accepted": status == "success",
        "params": {"alpha": args.alpha, "beta": args.beta, "L": 5 * args.n_units, "n_units": args.n_units},
        "settings": {
            "method": "finite_dmrg_multistart",
            "boundary": "OBC",
            "sectors": ["Sz=0", "Sz=1"],
            "maxdim": args.maxdim,
            "nsweeps": args.nsweeps,
            "budget": args.nsweeps,
            "cutoff": args.cutoff,
            "threads": args.threads,
            "init_modes": list(starts),
        },
        "observables": {
            "structure_factor_ratio": {
                "value": value,
                "error": error,
                "definition": "1 - S(pi-2pi/M)/S(pi), central OBC window M",
                "start_values": values,
            },
        },
        "diagnostics": {
            "child_manifests": [f"start_{mode}/manifest.json" for mode in starts],
            "child_returncodes": returncodes,
            "child_truncation_max": max(truncations, default=math.inf),
            "independent_start_half_range": spread_error,
        },
        "acceptance": {
            "children_completed": complete,
            "children_accepted": accepted_children,
            "finite_ratio": math.isfinite(value),
            "finite_error": math.isfinite(error),
        },
        "provenance": {
            "source_commit": args.source_commit,
            "standard_sha256": args.standard_sha256,
            "manifest_sha256": sha256(ROOT / "Manifest.toml"),
            "negative_alpha_excluded": True,
            "error_definition": "双初态半差与10倍最大截断误差的较大者，另设1e-4数值下限",
        },
        "timing": {"started_at": started.isoformat(), "finished_at": finished.isoformat()},
        "returncode": 0 if status == "success" else 1,
    }
    write_json(outdir / "manifest.json", manifest)
    write_json(outdir / "status.json", {"status": status, "accepted": status == "success", "returncode": manifest["returncode"]})
    progress.finish(status=status, returncode=manifest["returncode"], phase="finished", accepted=status == "success")
    files = sorted(path for path in outdir.iterdir() if path.is_file() and path.name != "checksums.sha256")
    (outdir / "checksums.sha256").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in files), encoding="utf-8"
    )
    if status != "success":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
