#!/usr/bin/env python3
"""准备修复后 Julia 源码对应的 Krylov=8 对照包；只做本地 dry-run。"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_RUN_REL = "results/autoresearch_v5_20260919/static_krylov_controls_r2"
R1_REL = "results/autoresearch_v5_20260919/static_krylov_controls_r1"
DEFAULT_PLAN = ROOT / R1_REL / "harness_parameter_scan_preflight" / "run_spec.json"
BATCH = SCRIPT_DIR / "run_negative_phase_structure_batch.py"
STANDARD = ROOT / "docs/negative_alpha_practical_convergence_standard_20260829.md"
AUDIT = ROOT / "results/autoresearch_v5_20260913/negative_phase_independent_audit_v6/summary.json"
PARAMETER_SCAN = Path(r"C:\Users\hh250\code\quantum.harness\scripts\parameter_scan.py")
JULIA_SOURCE = "scripts/autoresearch_v5/negative_static_cell.jl"
TEST_SOURCE = "scripts/autoresearch_v5/test_negative_static_cell_args.jl"

sys.path.insert(0, str(SCRIPT_DIR))
from make_negative_phase_independent_pilot import SOURCES as PILOT_SOURCES  # noqa: E402


AXES = {"alpha": [-0.1, -0.175], "beta": [0.25], "L": [80], "eigsolve_krylovdim": [8]}
SRC_DEPENDENCIES = (
    "src/utils.jl",
    "src/exact_diag.jl",
    "src/dmrg_solver.jl",
    "src/spectral.jl",
)
EXPECTED_SETTINGS = {
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
    "eigsolve_krylovdim": 8,
    "eigsolve_maxiter": 1,
    "eigsolve_tol": 1e-14,
    "warmstart": False,
    "retry_policy": "none",
    "maxdim_escalation": False,
    "execution": "prepared_only; concurrency=1; stop on first failed cell",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    if path.exists():
        raise FileExistsError(f"拒绝覆盖：{path}")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def exact_int(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} 不得为 bool")
    if type(value) is int:
        return value
    if type(value) is float and math.isfinite(value) and value.is_integer():
        return int(value)
    raise ValueError(f"{label} 必须是整数值")


def source_names() -> tuple[str, ...]:
    names = list(dict.fromkeys((*PILOT_SOURCES, *SRC_DEPENDENCIES, str(Path(__file__).relative_to(ROOT)).replace("\\", "/"))))
    return tuple(names)


def validation_names() -> tuple[str, ...]:
    names = list(source_names())
    if TEST_SOURCE not in names:
        names.append(TEST_SOURCE)
    return tuple(names)


def validate_sources(names: tuple[str, ...]) -> dict[str, str]:
    records: dict[str, str] = {}
    for name in names:
        path = ROOT / name
        if not path.is_file():
            raise FileNotFoundError(path)
        records[name] = sha256(path)
    return records


def load_harness_plan(path: Path) -> dict[str, Any]:
    if not PARAMETER_SCAN.is_file():
        raise FileNotFoundError(f"缺少 harness plan 工具：{PARAMETER_SCAN}")
    if not path.is_file():
        raise FileNotFoundError(f"缺少已生成 harness run-spec：{path}")
    plan = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(plan, dict) or not isinstance(plan.get("cells"), list):
        raise ValueError("harness run-spec 必须包含 cells 列表")
    if plan.get("settings") != EXPECTED_SETTINGS:
        raise ValueError("harness run-spec shared settings 与 r2 协议不一致")
    expected = {(-0.1, 0.25, 80, 8), (-0.175, 0.25, 80, 8)}
    observed = set()
    for cell in plan["cells"]:
        if not isinstance(cell, dict) or not isinstance(cell.get("params"), dict):
            raise ValueError("harness cell 缺少 params")
        params = cell["params"]
        alpha = float(params.get("alpha"))
        beta = float(params.get("beta"))
        length = exact_int(params.get("L"), "L")
        krylov = exact_int(params.get("eigsolve_krylovdim"), "eigsolve_krylovdim")
        if not math.isfinite(alpha) or not math.isfinite(beta):
            raise ValueError("harness alpha/beta 必须有限")
        observed.add((alpha, beta, length, krylov))
    if observed != expected or len(plan["cells"]) != 2:
        raise ValueError(f"harness cell 映射不匹配：{sorted(observed)}")
    return plan


def token(alpha: float) -> str:
    return f"{round(abs(alpha) * 10000):05d}"


def build_cells(plan: dict[str, Any]) -> list[dict[str, Any]]:
    cells = []
    for cell in plan["cells"]:
        params = cell["params"]
        alpha = float(params["alpha"])
        beta = float(params["beta"])
        length = exact_int(params["L"], "L")
        krylov = exact_int(params["eigsolve_krylovdim"], "eigsolve_krylovdim")
        if length != 80 or length % 5 or beta != 0.25 or krylov != 8:
            raise ValueError("cell 不满足固定 r2 对照协议")
        cells.append(
            {
                "cell_id": f"negdiag-a{token(alpha)}-b{token(beta)}-L{length:03d}-k{krylov:02d}",
                "params": {"alpha": alpha, "beta": beta, "L": length, "n_units": length // 5, "eigsolve_krylovdim": krylov},
                "budget": 64,
                "stage": "static-krylov-controls-r2",
            }
        )
    if len(cells) != 2:
        raise ValueError("r2 必须正好包含两个 cell")
    return cells


def validate_dry_rows(rows: list[dict[str, Any]]) -> None:
    if len(rows) != 2:
        raise ValueError(f"dry-run cell 数错误：{len(rows)}")
    required = {
        "--maxdim": "1200",
        "--nsweeps": "64",
        "--cutoff": "1e-11",
        "--threads": "8",
        "--q-count": "401",
        "--eigsolve-krylovdim": "8",
        "--init-modes": "center,ferro_j2",
        "--noise-profile": "legacy",
        "--random-seed": "20260811",
    }
    seen: set[str] = set()
    for row in rows:
        cell_id = str(row.get("cell_id"))
        if cell_id in seen:
            raise ValueError(f"dry-run cell 重复：{cell_id}")
        seen.add(cell_id)
        argv = [str(item) for item in row.get("command", [])]
        for flag, value in required.items():
            if flag not in argv or argv[argv.index(flag) + 1] != value:
                raise ValueError(f"{cell_id} {flag} 配置错误")
        if "--save-state" not in argv or "--enriched-diagnostics" not in argv:
            raise ValueError(f"{cell_id} 缺保存态或增强观测")
        if "128" in " ".join(argv) or any("warm" in item.lower() or "retry" in item.lower() for item in argv):
            raise ValueError(f"{cell_id} 意外包含 128/warmstart/retry")


def run_dry_run(run_spec: Path, outdir: Path, manifest_sha: str, standard_sha: str) -> tuple[list[dict[str, Any]], list[str]]:
    command = [
        sys.executable, str(BATCH), "--run-spec", str(run_spec), "--outdir", str(outdir),
        "--standard-sha256", standard_sha, "--expected-manifest-sha256", manifest_sha,
        "--expected-julia-version", "1.12.3", "--source-commit", "static-krylov-controls-r2-prepared",
        "--julia", "auto", "--dry-run",
    ]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    rows = [json.loads(line) for line in result.stdout.splitlines() if line.strip().startswith("{")]
    if result.returncode != 0 or not result.stdout.rstrip().endswith("DRY_RUN_OK cells=2"):
        raise RuntimeError(f"dry-run 失败：rc={result.returncode}; stdout={result.stdout}; stderr={result.stderr}")
    validate_dry_rows(rows)
    return rows, command


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harness-plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--outdir", type=Path, default=ROOT / DEFAULT_RUN_REL)
    parser.add_argument("--run-id", default="pentamer-negative-alpha-static-krylov-controls-r2-20260919")
    args = parser.parse_args(argv)
    run = args.outdir.resolve()
    results_root = (ROOT / "results").resolve()
    try:
        run.relative_to(results_root)
    except ValueError as error:
        raise ValueError("输出目录必须位于 results 下") from error
    if run.exists() and any(run.iterdir()):
        raise FileExistsError(f"拒绝覆盖非空目录：{run}")
    if not BATCH.is_file() or not STANDARD.is_file() or not AUDIT.is_file():
        raise FileNotFoundError("缺少 batch/标准/审计输入")
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    if audit.get("verdict") != "new_thermodynamic_phase_not_confirmed":
        raise ValueError("负区审计状态不匹配")

    harness_plan_path = args.harness_plan.resolve()
    harness_plan = load_harness_plan(harness_plan_path)
    cells = build_cells(harness_plan)
    code_hashes = validate_sources(source_names())
    validation_hashes = validate_sources(validation_names())
    manifest_sha = sha256(ROOT / "Manifest.toml")
    standard_sha = sha256(STANDARD)
    plan_backend = {
        "requested": "quantum.harness/scripts/parameter_scan.py plan",
        "path": str(PARAMETER_SCAN),
        "available": True,
        "sha256": sha256(PARAMETER_SCAN),
        "input_run_spec": str(harness_plan_path),
        "input_run_spec_sha256": sha256(harness_plan_path),
        "schema": "existing harness run-spec consumed; no manual enumeration",
    }
    provenance = {
        "negative_alpha_included": True,
        "phase_label_assigned": False,
        "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip(),
        "git_dirty": bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()),
        "standard_sha256": standard_sha,
        "audit_sha256": sha256(AUDIT),
        "manifest_sha256": manifest_sha,
        "code_sha256": code_hashes,
        "validation_source_sha256": validation_hashes,
        "julia_parse_fix_source": JULIA_SOURCE,
        "julia_parse_fix_sha256": code_hashes[JULIA_SOURCE],
        "parameter_plan_backend": plan_backend,
        "remote_launch": "not_started",
    }
    run_rel = str(run.relative_to(ROOT)).replace("\\", "/")
    run_spec = {
        "schema_version": 2,
        "run_id": args.run_id,
        "run_dir": run_rel,
        "scope": "two existing negative-alpha L80 points; Krylov 3->8 control after enriched parser fix",
        "cells": cells,
        "settings": EXPECTED_SETTINGS,
        "acceptance": {
            "status": "prepared_only",
            "success_receipt": False,
            "required_files": ["state_sz0.jld2", "entropy_profile_full.csv", "bond_bond_connected.csv"],
            "no_warmstart": True,
            "no_128": True,
            "no_retry": True,
            "enriched_parser_fix_required": True,
        },
        "provenance": provenance,
    }
    run.mkdir(parents=True)
    write_json(run / "axes.json", AXES)
    write_json(run / "parameter-scan.run_spec.json", run_spec)
    write_json(run / "settings.json", EXPECTED_SETTINGS)
    write_json(run / "provenance.json", provenance)
    (run / "source_hashes.sha256").write_text("".join(f"{digest}  {name}\n" for name, digest in code_hashes.items()), encoding="utf-8")
    spec_sha = sha256(run / "parameter-scan.run_spec.json")
    source_sha = sha256(run / "source_hashes.sha256")
    contract = {
        "schema_version": 2,
        "status": "prepared_only",
        "launch_ready": False,
        "dry_run_only": True,
        "cell_count": 2,
        "concurrency": 1,
        "stop_on_first_failure": True,
        "retry_policy": "none",
        "run_spec_sha256": spec_sha,
        "source_hashes_sha256": source_sha,
        "julia_parse_fix_sha256": code_hashes[JULIA_SOURCE],
        "include_dependencies": list(SRC_DEPENDENCIES),
    }
    write_json(run / "launch-contract.json", contract)
    rows, dry_command = run_dry_run(run / "parameter-scan.run_spec.json", run, manifest_sha, standard_sha)
    (run / "dry_run_command.txt").write_text(subprocess.list2cmdline([str(item) for item in dry_command]) + "\n", encoding="utf-8")
    (run / "dry_run.stdout.txt").write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\nDRY_RUN_OK cells=2\n", encoding="utf-8")
    preflight = {
        "schema_version": 2,
        "status": "prepared_only",
        "launch_started": False,
        "cell_count": 2,
        "dry_run_returncode": 0,
        "dry_run_cells": len(rows),
        "checks": {
            "harness_plan_consumed": True,
            "two_cells": len(rows) == 2,
            "argv_krylov8": True,
            "nsweeps_64": True,
            "maxdim_1200": True,
            "save_state_and_enriched": True,
            "julia_parser_fix_recorded": True,
            "include_dependencies_hashed": all(name in code_hashes for name in SRC_DEPENDENCIES),
            "single_concurrency_stop_first": True,
            "no_warmstart_128_retry": True,
        },
        "parameter_plan": plan_backend,
    }
    write_json(run / "preflight.json", preflight)
    input_records = [{"path": name, "sha256": digest, "role": "code"} for name, digest in code_hashes.items()]
    input_records.append({"path": TEST_SOURCE, "sha256": validation_hashes[TEST_SOURCE], "role": "validation_only"})
    input_records.extend({"path": f"{run_rel}/{name}", "sha256": sha256(run / name), "role": "prepared_output"} for name in ("parameter-scan.run_spec.json", "source_hashes.sha256", "launch-contract.json"))
    write_json(run / "input_hashes.json", {"schema_version": 1, "status": "prepared_only", "records": input_records})
    (run / "README.md").write_text(
        "# static_krylov_controls_r2\n\n"
        "仅本地准备与 batch dry-run；未启动 Julia、SSH 或远端上传。r1 历史目录不变。\n\n"
        "两 cell：alpha=-0.1、-0.175，beta=0.25，L=80/n_units=16；Sz=0/1，center 与 ferro_j2，64 sweeps，maxdim=1200，cutoff=1e-11，legacy noise，Krylov=8，maxiter=1，tol=1e-14，保存 state 与 enriched diagnostics。\n\n"
        f"本版本记录 enriched 解析修复 {JULIA_SOURCE} SHA256={code_hashes[JULIA_SOURCE]}；依赖补齐：" + ", ".join(SRC_DEPENDENCIES) + "。实际 harness plan 来源与哈希见 provenance.json。\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "prepared_only", "run": run_rel, "cells": 2, "dry_run": "DRY_RUN_OK cells=2", "julia_parse_fix_sha256": code_hashes[JULIA_SOURCE], "source_count": len(code_hashes), "validation_source_count": len(validation_hashes)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
