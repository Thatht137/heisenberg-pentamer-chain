#!/usr/bin/env python3
"""执行负 alpha 相图 cell，并汇总双初态全动量诊断。"""

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
from negative_dmrg_options import (
    EIGSOLVE_KRYLOVDIM_DEFAULT,
    EIGSOLVE_MAXITER,
    EIGSOLVE_TOL,
    parse_krylovdim_arg,
    validate_krylovdim,
)


ROOT = Path(__file__).resolve().parents[2]
SINGLE_CELL = ROOT / "scripts" / "autoresearch_v5" / "run_negative_static_cell.py"


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


def progress_probe(outdir: Path, starts: tuple[str, ...]) -> dict[str, object]:
    result: dict[str, object] = {}
    for mode in starts:
        path = outdir / f"start_{mode}" / "progress.json"
        if path.is_file():
            try:
                result[f"child_{mode}"] = read_json(path)
            except (OSError, json.JSONDecodeError):
                result[f"child_{mode}"] = {"status": "unreadable"}
    return result


def finite_values(manifests: dict[str, dict[str, object]], starts: tuple[str, ...], key: str) -> list[float]:
    values: list[float] = []
    for mode in starts:
        candidate = manifests[mode].get("observables", {}).get(key)
        if isinstance(candidate, (int, float)) and math.isfinite(float(candidate)):
            values.append(float(candidate))
    return values


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
    parser.add_argument("--q-count", type=int, default=401)
    parser.add_argument("--init-modes", default="center,ferro_j2")
    parser.add_argument("--noise-profile", choices=("legacy", "repair"), default="legacy")
    parser.add_argument("--random-seed", type=int, default=20260811)
    parser.add_argument("--energy-change-max", type=float)
    parser.add_argument("--energy-spread-max", type=float)
    parser.add_argument("--variance-max", type=float, default=1e-8)
    parser.add_argument("--save-state", action="store_true")
    parser.add_argument("--enriched-diagnostics", action="store_true")
    parser.add_argument("--standard-sha256", required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--expected-julia-version", required=True)
    parser.add_argument("--source-commit", default="unknown")
    parser.add_argument("--julia", default="auto")
    parser.add_argument("--eigsolve-krylovdim", type=parse_krylovdim_arg, default=EIGSOLVE_KRYLOVDIM_DEFAULT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    args.eigsolve_krylovdim = validate_krylovdim(args.eigsolve_krylovdim)
    if not -1.0 <= args.alpha < 0.0:
        raise SystemExit("alpha 必须位于 [-1,0)")
    if not 0.0 <= args.beta <= 1.0:
        raise SystemExit("beta 必须位于 [0,1]")
    if args.n_units <= 0 or args.n_units % 2 or args.q_count < 401:
        raise SystemExit("N_UNITS 必须为正偶数，Q_COUNT 至少为 401")
    starts = tuple(item.strip() for item in args.init_modes.split(",") if item.strip())
    allowed = {"center", "center_random", "domain", "ferro_j2"}
    if len(starts) < 2 or len(set(starts)) != len(starts) or any(mode not in allowed for mode in starts):
        raise SystemExit("init-modes 必须是至少两个互异合法初态")
    if args.random_seed < 0:
        raise SystemExit("random-seed 必须非负")
    if args.energy_change_max is not None and (not math.isfinite(args.energy_change_max) or args.energy_change_max <= 0):
        raise SystemExit("energy-change-max 必须为有限正数")
    if args.energy_spread_max is not None and (not math.isfinite(args.energy_spread_max) or args.energy_spread_max <= 0):
        raise SystemExit("energy-spread-max 必须为有限正数")
    if not math.isfinite(args.variance_max) or args.variance_max <= 0:
        raise SystemExit("variance-max 必须为有限正数")
    outdir = Path(args.outdir).resolve()
    try:
        outdir.relative_to((ROOT / "results").resolve())
    except ValueError as error:
        raise SystemExit(f"输出目录不在 results 下: {outdir}") from error
    if outdir.exists() and any(outdir.iterdir()):
        raise SystemExit(f"拒绝覆盖已有 cell: {outdir}")
    if not SINGLE_CELL.is_file():
        raise SystemExit(f"找不到单 cell runner: {SINGLE_CELL}")
    commands: list[list[str]] = []
    for mode in starts:
        commands.append([
            sys.executable, str(SINGLE_CELL), "--cell-id", f"{args.cell_id}-{mode}", "--outdir", str(outdir / f"start_{mode}"),
            "--path-id", args.cell_id, "--group", "0", "--role", "ridge", "--alpha", str(args.alpha), "--beta", str(args.beta),
            "--n-units", str(args.n_units), "--maxdim", str(args.maxdim), "--nsweeps", str(args.nsweeps), "--cutoff", str(args.cutoff),
            "--threads", str(args.threads), "--init-mode", mode, "--string-margin", "3", "--schmidt-levels", "16", "--q-count", str(args.q_count),
            "--standard-sha256", args.standard_sha256, "--expected-manifest-sha256", args.expected_manifest_sha256,
            "--expected-julia-version", args.expected_julia_version, "--source-commit", args.source_commit, "--julia", args.julia,
            "--noise-profile", args.noise_profile, "--random-seed", str(args.random_seed), "--eigsolve-krylovdim", str(args.eigsolve_krylovdim),
            "--variance-max", str(args.variance_max),
        ])
        if args.energy_change_max is not None:
            commands[-1].extend(["--energy-change-max", str(args.energy_change_max)])
        if args.save_state:
            commands[-1].append("--save-state")
        if args.enriched_diagnostics:
            commands[-1].append("--enriched-diagnostics")
    if args.dry_run:
        print(json.dumps({"cell_id": args.cell_id, "commands": commands}, ensure_ascii=False))
        return

    outdir.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    write_json(outdir / "status.json", {"status": "running", "started_at": started.isoformat()})
    progress = ProgressWriter(outdir, {"job_type": "negative_static_multistart", "cell_id": args.cell_id, "phase": "starting", "children": len(starts), "eigsolve_krylovdim": args.eigsolve_krylovdim, "eigsolve_maxiter": EIGSOLVE_MAXITER, "eigsolve_tol": EIGSOLVE_TOL}, probe=lambda: progress_probe(outdir, starts))
    progress.start()
    atexit.register(lambda: progress.finish(status="aborted", returncode=1))
    manifests: dict[str, dict[str, object]] = {}
    returncodes: dict[str, int] = {}
    for mode, command in zip(starts, commands):
        progress.update(phase=f"child_{mode}", current_child=mode)
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
        returncodes[mode] = completed.returncode
        (outdir / f"runner_{mode}.stdout.log").write_text(completed.stdout, encoding="utf-8")
        (outdir / f"runner_{mode}.stderr.log").write_text(completed.stderr, encoding="utf-8")
        path = outdir / f"start_{mode}" / "manifest.json"
        manifests[mode] = read_json(path) if path.is_file() else {"status": "failed", "error": completed.stderr[-2000:]}
    ratios = finite_values(manifests, starts, "structure_factor_ratio")
    peaks_q = finite_values(manifests, starts, "structure_factor_peak_q_over_pi")
    peaks_s = finite_values(manifests, starts, "structure_factor_peak")
    peaks_r = finite_values(manifests, starts, "dominant_structure_factor_ratio")
    energies_sz0 = finite_values(manifests, starts, "energy_sz0")
    energies_sz1 = finite_values(manifests, starts, "energy_sz1")
    truncations = [max(float(manifests[mode].get("diagnostics", {}).get("final_truncation_error_sz0", math.inf)), float(manifests[mode].get("diagnostics", {}).get("final_truncation_error_sz1", math.inf))) for mode in starts]
    def summary(values: list[float]) -> tuple[float, float]:
        if len(values) != len(starts):
            return math.nan, math.inf
        return sum(values) / len(values), (max(values) - min(values)) / 2
    pi_ratio, pi_spread = summary(ratios)
    q_peak, q_spread = summary(peaks_q)
    sq_peak, sq_spread = summary(peaks_s)
    peak_ratio, peak_spread = summary(peaks_r)
    _, energy_spread_sz0 = summary(energies_sz0)
    _, energy_spread_sz1 = summary(energies_sz1)
    energy_range_sz0 = 2 * energy_spread_sz0
    energy_range_sz1 = 2 * energy_spread_sz1
    numerical_floor = max(10 * max(truncations, default=math.inf), 1e-4)
    children_complete = all(code == 0 for code in returncodes.values()) and len(ratios) == len(peaks_q) == len(peaks_s) == len(peaks_r) == len(starts)
    children_accepted = all(bool(manifests[mode].get("accepted")) for mode in starts)
    energy_consistency = (
        args.energy_spread_max is None
        or (len(energies_sz0) == len(starts) and len(energies_sz1) == len(starts)
            and energy_range_sz0 <= args.energy_spread_max and energy_range_sz1 <= args.energy_spread_max)
    )
    status = "success" if children_complete and children_accepted and energy_consistency else "failed"
    acceptance = {"children_completed": children_complete, "children_accepted": children_accepted, "finite_pi_ratio": math.isfinite(pi_ratio), "finite_q_peak": math.isfinite(q_peak), "finite_peak": math.isfinite(sq_peak), "finite_peak_ratio": math.isfinite(peak_ratio), "energy_consistency": energy_consistency}
    finished = datetime.now(timezone.utc)
    manifest = {
        "schema_version": 1, "cell_id": args.cell_id, "status": status, "accepted": status == "success",
        "params": {"alpha": args.alpha, "beta": args.beta, "L": 5 * args.n_units, "n_units": args.n_units},
        "settings": {"method": "finite_dmrg_multistart", "boundary": "OBC", "sectors": ["Sz=0", "Sz=1"], "maxdim": args.maxdim, "nsweeps": args.nsweeps, "budget": args.nsweeps, "cutoff": args.cutoff, "threads": args.threads, "init_modes": list(starts), "q_count": args.q_count, "noise_profile": args.noise_profile, "random_seed": args.random_seed, "variance_per_site_max": args.variance_max, "save_state": args.save_state, "enriched_diagnostics": args.enriched_diagnostics, "eigsolve_krylovdim": args.eigsolve_krylovdim, "eigsolve_maxiter": EIGSOLVE_MAXITER, "eigsolve_tol": EIGSOLVE_TOL} | ({"energy_change_max": args.energy_change_max} if args.energy_change_max is not None else {}) | ({"energy_spread_max": args.energy_spread_max} if args.energy_spread_max is not None else {}),
        "observables": {
            "structure_factor_ratio": {"value": pi_ratio, "error": max(pi_spread, numerical_floor), "definition": "1-S(pi-2pi/M)/S(pi), central OBC window"},
            "structure_factor_peak_q_over_pi": {"value": q_peak, "error": max(q_spread, 1 / (args.q_count - 1)), "definition": "argmax S(q)/pi, q in [0,pi]"},
            "structure_factor_peak": {"value": sq_peak, "error": max(sq_spread, numerical_floor), "definition": "max S(q), central OBC window"},
            "dominant_structure_factor_ratio": {"value": peak_ratio, "error": max(peak_spread, numerical_floor), "definition": "中心峰用双侧邻点，q_peak=0/pi 时用单侧邻点；dq=2pi/M"},
            "structure_factor_peak_ratio": {"value": peak_ratio, "error": max(peak_spread, numerical_floor), "definition": "兼容别名；见 dominant_structure_factor_ratio"},
        },
        "diagnostics": {"child_manifests": [f"start_{mode}/manifest.json" for mode in starts], "child_returncodes": returncodes, "child_truncation_max": max(truncations, default=math.inf), "independent_start_half_range": {"pi_ratio": pi_spread, "q_peak_over_pi": q_spread, "peak": sq_spread, "peak_ratio": peak_spread}, "independent_start_energy_spread": {"sz0": energy_range_sz0, "sz1": energy_range_sz1}},
        "acceptance": acceptance,
        "provenance": {"source_commit": args.source_commit, "standard_sha256": args.standard_sha256, "manifest_sha256": sha256(ROOT / "Manifest.toml"), "negative_alpha_included": True, "acceptance_policy": "practical_v2" if args.variance_max != 1e-8 else "strict_v1", "dominant_ratio_boundary_rule": "q_peak=0 或 pi 时采用一侧 dq 邻点；内部峰采用两侧均值", "code_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in (SINGLE_CELL, Path(__file__).resolve(), ROOT / "scripts" / "autoresearch_v5" / "negative_static_cell.jl", ROOT / "scripts" / "autoresearch_v5" / "negative_dmrg_options.py", ROOT / "scripts" / "autoresearch_v5" / "progress.py")}, "error_definition": "多初态均值；误差取半极差与10倍最大最终截断误差的较大者，幅值项另设1e-4下限"},
        "timing": {"started_at": started.isoformat(), "finished_at": finished.isoformat()}, "returncode": 0 if status == "success" else 1,
    }
    write_json(outdir / "manifest.json", manifest)
    write_json(outdir / "status.json", {"status": status, "accepted": status == "success", "returncode": manifest["returncode"]})
    progress.finish(status=status, returncode=manifest["returncode"], phase="finished", accepted=status == "success")
    files = sorted(path for path in outdir.iterdir() if path.is_file() and path.name != "checksums.sha256")
    (outdir / "checksums.sha256").write_text("".join(f"{sha256(path)}  {path.name}\n" for path in files), encoding="utf-8")
    if status != "success":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
