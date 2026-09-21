#!/usr/bin/env python3
"""补跑 .175 两个 Krylov cell，并合并四点交叉核对证据。"""

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
V1_OUTPUT = ROOT / "results" / "autoresearch_v5_20260919" / "static_krylov_smoke_v1"
V2_OUTPUT = ROOT / "results" / "autoresearch_v5_20260919" / "static_krylov_smoke_v2"
OUTPUT = ROOT / "results" / "autoresearch_v5_20260919" / "static_krylov_smoke_v3"
JULIA_CELL = ROOT / "scripts" / "autoresearch_v5" / "negative_static_cell.jl"
EXPECTED_JULIA_CELL_SHA256 = "17cb83c1922b39efe34542ec795632360ff63873eb173c70763ecaa34337694e"
CASES = ((-0.175, 3), (-0.175, 8))
TOTAL_TIMEOUT_SECONDS = 240.0
CLEANUP_GRACE_SECONDS = 5.0


def load_base() -> Any:
    """载入已验证 wrapper 的通用 ED/进程函数。"""
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    import smoke_static_krylov as base

    base.OUTPUT = OUTPUT
    base.CASE_SPECS = CASES
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
    return {
        path.relative_to(directory).as_posix(): sha256(path)
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def source_hashes(base: Any) -> dict[str, str]:
    paths = list(base.source_paths())
    if Path(__file__).resolve() not in paths:
        paths.append(Path(__file__).resolve())
    return {relpath(path): sha256(path) for path in paths}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def no_active_julia() -> dict[str, Any]:
    """启动前确认没有遗留 Julia 进程。"""
    probe = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq julia.exe", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        check=False,
    )
    lines = [line.strip() for line in probe.stdout.splitlines() if line.strip()]
    active = [line for line in lines if "No tasks are running" not in line]
    return {"command": probe.args, "returncode": probe.returncode, "stdout": probe.stdout, "stderr": probe.stderr, "active": active}


def validate_references(base: Any) -> dict[str, Any]:
    """锁定旧结果，执行前后均比较完整文件 hash。"""
    refs = {
        "v1_a-0100-k3": V1_OUTPUT / "a-0100-k3",
        "v2_a-0100-k8": V2_OUTPUT / "a-0100-k8",
    }
    result: dict[str, Any] = {}
    for name, directory in refs.items():
        if not directory.is_dir():
            raise FileNotFoundError(directory)
        wrapper = read_json(directory / "wrapper_run.json")
        if name.startswith("v1"):
            if wrapper.get("returncode") != 0 or wrapper.get("timed_out") is not True:
                raise ValueError("v1 a-0100-k3 事实不匹配")
        else:
            if wrapper.get("returncode") != 0 or wrapper.get("timed_out") is not False:
                raise ValueError("v2 a-0100-k8 事实不匹配")
            if wrapper.get("comparison_passed") is not True:
                raise ValueError("v2 a-0100-k8 comparison 未通过")
        result[name] = {
            "path": str(directory),
            "wrapper": wrapper,
            "file_hashes_before": file_hashes(directory),
        }
    return result


def reference_command(wrapper: dict[str, Any]) -> str:
    return wrapper.get("command_text", "")


def json_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, float) and not math.isfinite(value):
        return ""
    return value


CSV_FIELDS = [
    "source_run", "cell_id", "method", "alpha", "beta", "L", "boundary", "target_sz",
    "krylovdim", "dmrg_energy", "ed_energy", "dmrg_abs_energy_error",
    "dmrg_energy_error_budget", "ed_residual", "ed_residual_budget", "ed_norm",
    "ed_total_sz", "dmrg_state_norm", "dmrg_total_sz", "sweeps_completed",
    "metrics_status", "returncode", "timed_out",
]


