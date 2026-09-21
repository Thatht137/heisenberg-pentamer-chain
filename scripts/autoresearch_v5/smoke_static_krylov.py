#!/usr/bin/env python3
"""运行 L=10 负 alpha 双扇区 Julia Krylov smoke，并记录可复核元数据。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
JULIA = "D:/program/Julia-1.11.5/bin/julia.exe"
JULIA_CELL = ROOT / "scripts" / "autoresearch_v5" / "negative_static_cell.jl"
ED_MODULE = ROOT / "scripts" / "autoresearch_v5" / "static_krylov_ed_reference.py"
V1_OUTPUT = ROOT / "results" / "autoresearch_v5_20260919" / "static_krylov_smoke_v1"
OUTPUT = ROOT / "results" / "autoresearch_v5_20260919" / "static_krylov_smoke_v2"

ALPHAS = (-0.1, -0.175)
BETA = 0.25
N_UNITS = 2
MAXDIM = 64
NSWEEPS = 16
CUTOFF = "1e-11"
THREADS = 2
INIT_MODE = "center"
STRING_MARGIN = 0
SCHMIDT_LEVELS = 8
Q_COUNT = 401
SAVE_STATE = "0"
NOISE_PROFILE = "legacy"
RANDOM_SEED = 20260811
ENRICHED = "0"
KRYLOV_DIMS = (3, 8)
CASE_SPECS = ((-0.1, 8), (-0.175, 3), (-0.175, 8))
V1_FIRST_WALL_SECONDS = 85.734
TOTAL_TIMEOUT_SECONDS = 94.0
CLEANUP_GRACE_SECONDS = 5.0
EXPECTED_JULIA_VERSION = "1.11.5"
EXPECTED_JULIA_CELL_SHA256 = "17cb83c1922b39efe34542ec795632360ff63873eb173c70763ecaa34337694e"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relpath(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def source_paths() -> list[Path]:
    paths = [
        ROOT / "Project.toml",
        ROOT / "Manifest.toml",
        JULIA_CELL,
        ED_MODULE,
        Path(__file__).resolve(),
    ]
    paths.extend(sorted((ROOT / "src").glob("*.jl")))
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError("缺少输入源码: " + ", ".join(map(str, missing)))
    return paths


def source_hashes() -> dict[str, str]:
    return {relpath(path): sha256(path) for path in source_paths()}


def output_file_hashes(directory: Path) -> dict[str, str]:
    if not directory.is_dir():
        raise FileNotFoundError(f"缺少引用输出目录: {directory}")
    return {
        path.relative_to(directory).as_posix(): sha256(path)
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def v1_reference() -> dict[str, Any]:
    reference_dir = V1_OUTPUT / "a-0100-k3"
    wrapper_path = reference_dir / "wrapper_run.json"
    if not wrapper_path.is_file():
        raise FileNotFoundError(f"缺少 v1 首点 wrapper 证据: {wrapper_path}")
    wrapper = json.loads(wrapper_path.read_text(encoding="utf-8"))
    if wrapper.get("returncode") != 0 or wrapper.get("timed_out") is not True:
        raise ValueError("v1 首点事实不是预期的 returncode=0/timed_out=true")
    return {
        "path": str(reference_dir),
        "cell_id": "a-0100-k3",
        "returncode": wrapper.get("returncode"),
        "timed_out": wrapper.get("timed_out"),
        "wall_seconds": wrapper.get("wall_seconds"),
        "file_hashes_before": output_file_hashes(reference_dir),
        "wrapper_summary": {
            "energy_abs_deltas": wrapper.get("energy_abs_deltas"),
            "observed_metrics": wrapper.get("observed_metrics"),
            "gates": wrapper.get("gates"),
        },
    }


def import_ed() -> Any:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    import static_krylov_ed_reference as ed

    return ed


def ed_reference() -> dict[tuple[float, int], dict[str, float | int]]:
    ed = import_ed()
    reference: dict[tuple[float, int], dict[str, float | int]] = {}
    for alpha in ALPHAS:
        for target_sz in (0, 1):
            row = ed.solve_sector(alpha, BETA, target_sz)
            reference[(alpha, target_sz)] = {
                "alpha": float(alpha),
                "beta": float(BETA),
                "target_sz": int(target_sz),
                "n_up": int(row["n_up"]),
                "dimension": int(row["dimension"]),
                "energy": float(row["energy"]),
                "residual_ed": float(row["residual_norm"]),
                "norm_ed": float(row["norm"]),
                "total_sz_ed": float(row["total_sz"]),
            }
    return reference


def cell_id(alpha: float, krylovdim: int) -> str:
    alpha_tag = "0100" if alpha == -0.1 else "0175"
    return f"a-{alpha_tag}-k{krylovdim}"


def cell_dir(alpha: float, krylovdim: int) -> Path:
    return OUTPUT / cell_id(alpha, krylovdim)


def command_for(alpha: float, krylovdim: int) -> list[str]:
    cell = cell_dir(alpha, krylovdim)
    return [
        JULIA,
        "--startup-file=no",
        f"--threads={THREADS}",
        "--project=.",
        "scripts/autoresearch_v5/negative_static_cell.jl",
        str(cell),
        str(alpha),
        str(BETA),
        str(N_UNITS),
        str(MAXDIM),
        str(NSWEEPS),
        CUTOFF,
        INIT_MODE,
        str(STRING_MARGIN),
        str(SCHMIDT_LEVELS),
        str(Q_COUNT),
        SAVE_STATE,
        NOISE_PROFILE,
        str(RANDOM_SEED),
        ENRICHED,
        str(krylovdim),
    ]


def command_text(command: Iterable[str]) -> str:
    return subprocess.list2cmdline([str(item) for item in command])


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def safe_float(value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return math.nan
    return result


def json_float(value: Any) -> float | None:
    result = safe_float(value)
    return result if math.isfinite(result) else None


def read_metrics(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    values: dict[str, Any] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            key = row.get("metric")
            if not key:
                continue
            value = row.get("value", "")
            try:
                values[key] = float(value)
            except ValueError:
                values[key] = value
    return values


def metric(values: dict[str, Any], key: str) -> float:
    return safe_float(values.get(key))


def finite(value: float) -> bool:
    return math.isfinite(value)


def _terminate_tree(process: subprocess.Popen[Any]) -> dict[str, Any]:
    result: dict[str, Any] = {"pid": process.pid, "taskkill_returncode": None, "waited": False, "forced_parent_kill": False}
    if process.poll() is not None:
        result["already_exited"] = True
        result["returncode"] = process.returncode
        return result
    if os.name == "nt":
        try:
            taskkill = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=2.0,
            )
            result["taskkill_returncode"] = taskkill.returncode
        except subprocess.TimeoutExpired:
            result["taskkill_timed_out"] = True
        try:
            process.wait(timeout=2.0)
            result["waited"] = True
        except subprocess.TimeoutExpired:
            process.kill()
            result["forced_parent_kill"] = True
            try:
                process.wait(timeout=1.0)
                result["waited"] = True
            except subprocess.TimeoutExpired:
                result["wait_timed_out"] = True
    else:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except ProcessLookupError:
            result["already_exited"] = True
            result["returncode"] = process.poll()
            return result
        try:
            process.wait(timeout=2.0)
            result["waited"] = True
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=1.0)
                result["waited"] = True
            except subprocess.TimeoutExpired:
                result["wait_timed_out"] = True
    result["returncode"] = process.poll()
    return result


def _popen_flags() -> dict[str, Any]:
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def offline_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "JULIA_PKG_OFFLINE": "true",
            "JULIA_PKG_SERVER": "",
            "HTTP_PROXY": "http://127.0.0.1:9",
            "HTTPS_PROXY": "http://127.0.0.1:9",
        }
    )
    return environment


def probe_julia_version(deadline: float, log_dir: Path) -> dict[str, Any]:
    command = [JULIA, "--startup-file=no", "--version"]
    record: dict[str, Any] = {
        "command": command,
        "command_text": command_text(command),
        "expected": EXPECTED_JULIA_VERSION,
    }
    if not Path(JULIA).is_file():
        record.update({"available": False, "returncode": None, "stdout": "", "stderr": "Julia 可执行文件不存在"})
        return record
    timeout = min(10.0, max(0.1, deadline - time.monotonic()))
    started = time.monotonic()
    stdout_path = log_dir / "julia_version_stdout.log"
    stderr_path = log_dir / "julia_version_stderr.log"
    with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open("w", encoding="utf-8") as stderr_handle:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=offline_environment(),
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
            **_popen_flags(),
        )
        timed_out = False
        termination = None
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            termination = _terminate_tree(process)
    stdout = stdout_path.read_text(encoding="utf-8", errors="replace")
    stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"julia version ([^\s]+)", stdout)
    version = match.group(1) if match else ""
    record.update(
        {
            "available": True,
            "version": version,
            "stdout": stdout,
            "stderr": stderr,
            "returncode": process.returncode,
            "timed_out": timed_out,
            "termination": termination,
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "wall_seconds": time.monotonic() - started,
            "matches_expected": not timed_out and process.returncode == 0 and version == EXPECTED_JULIA_VERSION,
        }
    )
    return record


def evaluate_cell(
    alpha: float,
    krylovdim: int,
    returncode: int | None,
    timed_out: bool,
    metrics: dict[str, Any],
    reference: dict[tuple[float, int], dict[str, float | int]],
) -> dict[str, Any]:
    observed = {
        key: json_float(metrics.get(key))
        for key in (
            "energy_sz0",
            "energy_sz1",
            "variance_per_site_sz0",
            "variance_per_site_sz1",
            "final_truncation_error_sz0",
            "final_truncation_error_sz1",
            "state_norm_sz0",
            "state_norm_sz1",
            "total_sz0",
            "total_sz1",
            "nsweeps_completed_sz0",
            "nsweeps_completed_sz1",
        )
    }
    deltas = {}
    for target_sz, key in ((0, "energy_sz0"), (1, "energy_sz1")):
        expected = float(reference[(alpha, target_sz)]["energy"])
        value = safe_float(metrics.get(key))
        deltas[f"energy_abs_delta_sz{target_sz}"] = abs(value - expected) if finite(value) else None
    gates: dict[str, bool] = {
        "execution_success": returncode == 0 and not timed_out,
        "metrics_present": bool(metrics),
    }
    for target_sz in (0, 1):
        row = reference[(alpha, target_sz)]
        gates[f"ed_residual_sz{target_sz}_le_1e-10"] = float(row["residual_ed"]) <= 1e-10
        gates[f"ed_norm_sz{target_sz}_near_1"] = abs(float(row["norm_ed"]) - 1.0) <= 1e-12
        gates[f"ed_total_sz{target_sz}_correct"] = abs(float(row["total_sz_ed"]) - target_sz) <= 1e-12
        delta = deltas[f"energy_abs_delta_sz{target_sz}"]
        gates[f"energy_sz{target_sz}_abs_delta_le_1e-8"] = delta is not None and delta <= 1e-8
        observed_sz = metric(metrics, f"total_sz{target_sz}")
        gates[f"dmrg_total_sz{target_sz}_correct"] = finite(observed_sz) and abs(observed_sz - target_sz) <= 1e-8
        state_norm = metric(metrics, f"state_norm_sz{target_sz}")
        gates[f"state_norm_sz{target_sz}_near_1"] = finite(state_norm) and abs(state_norm - 1.0) <= 1e-8
        variance = metric(metrics, f"variance_per_site_sz{target_sz}")
        gates[f"variance_per_site_sz{target_sz}_le_1e-8"] = finite(variance) and variance <= 1e-8
        truncation = metric(metrics, f"final_truncation_error_sz{target_sz}")
        gates[f"final_truncation_error_sz{target_sz}_le_1e-9"] = finite(truncation) and truncation <= 1e-9
        sweeps = metric(metrics, f"nsweeps_completed_sz{target_sz}")
        gates[f"all_sweeps_sz{target_sz}"] = finite(sweeps) and int(sweeps) == NSWEEPS
    comparison_passed = all(gates.values())
    return {
        "alpha": alpha,
        "beta": BETA,
        "L": 5 * N_UNITS,
        "krylovdim": krylovdim,
        "ed_reference": {
            "sz0": reference[(alpha, 0)],
            "sz1": reference[(alpha, 1)],
        },
        "observed_metrics": observed,
        "energy_abs_deltas": deltas,
        "gates": gates,
        "comparison_passed": comparison_passed,
        "k8_gate_required": krylovdim == 8,
        "accepted": comparison_passed if krylovdim == 8 else None,
    }


def metadata_for_dry_run(reference: dict[tuple[float, int], dict[str, float | int]]) -> dict[str, Any]:
    commands = []
    for alpha, krylovdim in CASE_SPECS:
        command = command_for(alpha, krylovdim)
        commands.append(
            {
                "cell_id": cell_id(alpha, krylovdim),
                "alpha": alpha,
                "krylovdim": krylovdim,
                "cwd": str(ROOT),
                "argv": command,
                "command": command_text(command),
                "estimated_wall_seconds": None,
            }
        )
    reference_rows = [reference[key] for key in sorted(reference)]
    v1 = v1_reference()
    return {
        "schema_version": 1,
        "mode": "dry-run",
        "output_dir": str(OUTPUT),
        "output_must_be_new": True,
        "settings": {
            "alpha_values": list(ALPHAS),
            "beta": BETA,
            "L": 5 * N_UNITS,
            "n_units": N_UNITS,
            "maxdim": MAXDIM,
            "nsweeps": NSWEEPS,
            "cutoff": float(CUTOFF),
            "threads": THREADS,
            "init_mode_sz0": INIT_MODE,
            "init_mode_sz1": "center",
            "string_margin": STRING_MARGIN,
            "schmidt_levels": SCHMIDT_LEVELS,
            "q_count": Q_COUNT,
            "save_state": False,
            "noise_profile": NOISE_PROFILE,
            "random_seed": RANDOM_SEED,
            "enriched_diagnostics": False,
            "krylov_dimensions": list(KRYLOV_DIMS),
            "cases": [{"alpha": alpha, "krylovdim": krylovdim} for alpha, krylovdim in CASE_SPECS],
        },
        "julia": {
            "executable": JULIA,
            "expected_version": EXPECTED_JULIA_VERSION,
            "project": ".",
            "pkg_offline": True,
            "instantiate": False,
        },
        "source_hashes": source_hashes(),
        "v1_reference": v1,
        "ed_reference": reference_rows,
        "gates": {
            "k8_energy_abs_delta_le_1e-8": True,
            "ed_residual_le_1e-10": True,
            "ed_norm_near_1": True,
            "ed_total_sz_exact": True,
            "dmrg_state_norm_tol": 1e-8,
            "dmrg_total_sz_tol": 1e-8,
            "variance_per_site_max": 1e-8,
            "final_truncation_error_max": 1e-9,
            "all_sweeps": NSWEEPS,
            "k3_reported_without_hiding": True,
        },
        "timeout": {
            "total_seconds": 180.0,
            "remaining_seconds_after_v1": TOTAL_TIMEOUT_SECONDS,
            "v1_first_wall_seconds": V1_FIRST_WALL_SECONDS,
            "cleanup_grace_seconds": CLEANUP_GRACE_SECONDS,
            "per_cell_seconds": "remaining_budget_only",
            "estimated_total_seconds": TOTAL_TIMEOUT_SECONDS,
        },
        "commands": commands,
    }


def run_cell(
    alpha: float,
    krylovdim: int,
    deadline: float,
    reference: dict[tuple[float, int], dict[str, float | int]],
) -> dict[str, Any]:
    target = cell_dir(alpha, krylovdim)
    target.mkdir(parents=True, exist_ok=False)
    command = command_for(alpha, krylovdim)
    started = time.monotonic()
    started_at = utc_now()
    timeout = max(0.1, deadline - started)
    stdout_path = target / "stdout.log"
    stderr_path = target / "stderr.log"
    with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open("w", encoding="utf-8") as stderr_handle:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=offline_environment(),
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
            **_popen_flags(),
        )
        timed_out = False
        termination = None
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            termination = _terminate_tree(process)
    wall_seconds = time.monotonic() - started
    metrics = read_metrics(target / "metrics.csv")
    comparison = evaluate_cell(alpha, krylovdim, process.returncode, timed_out, metrics, reference)
    result = {
        "cell_id": cell_id(alpha, krylovdim),
        "command": command,
        "command_text": command_text(command),
        "started_at": started_at,
        "finished_at": utc_now(),
        "wall_seconds": wall_seconds,
        "timeout_seconds": timeout,
        "timed_out": timed_out,
        "termination": termination,
        "returncode": process.returncode,
        "stdout_path": str(target / "stdout.log"),
        "stderr_path": str(target / "stderr.log"),
        "metrics_path": str(target / "metrics.csv"),
        **comparison,
    }
    write_json(target / "wrapper_run.json", result)
    return result


def run(reference: dict[tuple[float, int], dict[str, float | int]], metadata: dict[str, Any]) -> int:
    if OUTPUT.exists():
        raise SystemExit(f"拒绝覆盖已有输出目录: {OUTPUT}")
    source_before = source_hashes()
    if source_before.get(relpath(JULIA_CELL)) != EXPECTED_JULIA_CELL_SHA256:
        raise SystemExit("negative_static_cell.jl SHA256 与冻结值不一致")
    v1_before = output_file_hashes(V1_OUTPUT / "a-0100-k3")
    if v1_before != metadata["v1_reference"]["file_hashes_before"]:
        raise SystemExit("v1 首点引用 hash 在启动前已漂移")
    OUTPUT.mkdir(parents=True)
    started = time.monotonic()
    deadline = started + TOTAL_TIMEOUT_SECONDS
    metadata = {
        **metadata,
        "mode": "execute",
        "started_at": utc_now(),
        "host": platform.platform(),
        "python_version": platform.python_version(),
        "source_hashes_before": source_before,
        "v1_reference_before": v1_before,
    }
    write_json(OUTPUT / "run_metadata.json", metadata)
    (OUTPUT / "commands.txt").write_text(
        "\n".join(item["command"] for item in metadata["commands"]) + "\n",
        encoding="utf-8",
    )
    version = probe_julia_version(deadline, OUTPUT)
    metadata["julia_version_probe"] = version
    if not version.get("matches_expected", False):
        metadata.update({"status": "julia_version_failed", "finished_at": utc_now()})
        write_json(OUTPUT / "manifest.json", metadata)
        return 1

    results: list[dict[str, Any]] = []
    for index, (alpha, krylovdim) in enumerate(CASE_SPECS):
        if time.monotonic() >= deadline:
            for pending_alpha, pending_krylov in CASE_SPECS[index:]:
                results.append(
                    {
                        "cell_id": cell_id(pending_alpha, pending_krylov),
                        "alpha": pending_alpha,
                        "krylovdim": pending_krylov,
                        "status": "not_started",
                        "timed_out": False,
                        "blocked_by_timeout": True,
                        "reason": "剩余墙钟预算已耗尽",
                    }
                )
            break
        row = run_cell(alpha, krylovdim, deadline, reference)
        results.append(row)
        if row.get("timed_out"):
            for pending_alpha, pending_krylov in CASE_SPECS[index + 1:]:
                results.append(
                    {
                        "cell_id": cell_id(pending_alpha, pending_krylov),
                        "alpha": pending_alpha,
                        "krylovdim": pending_krylov,
                        "status": "not_started",
                        "timed_out": False,
                        "blocked_by_timeout": True,
                        "reason": "前一 cell 超时，按策略停止后续",
                    }
                )
            break
    k8 = [row for row in results if row.get("krylovdim") == 8]
    expected_count = len(CASE_SPECS)
    completed = len(results) == expected_count and all(
        row.get("returncode") == 0 and not row.get("timed_out", False) for row in results
    )
    source_hashes_after = source_hashes()
    hashes_stable = source_hashes_after == metadata["source_hashes_before"]
    v1_after = output_file_hashes(V1_OUTPUT / "a-0100-k3")
    v1_stable = v1_after == v1_before
    k8_gate_passed = len(k8) == 2 and all(row.get("accepted") is True for row in k8)
    v1_gates = metadata["v1_reference"]["wrapper_summary"].get("gates", {})
    v1_numeric_passed = all(value is True for key, value in v1_gates.items() if key != "execution_success")
    all_cases_gate_passed = (
        v1_numeric_passed
        and completed
        and all(row.get("comparison_passed") is True for row in results)
    )
    accepted = k8_gate_passed and hashes_stable and v1_stable
    output_hashes = output_file_hashes(OUTPUT)
    metadata.update(
        {
            "status": "k8_gate_pass_all_cases_gate_fail" if accepted and not all_cases_gate_passed else ("pass" if accepted else "failed"),
            "accepted": accepted and all_cases_gate_passed,
            "k8_gate": {"passed": k8_gate_passed, "required_cases": 2, "rows": k8},
            "all_cases_gate": {
                "passed": all_cases_gate_passed,
                "required_cases": expected_count + 1,
                "v1_reference_numeric_passed": v1_numeric_passed,
                "v1_timeout_reported_separately": metadata["v1_reference"].get("timed_out"),
            },
            "finished_at": utc_now(),
            "wall_seconds_total": time.monotonic() - started,
            "source_hashes_after": source_hashes_after,
            "source_hashes_stable": hashes_stable,
            "v1_reference_after": v1_after,
            "v1_reference_stable": v1_stable,
            "output_hashes_excluding_manifest": output_hashes,
            "results": results,
            "k3_report": [row for row in results if row.get("krylovdim") == 3],
        }
    )
    write_json(OUTPUT / "manifest.json", metadata)
    print(json.dumps(metadata, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if accepted and all_cases_gate_passed else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="执行剩余三个 Julia cell；默认仅打印 dry-run 命令",
    )
    args = parser.parse_args()
    reference = ed_reference()
    metadata = metadata_for_dry_run(reference)
    if not args.execute:
        print(json.dumps(metadata, ensure_ascii=False, indent=2, allow_nan=False))
        return
    raise SystemExit(run(reference, metadata))


if __name__ == "__main__":
    main()
