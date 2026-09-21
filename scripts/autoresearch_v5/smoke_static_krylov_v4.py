#!/usr/bin/env python3
"""运行两个 L=10 k=8 保存态/增强诊断对照点。"""

from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
BASE_SCRIPT = SCRIPT_DIR / "smoke_static_krylov.py"
JULIA_CELL = ROOT / "scripts" / "autoresearch_v5" / "negative_static_cell.jl"
OUTPUT = ROOT / "results" / "autoresearch_v5_20260919" / "static_krylov_smoke_v4"
CASES = ((-0.1, 8), (-0.175, 8))
TOTAL_TIMEOUT_SECONDS = 300.0
CLEANUP_GRACE_SECONDS = 5.0
EXPECTED_JULIA_CELL_SHA256 = (
    "291eb369d5441b53d4abafd36d8469e107f4c1d91622ed33478912228ed3635f"
)
OLD_JULIA_CELL_SHA256 = (
    "17cb83c1922b39efe34542ec795632360ff63873eb173c70763ecaa34337694e"
)
OLD_REFERENCE_DIRS = {
    "v1_a-0100-k3": ROOT / "results" / "autoresearch_v5_20260919" / "static_krylov_smoke_v1" / "a-0100-k3",
    "v2_a-0100-k8": ROOT / "results" / "autoresearch_v5_20260919" / "static_krylov_smoke_v2" / "a-0100-k8",
    "v3_a-0175-k3": ROOT / "results" / "autoresearch_v5_20260919" / "static_krylov_smoke_v3" / "a-0175-k3",
    "v3_a-0175-k8": ROOT / "results" / "autoresearch_v5_20260919" / "static_krylov_smoke_v3" / "a-0175-k8",
}


def load_base() -> Any:
    """复用已核验的 ED、进程和超时实现。"""
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    import smoke_static_krylov as base

    base.OUTPUT = OUTPUT
    base.CASE_SPECS = CASES
    base.SAVE_STATE = "1"
    base.ENRICHED = "1"
    return base


def sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relpath(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def file_hashes(directory: Path) -> dict[str, str]:
    if not directory.is_dir():
        raise FileNotFoundError(directory)
    return {
        path.relative_to(directory).as_posix(): sha256(path)
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def source_hashes(base: Any) -> dict[str, str]:
    paths = list(base.source_paths())
    driver = Path(__file__).resolve()
    if driver not in paths:
        paths.append(driver)
    return {relpath(path): sha256(path) for path in paths}


def no_active_julia() -> dict[str, Any]:
    """仅检查 julia.exe，不触碰其它进程。"""
    probe = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq julia.exe", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        check=False,
    )
    lines = [line.strip() for line in probe.stdout.splitlines() if line.strip()]
    active = [line for line in lines if "No tasks are running" not in line and "没有运行的任务" not in line]
    return {"command": probe.args, "returncode": probe.returncode, "stdout": probe.stdout, "stderr": probe.stderr, "active": active}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def freeze_old_references() -> dict[str, Any]:
    frozen: dict[str, Any] = {}
    for name, directory in OLD_REFERENCE_DIRS.items():
        wrapper = read_json(directory / "wrapper_run.json")
        frozen[name] = {
            "path": str(directory),
            "returncode": wrapper.get("returncode"),
            "timed_out": wrapper.get("timed_out"),
            "file_hashes": file_hashes(directory),
        }
    return frozen


def json_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, float) and not math.isfinite(value):
        return ""
    return value