def row_for(
    base: Any,
    source_run: str,
    cell: dict[str, Any],
    reference: dict[tuple[float, int], dict[str, Any]],
) -> list[dict[str, Any]]:
    alpha = float(cell["alpha"])
    krylovdim = int(cell["krylovdim"])
    metrics = cell.get("observed_metrics") or {}
    deltas = cell.get("energy_abs_deltas") or {}
    status = cell.get("metrics_status")
    if status is None:
        if cell.get("status") == "not_started":
            status = "not_started_after_timeout"
        elif metrics:
            status = "metrics_complete_timeout" if cell.get("timed_out") else "metrics_complete"
        else:
            status = "metrics_missing_timeout" if cell.get("timed_out") else "metrics_missing"
    rows = []
    for target_sz in (0, 1):
        ed = reference[(alpha, target_sz)]
        key = f"energy_sz{target_sz}"
        row = {
            "source_run": source_run,
            "cell_id": cell["cell_id"],
            "method": "DMRG",
            "alpha": alpha,
            "beta": base.BETA,
            "L": 5 * base.N_UNITS,
            "boundary": "OBC",
            "target_sz": target_sz,
            "krylovdim": krylovdim,
            "dmrg_energy": json_value(metrics.get(key)),
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
        rows.append(row)
    return rows


def write_cross_method_csv(
    base: Any,
    output: Path,
    refs: dict[str, Any],
    results: list[dict[str, Any]],
    reference: dict[tuple[float, int], dict[str, Any]],
) -> dict[str, Any]:
    old_v1 = dict(refs["v1_a-0100-k3"]["wrapper"])
    old_v1["source_run"] = "v1-reference"
    old_v1["metrics_status"] = "metrics_complete_timeout"
    old_v2 = dict(refs["v2_a-0100-k8"]["wrapper"])
    old_v2["source_run"] = "v2-reference"
    old_v2["metrics_status"] = "metrics_complete"
    rows = row_for(base, "v1-reference", old_v1, reference)
    rows.extend(row_for(base, "v2-reference", old_v2, reference))
    for result in results:
        rows.extend(row_for(base, "v3-completion", result, reference))
    path = output / "cross-method-check.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return {"path": str(path), "sha256": sha256(path), "rows": len(rows), "fields": CSV_FIELDS}


def combined_gates(base: Any, refs: dict[str, Any], results: list[dict[str, Any]]) -> dict[str, Any]:
    v1 = refs["v1_a-0100-k3"]["wrapper"]
    v2 = refs["v2_a-0100-k8"]["wrapper"]
    new_by_id = {row["cell_id"]: row for row in results}
    k8_rows = [v2, new_by_id.get("a-0175-k8", {})]
    k8_passed = len(k8_rows) == 2 and all(row.get("accepted") is True for row in k8_rows)
    v1_numeric = all(value is True for key, value in (v1.get("gates") or {}).items() if key != "execution_success")
    four = [v1, v2, *results]
    all_passed = len(four) == 4 and v1_numeric and all(row.get("comparison_passed") is True for row in four)
    return {
        "k8_gate": {
            "passed": k8_passed,
            "required_cases": 2,
            "rows": [{"cell_id": row.get("cell_id"), "accepted": row.get("accepted"), "comparison_passed": row.get("comparison_passed")} for row in k8_rows],
        },
        "all_cases_gate": {
            "passed": all_passed,
            "required_cases": 4,
            "v1_reference_numeric_passed": v1_numeric,
            "v1_timeout_reported_separately": v1.get("timed_out"),
            "rows": [{"cell_id": row.get("cell_id"), "comparison_passed": row.get("comparison_passed")} for row in four],
        },
    }


def run(base: Any, execute: bool) -> int:
    reference = base.ed_reference()
    refs = validate_references(base)
    source_before = source_hashes(base)
    if source_before[relpath(JULIA_CELL)] != EXPECTED_JULIA_CELL_SHA256:
        raise SystemExit("negative_static_cell.jl SHA256 与冻结值不一致")
    process_probe = no_active_julia()
    if process_probe["active"]:
        raise SystemExit("启动前发现活动 julia.exe: " + repr(process_probe["active"]))
    commands = [base.command_for(alpha, krylovdim) for alpha, krylovdim in CASES]
    metadata: dict[str, Any] = {
        "schema_version": 1,
        "mode": "execute" if execute else "dry-run",
        "output_dir": str(OUTPUT),
        "completion_only": True,
        "cases": [{"alpha": alpha, "krylovdim": krylovdim} for alpha, krylovdim in CASES],
        "settings": {
            "beta": base.BETA,
            "L": 5 * base.N_UNITS,
            "maxdim": base.MAXDIM,
            "nsweeps": base.NSWEEPS,
            "cutoff": float(base.CUTOFF),
            "init_mode": base.INIT_MODE,
            "noise_profile": base.NOISE_PROFILE,
            "random_seed": base.RANDOM_SEED,
            "krylov_dimensions": [3, 8],
        },
        "julia": {"executable": base.JULIA, "expected_version": base.EXPECTED_JULIA_VERSION, "pkg_offline": True, "instantiate": False},
        "source_hashes_before": source_before,
        "references_before": {
            name: {"path": item["path"], "file_hashes": item["file_hashes_before"], "returncode": item["wrapper"].get("returncode"), "timed_out": item["wrapper"].get("timed_out")}
            for name, item in refs.items()
        },
        "preflight_no_active_julia": process_probe,
        "wall_budget": {
            "case_budget_seconds": TOTAL_TIMEOUT_SECONDS,
            "cleanup_grace_seconds": CLEANUP_GRACE_SECONDS,
            "per_case": "remaining_budget_only",
            "reason": "v1 首点约85.734 s且v2冷启动约84.094 s，原180 s不足以完成四个冷启动；仅补跑 .175 两点。",
        },
        "commands": [
            {"cell_id": base.cell_id(alpha, krylovdim), "argv": command, "command": base.command_text(command), "cwd": str(ROOT)}
            for (alpha, krylovdim), command in zip(CASES, commands)
        ],
        "reference_commands": {
            name: reference_command(item["wrapper"]) for name, item in refs.items()
        },
        "ed_reference": [reference[key] for key in sorted(reference)],
    }
    if not execute:
        print(json.dumps(metadata, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    if OUTPUT.exists():
        raise SystemExit(f"拒绝覆盖已有 v3 输出目录: {OUTPUT}")
    OUTPUT.mkdir(parents=True)
    started = time.monotonic()
    deadline = started + TOTAL_TIMEOUT_SECONDS
    metadata["started_at"] = base.utc_now()
    metadata["host"] = base.platform.platform()
    metadata["python_version"] = base.platform.python_version()
    base.write_json(OUTPUT / "run_metadata.json", metadata)
    (OUTPUT / "commands.txt").write_text("\n".join(base.command_text(command) for command in commands) + "\n", encoding="utf-8")
    version = base.probe_julia_version(deadline, OUTPUT)
    metadata["julia_version_probe"] = version
    results: list[dict[str, Any]] = []
    if version.get("matches_expected", False):
        for index, (alpha, krylovdim) in enumerate(CASES):
            if time.monotonic() >= deadline:
                for pending_alpha, pending_krylov in CASES[index:]:
                    results.append({"cell_id": base.cell_id(pending_alpha, pending_krylov), "alpha": pending_alpha, "krylovdim": pending_krylov, "status": "not_started", "timed_out": False, "blocked_by_timeout": True, "reason": "剩余墙钟预算已耗尽"})
                break
            result = base.run_cell(alpha, krylovdim, deadline, reference)
            results.append(result)
            if result.get("timed_out"):
                for pending_alpha, pending_krylov in CASES[index + 1:]:
                    results.append({"cell_id": base.cell_id(pending_alpha, pending_krylov), "alpha": pending_alpha, "krylovdim": pending_krylov, "status": "not_started", "timed_out": False, "blocked_by_timeout": True, "reason": "前一 cell 超时，停止后续"})
                break
    no_active_after = no_active_julia()
    source_after = source_hashes(base)
    refs_after = validate_references(base)
    references_stable = all(refs[name]["file_hashes_before"] == refs_after[name]["file_hashes_before"] for name in refs)
    csv_info = write_cross_method_csv(base, OUTPUT, refs, results, reference)
    gates = combined_gates(base, refs, results)
    completed = len(results) == len(CASES) and all(row.get("returncode") == 0 and not row.get("timed_out", False) for row in results)
    metadata.update(
        {
            "finished_at": base.utc_now(),
            "wall_seconds_total": time.monotonic() - started,
            "results": results,
            "completed_new_cases": completed,
            "source_hashes_after": source_after,
            "source_hashes_stable": source_after == source_before,
            "references_after": {
                name: {"file_hashes": item["file_hashes_before"], "returncode": item["wrapper"].get("returncode"), "timed_out": item["wrapper"].get("timed_out")}
                for name, item in refs_after.items()
            },
            "references_stable": references_stable,
            "postflight_no_active_julia": no_active_after,
            **gates,
            "cross_method_csv": csv_info,
            "status": "pass" if gates["k8_gate"]["passed"] and gates["all_cases_gate"]["passed"] else "failed",
            "accepted": bool(gates["k8_gate"]["passed"] and gates["all_cases_gate"]["passed"] and references_stable and source_after == source_before),
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
    parser.add_argument("--execute", action="store_true", help="执行两个 .175 completion cell")
    args = parser.parse_args()
    base = load_base()
    raise SystemExit(run(base, args.execute))


if __name__ == "__main__":
    main()
