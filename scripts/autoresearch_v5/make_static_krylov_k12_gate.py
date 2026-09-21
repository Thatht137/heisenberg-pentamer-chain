#!/usr/bin/env python3
"""准备独立 k12 单点 release v3；只生成元数据并执行 batch dry-run。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
RUN_REL = Path("results/autoresearch_v5_20260920/static_krylov_k12_r1")
RELEASE_REL = Path("results/autoresearch_v5_20260920/static_krylov_controls_release_v3")
SMOKE_REL = Path("results/autoresearch_v5_20260920/static_krylov_k12_smoke_r1/a-0100-k12")
RELEASE_ID = "static-krylov-controls-release-v3"
RUN_ID = "pentamer-negative-alpha-static-krylov-k12-single-r1-20260920"
CELL_ID = "negdiag-a01000-b02500-L080-k12"
KRYLOV = 12
REMOTE_JULIA = "1.12.3"
SMOKE_JULIA = "1.11.5"
BATCH = SCRIPT_DIR / "run_negative_phase_structure_batch.py"
PREFLIGHT = SCRIPT_DIR / "static_krylov_k12_preflight.py"
LAUNCHER = SCRIPT_DIR / "launch_static_krylov_k12_release_v3.sh"
UPLOAD = SCRIPT_DIR / "upload_static_krylov_k12_release_v3.ps1"
STANDARD = ROOT / "docs/negative_alpha_practical_convergence_standard_20260829.md"
MANIFEST_TOML = ROOT / "Manifest.toml"
SMOKE_ARTIFACTS = (
    "bond_bond_connected.csv",
    "bond_correlations.csv",
    "entropy_profile_full.csv",
    "metrics.csv",
    "schmidt_spectrum.csv",
    "state_sz0.jld2",
    "string_profile.csv",
    "structure_factor_fullq.csv",
    "sweep_history_sz0.csv",
    "sweep_history_sz1.csv",
)
SOURCE_FILES = (
    "Project.toml",
    "Manifest.toml",
    "docs/negative_alpha_practical_convergence_standard_20260829.md",
    "src/PentamerChain.jl",
    "src/hamiltonian.jl",
    "src/order_parameters.jl",
    "src/utils.jl",
    "src/exact_diag.jl",
    "src/dmrg_solver.jl",
    "src/spectral.jl",
    "scripts/autoresearch_v5/progress.py",
    "scripts/autoresearch_v5/negative_dmrg_options.py",
    "scripts/autoresearch_v5/negative_static_cell.jl",
    "scripts/autoresearch_v5/run_negative_static_cell.py",
    "scripts/autoresearch_v5/run_negative_phase_structure_cell.py",
    "scripts/autoresearch_v5/run_negative_phase_structure_batch.py",
    "scripts/autoresearch_v5/validate_negative_phase_run_practical_v2.py",
    "scripts/autoresearch_v5/static_krylov_supervisor.py",
    "scripts/autoresearch_v5/test_static_krylov_supervisor.py",
    "scripts/autoresearch_v5/static_krylov_k12_preflight.py",
    "scripts/autoresearch_v5/launch_static_krylov_k12_release_v3.sh",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    if path.exists():
        raise FileExistsError(f"拒绝覆盖：{path}")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _finite(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} 不是数值") from error
    if not math.isfinite(result):
        raise ValueError(f"{label} 不是有限数")
    return result


def _exact(value: Any, expected: int, label: str) -> None:
    if abs(_finite(value, label) - expected) > 0.0:
        raise ValueError(f"{label} 不匹配：{value!r} != {expected}")


def settings() -> dict[str, Any]:
    return {
        "method": "finite_dmrg_multistart_saved_state_enriched",
        "boundary": "OBC",
        "sectors": ["Sz=0", "Sz=1"],
        "maxdim_by_L": {"80": 1200},
        "nsweeps": 64,
        "cutoff": 1e-11,
        "threads": 8,
        "q_count": 401,
        "init_modes": ["center", "ferro_j2"],
        "noise_profile": "legacy",
        "random_seed": 20260811,
        "variance_per_site_max": 5e-8,
        "save_state": True,
        "enriched_diagnostics": True,
        "eigsolve_krylovdim": KRYLOV,
        "eigsolve_maxiter": 1,
        "eigsolve_tol": 1e-14,
        "warmstart": False,
        "retry_policy": "none",
        "maxdim_escalation": False,
        "execution": "prepared_only; concurrency=1; stop on first failed cell",
    }


def future_output_contract() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "parent": {
            "cell_id": CELL_ID,
            "required_status": "success",
            "required_accepted": True,
            "required_krylovdim": KRYLOV,
            "required_modes": ["center", "ferro_j2"],
            "required_sectors": ["Sz=0", "Sz=1"],
        },
        "children": {
            "modes": ["center", "ferro_j2"],
            "required_status": "success",
            "required_accepted": True,
            "required_krylovdim": KRYLOV,
            "required_sectors": ["Sz=0", "Sz=1"],
            "required_sweeps": 64,
        },
    }


def smoke_evidence() -> dict[str, Any]:
    directory = ROOT / SMOKE_REL
    if not directory.is_dir():
        raise FileNotFoundError(directory)
    for name in SMOKE_ARTIFACTS:
        path = directory / name
        if not path.is_file() or path.stat().st_size <= 0:
            raise FileNotFoundError(path)
    rows: dict[str, str] = {}
    with (directory / "metrics.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if set(row) != {"metric", "value"} or row["metric"] in rows:
                raise ValueError("k12 smoke metrics 格式错误")
            rows[row["metric"]] = row["value"]
    for key, expected in {
        "alpha": -0.1, "beta": 0.25, "n_units": 2, "L": 10,
        "structure_factor_q_count": 401, "eigsolve_krylovdim": KRYLOV,
        "eigsolve_maxiter": 1, "random_seed_base": 20260811,
        "nsweeps_requested": 16, "nsweeps_completed_sz0": 16, "nsweeps_completed_sz1": 16,
    }.items():
        _exact(rows.get(key), expected, f"smoke.{key}")
    if rows.get("noise_profile") != "legacy" or rows.get("init_mode_sz0") != "center" or rows.get("init_mode_sz1") != "center":
        raise ValueError("k12 smoke 初态/noise 不匹配")
    if rows.get("enriched_diagnostics") != "true":
        raise ValueError("k12 smoke 未开启 enriched diagnostics")
    return {
        "path": SMOKE_REL.as_posix(),
        "julia_version": SMOKE_JULIA,
        "role": "parser/execution evidence only",
        "not_remote_validation": True,
        "remote_julia_version_required": REMOTE_JULIA,
        "artifact_names": list(SMOKE_ARTIFACTS),
        "artifact_sha256": {name: sha256(directory / name) for name in SMOKE_ARTIFACTS},
        "metrics_checks": {"alpha": -0.1, "beta": 0.25, "L": 10, "eigsolve_krylovdim": KRYLOV, "q_count": 401},
    }


def validate_sources() -> dict[str, str]:
    records: dict[str, str] = {}
    for name in SOURCE_FILES:
        path = ROOT / name
        if not path.is_file():
            raise FileNotFoundError(path)
        records[name] = sha256(path)
    return records


def build_run_spec(source_records: dict[str, str], smoke: dict[str, Any]) -> dict[str, Any]:
    shared = settings()
    return {
        "schema_version": 3,
        "run_id": RUN_ID,
        "run_dir": RUN_REL.as_posix(),
        "scope": "single negative-alpha L80 k12 gate; audit_only preparation, no thermodynamic claim",
        "cells": [{
            "cell_id": CELL_ID,
            "params": {"alpha": -0.1, "beta": 0.25, "L": 80, "n_units": 16, "eigsolve_krylovdim": KRYLOV},
            "budget": 64,
            "stage": "static-krylov-k12-single-r1",
        }],
        "settings": shared,
        "future_output_contract": future_output_contract(),
        "acceptance": {
            "status": "prepared_only",
            "success_receipt": False,
            "required_files": ["state_sz0.jld2", "entropy_profile_full.csv", "bond_bond_connected.csv"],
            "no_warmstart": True,
            "no_128": True,
            "no_retry": True,
            "parent_child_k12_contract_required": True,
        },
        "provenance": {
            "negative_alpha_included": True,
            "source_commit": RELEASE_ID,
            "source_hashes_path": (RUN_REL / "source_hashes.sha256").as_posix(),
            "source_hashes": source_records,
            "smoke_evidence": smoke,
            "remote_launch": "not_started",
            "remote_julia_version_required": REMOTE_JULIA,
        },
    }


def validate_dry_rows(rows: list[dict[str, Any]]) -> None:
    if len(rows) != 1:
        raise ValueError(f"dry-run cell 数错误：{len(rows)}")
    argv = [str(item) for item in rows[0].get("command", [])]
    required = {
        "--maxdim": "1200", "--nsweeps": "64", "--cutoff": "1e-11", "--threads": "8",
        "--q-count": "401", "--eigsolve-krylovdim": "12", "--init-modes": "center,ferro_j2",
        "--noise-profile": "legacy", "--random-seed": "20260811",
    }
    for flag, value in required.items():
        if flag not in argv or argv[argv.index(flag) + 1] != value:
            raise ValueError(f"dry-run {flag} 配置错误")
    if "--save-state" not in argv or "--enriched-diagnostics" not in argv:
        raise ValueError("dry-run 缺保存态或 enriched")
    if "128" in " ".join(argv) or any("warm" in item.lower() or "retry" in item.lower() for item in argv):
        raise ValueError("dry-run 意外包含 128/warmstart/retry")


def run_dry_run(run_spec: Path) -> tuple[list[dict[str, Any]], list[str]]:
    command = [
        sys.executable, str(BATCH), "--run-spec", str(run_spec), "--outdir", str(run_spec.parent),
        "--standard-sha256", sha256(STANDARD), "--expected-manifest-sha256", sha256(MANIFEST_TOML),
        "--expected-julia-version", REMOTE_JULIA, "--source-commit", RELEASE_ID,
        "--julia", "auto", "--dry-run",
    ]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    rows = [json.loads(line) for line in result.stdout.splitlines() if line.strip().startswith("{")]
    if result.returncode != 0 or not result.stdout.rstrip().endswith("DRY_RUN_OK cells=1"):
        raise RuntimeError(f"dry-run 失败：rc={result.returncode}; stdout={result.stdout}; stderr={result.stderr}")
    validate_dry_rows(rows)
    return rows, command


def _entry(path: Path) -> dict[str, Any]:
    return {"path": path.as_posix(), "sha256": sha256(ROOT / path), "bytes": (ROOT / path).stat().st_size}


def build_manifest(run_spec: dict[str, Any], source_records: dict[str, str], smoke: dict[str, Any], run_files: list[str]) -> dict[str, Any]:
    paths = [RUN_REL / name for name in run_files]
    paths.extend(Path(name) for name in SOURCE_FILES)
    paths.extend(SMOKE_REL / name for name in SMOKE_ARTIFACTS)
    entries = [_entry(path) for path in paths]
    return {
        "schema_version": 3,
        "release_id": RELEASE_ID,
        "release_version": 3,
        "status": "prepared_only",
        "launch_ready": False,
        "target": "/home/wangjieren/releases/1x5_Heisenberg_Pentamer/static_krylov_controls_release_v3",
        "remote_run_dir": RUN_REL.as_posix(),
        "bundle_source_hashes_path": (RUN_REL / "source_hashes.sha256").as_posix(),
        "control_path": (RELEASE_REL / "server_upload_manifest.json").as_posix(),
        "cell_count": 1,
        "concurrency": 1,
        "stop_on_first_failure": True,
        "retry_policy": "none",
        "krylovdim": KRYLOV,
        "expected_remote_julia_version": REMOTE_JULIA,
        "smoke_evidence": smoke,
        "future_output_contract": run_spec["future_output_contract"],
        "files": entries,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=ROOT / RUN_REL)
    parser.add_argument("--release-dir", type=Path, default=ROOT / RELEASE_REL)
    args = parser.parse_args(argv)
    run = args.run_dir.resolve()
    release = args.release_dir.resolve()
    results_root = (ROOT / "results").resolve()
    for directory in (run, release):
        try:
            directory.relative_to(results_root)
        except ValueError as error:
            raise ValueError("输出目录必须位于 results 下") from error
        if directory.exists() and any(directory.iterdir()):
            raise FileExistsError(f"拒绝覆盖非空目录：{directory}")
    if not BATCH.is_file() or not STANDARD.is_file() or not MANIFEST_TOML.is_file():
        raise FileNotFoundError("缺少 batch/标准/Manifest 输入")
    smoke = smoke_evidence()
    source_records = validate_sources()
    run.mkdir(parents=True, exist_ok=True)
    release.mkdir(parents=True, exist_ok=True)
    run_rel = run.relative_to(ROOT).as_posix()
    if run_rel != RUN_REL.as_posix() or release.relative_to(ROOT).as_posix() != RELEASE_REL.as_posix():
        raise ValueError("k12 release 输出路径必须保持 versioned 固定路径")
    spec = build_run_spec(source_records, smoke)
    write_json(run / "axes.json", {"alpha": [-0.1], "beta": [0.25], "L": [80], "eigsolve_krylovdim": [KRYLOV]})
    write_json(run / "parameter-scan.run_spec.json", spec)
    write_json(run / "settings.json", spec["settings"])
    write_json(run / "provenance.json", spec["provenance"])
    (run / "source_hashes.sha256").write_text("".join(f"{digest}  {name}\n" for name, digest in sorted(source_records.items())), encoding="utf-8")
    spec_sha = sha256(run / "parameter-scan.run_spec.json")
    source_sha = sha256(run / "source_hashes.sha256")
    contract = {
        "schema_version": 3,
        "release_id": RELEASE_ID,
        "status": "prepared_only",
        "launch_ready": False,
        "dry_run_only": True,
        "cell_count": 1,
        "concurrency": 1,
        "stop_on_first_failure": True,
        "retry_policy": "none",
        "run_spec_sha256": spec_sha,
        "source_hashes_sha256": source_sha,
        "eigsolve_krylovdim": KRYLOV,
        "expected_remote_julia_version": REMOTE_JULIA,
        "smoke_julia_version": SMOKE_JULIA,
        "smoke_not_remote_validation": True,
        "future_output_contract": spec["future_output_contract"],
    }
    write_json(run / "launch-contract.json", contract)
    rows, dry_command = run_dry_run(run / "parameter-scan.run_spec.json")
    (run / "dry_run_command.txt").write_text(subprocess.list2cmdline([str(item) for item in dry_command]) + "\n", encoding="utf-8")
    (run / "dry_run.stdout.txt").write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\nDRY_RUN_OK cells=1\n", encoding="utf-8")
    (run / "README.md").write_text(
        "# static_krylov_k12_r1\n\n"
        "仅本地 prepared_only 与 batch dry-run；未启动 Julia、SSH、上传或远端任务。\n\n"
        "单点 alpha=-0.1、beta=0.25、L=80、n_units=16、Krylov=12；64 sweeps、maxdim=1200、cutoff=1e-11、threads=8、q_count=401；Sz=0/1，center 与 ferro_j2，保存 state 与 enriched diagnostics。\n\n"
        "L10 smoke 证据路径：" + SMOKE_REL.as_posix() + "；该证据仅用于 parser/execution gate，声明 Julia 1.11.5，不替代远端要求 Julia 1.12.3。\n",
        encoding="utf-8",
    )
    run_files = [
        "axes.json", "dry_run.stdout.txt", "dry_run_command.txt", "input_hashes.json",
        "launch-contract.json", "parameter-scan.run_spec.json", "provenance.json", "README.md",
        "settings.json", "source_hashes.sha256",
    ]
    input_records = [{"path": name, "sha256": digest, "role": "code"} for name, digest in sorted(source_records.items())]
    input_records.extend({"path": (SMOKE_REL / name).as_posix(), "sha256": digest, "role": "smoke_evidence"} for name, digest in smoke["artifact_sha256"].items())
    input_records.extend({"path": (RUN_REL / name).as_posix(), "sha256": sha256(run / name), "role": "prepared_output"} for name in run_files if name != "input_hashes.json")
    write_json(run / "input_hashes.json", {"schema_version": 1, "status": "prepared_only", "records": input_records})
    manifest = build_manifest(spec, source_records, smoke, run_files)
    write_json(release / "server_upload_manifest.json", manifest)
    preflight_command = [sys.executable, str(PREFLIGHT), "--mode", "prepare", "--manifest", str(release / "server_upload_manifest.json"), "--root", str(ROOT), "--json"]
    preflight_result = subprocess.run(preflight_command, cwd=ROOT, capture_output=True, text=True, check=False)
    if preflight_result.returncode != 0:
        raise RuntimeError(f"k12 preflight 失败：{preflight_result.stdout}\n{preflight_result.stderr}")
    write_json(run / "preflight.json", json.loads(preflight_result.stdout))
    print(json.dumps({"status": "prepared_only", "run": RUN_REL.as_posix(), "release": RELEASE_REL.as_posix(), "release_id": RELEASE_ID, "cell_id": CELL_ID, "krylovdim": KRYLOV, "dry_run": "DRY_RUN_OK cells=1", "smoke_julia": SMOKE_JULIA, "remote_julia_required": REMOTE_JULIA, "payload_files": len(manifest["files"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