def csv_rows(path: Path) -> int:
    if not path.is_file() or path.stat().st_size == 0:
        return 0
    with path.open(encoding="utf-8", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def artifact_checks(directory: Path, metrics: dict[str, Any]) -> dict[str, Any]:
    """检查增强诊断和保存态，不以文件存在替代内容检查。"""
    required = {
        "metrics": directory / "metrics.csv",
        "entropy": directory / "entropy_profile_full.csv",
        "bonds": directory / "bond_correlations.csv",
        "connected": directory / "bond_bond_connected.csv",
        "state_sz0": directory / "state_sz0.jld2",
    }
    files: dict[str, Any] = {}
    for category, path in required.items():
        exists = path.is_file()
        size = path.stat().st_size if exists else 0
        rows = csv_rows(path) if category != "state_sz0" else None
        files[category] = {"path": str(path), "exists": exists, "nonempty": size > 0, "size": size, "rows": rows}
    metric_keys = {
        "energy_sz0", "energy_sz1", "state_norm_sz0", "state_norm_sz1",
        "total_sz0", "total_sz1", "nsweeps_completed_sz0", "nsweeps_completed_sz1",
        "enriched_diagnostics", "eigsolve_krylovdim",
    }
    metrics_complete = files["metrics"]["exists"] and files["metrics"]["nonempty"] and metric_keys <= set(metrics)
    csv_complete = all(files[key]["exists"] and files[key]["nonempty"] and int(files[key]["rows"] or 0) > 0 for key in ("entropy", "bonds", "connected"))
    state_complete = files["state_sz0"]["exists"] and files["state_sz0"]["nonempty"]
    complete = metrics_complete and csv_complete and state_complete
    return {"complete": complete, "metrics_complete": metrics_complete, "files": files}


CSV_FIELDS = [
    "source_run", "cell_id", "method", "alpha", "beta", "L", "boundary", "target_sz",
    "krylovdim", "dmrg_energy", "ed_energy", "dmrg_abs_energy_error",
    "dmrg_energy_error_budget", "ed_residual", "ed_residual_budget", "ed_norm",
    "ed_total_sz", "dmrg_state_norm", "dmrg_total_sz", "sweeps_completed",
    "metrics_status", "returncode", "timed_out",
]


def cross_method_csv(base: Any, output: Path, results: list[dict[str, Any]], reference: dict[tuple[float, int], dict[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for cell in results:
        if cell.get("status") == "not_started":
            continue
        alpha = float(cell["alpha"])
        metrics = cell.get("observed_metrics") or {}
        deltas = cell.get("energy_abs_deltas") or {}
        status = "metrics_complete" if cell.get("artifact_checks", {}).get("metrics_complete") else "metrics_missing"
        for target_sz in (0, 1):
            ed = reference[(alpha, target_sz)]
            rows.append(
                {
                    "source_run": "v4-save-enriched",
                    "cell_id": cell["cell_id"],
                    "method": "DMRG",
                    "alpha": alpha,
                    "beta": base.BETA,
                    "L": 5 * base.N_UNITS,
                    "boundary": "OBC",
                    "target_sz": target_sz,
                    "krylovdim": int(cell["krylovdim"]),
                    "dmrg_energy": json_value(metrics.get(f"energy_sz{target_sz}")),
                    "ed_energy": ed["energy"],
                    "dmrg_abs_energy_error": json_value(deltas.get(f"energy_abs_delta_sz{target_sz}")),
                    "dmrg_energy_error_budget": "1e-8",
                    "ed_residual": ed["residual_ed"],
                    "ed_residual_budget": "1e-10",
                    "ed_norm": ed["norm_ed"],
                    "ed_total_sz": ed["total_sz_ed"],
                    "dmrg_state_norm": json_value(metrics.get(f"state_norm_sz{target_sz}")),
                    "dmrg_total_sz": json_value(metrics.get(f"total_sz{target_sz}")),
                    "sweeps_completed": json_value(metrics.get(f"nsweeps_completed_sz{target_sz}")),
                    "metrics_status": status,
                    "returncode": json_value(cell.get("returncode")),
                    "timed_out": str(bool(cell.get("timed_out", False))).lower(),
                }
            )
    path = output / "cross-method-check.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return {"path": str(path), "sha256": sha256(path), "rows": len(rows), "fields": CSV_FIELDS}


def run(base: Any, execute: bool) -> int:
    reference = base.ed_reference()
    source_before = source_hashes(base)
    if source_before[relpath(JULIA_CELL)] != EXPECTED_JULIA_CELL_SHA256:
        raise SystemExit("negative_static_cell.jl 新 SHA256 不匹配")
    process_probe = no_active_julia()
    if process_probe["active"]:
        raise SystemExit("启动前发现活动 julia.exe: " + repr(process_probe["active"]))
    frozen_refs = freeze_old_references()
    commands = [base.command_for(alpha, krylovdim) for alpha, krylovdim in CASES]
    metadata: dict[str, Any] = {
        "schema_version": 1,
        "mode": "execute" if execute else "dry-run",
        "output_dir": str(OUTPUT),
        "cases": [{"alpha": alpha, "krylovdim": krylovdim} for alpha, krylovdim in CASES],
        "settings": {
            "beta": base.BETA, "L": 5 * base.N_UNITS, "maxdim": base.MAXDIM,
            "nsweeps": base.NSWEEPS, "cutoff": float(base.CUTOFF), "threads": base.THREADS,
            "init_mode_sz0": base.INIT_MODE, "init_mode_sz1": "center",
            "noise_profile": base.NOISE_PROFILE, "random_seed": base.RANDOM_SEED,
            "save_state": True, "enriched_diagnostics": True, "krylov_dimensions": [8],
        },
        "julia": {"executable": base.JULIA, "expected_version": base.EXPECTED_JULIA_VERSION, "pkg_offline": True, "instantiate": False},
        "source_hashes": source_before,
        "source_change_scope": {
            "old_julia_cell_sha256": OLD_JULIA_CELL_SHA256,
            "new_julia_cell_sha256": EXPECTED_JULIA_CELL_SHA256,
            "declared_difference": "negative_static_cell.jl 15/16-args 解析修复；物理模型与门不变",
            "v4_output_delta": "仅请求 SAVE_STATE=1、ENRICHED=1 产物",
        },
        "old_reference_hashes_before": frozen_refs,
        "preflight_no_active_julia": process_probe,
        "wall_budget": {"total_seconds": TOTAL_TIMEOUT_SECONDS, "cleanup_grace_seconds": CLEANUP_GRACE_SECONDS, "per_case": "remaining_budget_only"},
        "commands": [{"cell_id": base.cell_id(alpha, krylovdim), "argv": command, "command": base.command_text(command), "cwd": str(ROOT)} for (alpha, krylovdim), command in zip(CASES, commands)],
        "ed_reference": [reference[key] for key in sorted(reference)],
    }
    if not execute:
        print(json.dumps(metadata, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    if OUTPUT.exists():
        raise SystemExit(f"拒绝覆盖已有 v4 输出目录: {OUTPUT}")
    OUTPUT.mkdir(parents=True)
    started = time.monotonic()
    deadline = started + TOTAL_TIMEOUT_SECONDS
    metadata.update({"started_at": base.utc_now(), "host": base.platform.platform(), "python_version": base.platform.python_version()})
    base.write_json(OUTPUT / "run_metadata.json", metadata)
    (OUTPUT / "commands.txt").write_text("\n".join(item["command"] for item in metadata["commands"]) + "\n", encoding="utf-8")
    version = base.probe_julia_version(deadline, OUTPUT)
    metadata["julia_version_probe"] = version
    results: list[dict[str, Any]] = []
    if version.get("matches_expected", False):
        for index, (alpha, krylovdim) in enumerate(CASES):
            if time.monotonic() >= deadline:
                for pending_alpha, pending_krylov in CASES[index:]:
                    results.append({"cell_id": base.cell_id(pending_alpha, pending_krylov), "alpha": pending_alpha, "krylovdim": pending_krylov, "status": "not_started", "timed_out": False, "blocked_by_timeout": True, "reason": "剩余墙钟预算耗尽"})
                break
            result = base.run_cell(alpha, krylovdim, deadline, reference)
            result["artifact_checks"] = artifact_checks(base.cell_dir(alpha, krylovdim), base.read_metrics(base.cell_dir(alpha, krylovdim) / "metrics.csv"))
            result["comparison_passed_with_artifacts"] = bool(result.get("comparison_passed") and result["artifact_checks"]["complete"])
            result["accepted"] = bool(result["comparison_passed_with_artifacts"])
            base.write_json(base.cell_dir(alpha, krylovdim) / "wrapper_run.json", result)
            results.append(result)
            if result.get("timed_out"):
                for pending_alpha, pending_krylov in CASES[index + 1:]:
                    results.append({"cell_id": base.cell_id(pending_alpha, pending_krylov), "alpha": pending_alpha, "krylovdim": pending_krylov, "status": "not_started", "timed_out": False, "blocked_by_timeout": True, "reason": "前一 cell 超时，停止后续"})
                break
    no_active_after = no_active_julia()
    source_after = source_hashes(base)
    refs_after = freeze_old_references()
    references_stable = all(frozen_refs[name]["file_hashes"] == refs_after[name]["file_hashes"] for name in frozen_refs)
    csv_info = cross_method_csv(base, OUTPUT, results, reference)
    complete = len(results) == len(CASES) and all(row.get("returncode") == 0 and not row.get("timed_out", False) for row in results)
    k8_passed = len(results) == len(CASES) and all(row.get("accepted") is True for row in results)
    metadata.update(
        {
            "finished_at": base.utc_now(), "wall_seconds_total": time.monotonic() - started,
            "results": results, "completed_new_cases": complete,
            "source_hashes_after": source_after, "source_hashes_stable": source_after == source_before,
            "old_reference_hashes_after": refs_after, "old_references_stable": references_stable,
            "postflight_no_active_julia": no_active_after, "cross_method_csv": csv_info,
            "k8_gate": {"passed": k8_passed, "required_cases": 2, "rows": [{"cell_id": row.get("cell_id"), "accepted": row.get("accepted"), "comparison_passed": row.get("comparison_passed"), "artifacts_complete": row.get("artifact_checks", {}).get("complete")} for row in results]},
            "all_cases_gate": {"passed": k8_passed, "required_cases": 2, "scope": "v4 两个 k=8 保存态/增强诊断点；历史 v1-v3 门另存", "rows": [{"cell_id": row.get("cell_id"), "comparison_passed_with_artifacts": row.get("comparison_passed_with_artifacts")} for row in results]},
            "status": "pass" if k8_passed and references_stable and source_after == source_before else "failed",
            "accepted": bool(k8_passed and references_stable and source_after == source_before),
        }
    )
    output_hashes = file_hashes(OUTPUT)
    output_hashes.pop("manifest.json", None)
    metadata["output_hashes_excluding_manifest"] = output_hashes
    base.write_json(OUTPUT / "manifest.json", metadata)
    print(json.dumps(metadata, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if metadata["accepted"] else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="执行两个 L=10 k=8 保存态/增强诊断点")
    args = parser.parse_args()
    base = load_base()
    raise SystemExit(run(base, args.execute))


if __name__ == "__main__":
    main()
