#!/usr/bin/env python3
"""准备 L80 Krylov=8 对照输入；只生成计划，不启动计算。"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
RUN_REL = "results/autoresearch_v5_20260919/static_krylov_controls_r1"
RUN = ROOT / RUN_REL
PILOT_SCRIPT = SCRIPT_DIR / "make_negative_phase_independent_pilot.py"
BATCH_SCRIPT = SCRIPT_DIR / "run_negative_phase_structure_batch.py"
HELPER = "scripts/autoresearch_v5/negative_dmrg_options.py"
MAKER = "scripts/autoresearch_v5/make_static_krylov_controls.py"
STANDARD = ROOT / "docs/negative_alpha_practical_convergence_standard_20260829.md"
AUDIT = ROOT / "results/autoresearch_v5_20260913/negative_phase_independent_audit_v6/summary.json"
PARAMETER_SCAN = Path(r"C:\Users\hh250\code\quantum.harness\scripts\parameter_scan.py")

sys.path.insert(0, str(SCRIPT_DIR))
from make_negative_phase_independent_pilot import (  # noqa: E402
    SOURCES as PILOT_SOURCES,
)


AXES: dict[str, list[float | int]] = {
    "alpha": [-0.1, -0.175],
    "beta": [0.25],
    "L": [80],
    "eigsolve_krylovdim": [8],
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload: object) -> None:
    if path.exists():
        raise FileExistsError(f"拒绝覆盖：{path}")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def token(alpha: float) -> str:
    return f"{round(abs(alpha) * 10000):05d}"


def source_names() -> tuple[str, ...]:
    names = list(dict.fromkeys((*PILOT_SOURCES, MAKER)))
    if HELPER not in names:
        raise ValueError("主 pilot SOURCES 缺少 negative_dmrg_options.py")
    return tuple(names)


def validate_sources(names: Iterable[str] | None = None) -> dict[str, str]:
    selected = tuple(names) if names is not None else source_names()
    if HELPER not in selected:
        raise ValueError("输入依赖缺少 negative_dmrg_options.py，拒绝生成")
    records: dict[str, str] = {}
    for name in selected:
        path = ROOT / name
        if not path.is_file():
            raise FileNotFoundError(path)
        records[name] = sha256(path)
    return records


def load_harness_plan(path: Path) -> dict[str, Any]:
    if not PARAMETER_SCAN.is_file():
        raise FileNotFoundError(f"缺少 harness plan 工具，拒绝降级：{PARAMETER_SCAN}")
    if not path.is_file():
        raise FileNotFoundError(f"缺少 harness run-spec：{path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("cells"), list):
        raise ValueError("harness run-spec 必须包含 cells 列表")
    expected = {
        (float(alpha), float(beta), int(length), int(krylovdim))
        for alpha, beta, length, krylovdim in itertools.product(
            AXES["alpha"], AXES["beta"], AXES["L"], AXES["eigsolve_krylovdim"]
        )
    }
    observed = []
    for cell in payload["cells"]:
        params = cell.get("params") if isinstance(cell, dict) else None
        if not isinstance(params, dict):
            raise ValueError("harness cell 缺少 params")
        if isinstance(params.get("L"), bool) or isinstance(params.get("eigsolve_krylovdim"), bool):
            raise ValueError("harness L/Krylov 不得为 bool")
        try:
            observed.append((float(params["alpha"]), float(params["beta"]), int(params["L"]), int(params["eigsolve_krylovdim"])))
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("harness cell 参数不完整") from error
    if len(observed) != len(expected) or set(observed) != expected:
        raise ValueError(f"harness cell 映射不匹配：observed={observed}, expected={sorted(expected)}")
    return payload


def build_cells_from_harness(plan: dict[str, Any]) -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = []
    for cell in plan["cells"]:
        params = cell["params"]
        alpha = float(params["alpha"])
        beta = float(params["beta"])
        length = int(params["L"])
        krylovdim = int(params["eigsolve_krylovdim"])
        if length % 5 != 0:
            raise ValueError("cell 参数不满足负区 L=5*n_units 约束")
        cells.append(
            {
                "cell_id": f"negdiag-a{token(alpha)}-b{token(beta)}-L{length:03d}-k{krylovdim:02d}",
                "params": {
                    "alpha": alpha,
                    "beta": beta,
                    "L": length,
                    "n_units": length // 5,
                    "eigsolve_krylovdim": krylovdim,
                },
                "budget": 64,
                "stage": "static-krylov-controls-r1",
            }
        )
    if len(cells) != 2:
        raise AssertionError(f"应有 2 个 cells，实际 {len(cells)}")
    return cells


def validate_harness_settings(plan: dict[str, Any], expected: dict[str, Any]) -> None:
    observed = plan.get("settings")
    if not isinstance(observed, dict):
        raise ValueError("harness run-spec 缺少 shared settings，拒绝生成")
    if observed != expected:
        raise ValueError("harness shared settings 与控制协议不一致")


def git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def validate_dry_run_rows(rows: list[dict[str, Any]]) -> None:
    if len(rows) != 2:
        raise ValueError(f"dry-run cell 数错误：{len(rows)}")
    seen: set[str] = set()
    for row in rows:
        cell_id = str(row.get("cell_id"))
        if cell_id in seen:
            raise ValueError(f"dry-run cell 重复：{cell_id}")
        seen.add(cell_id)
        argv = list(row.get("command", []))
        if "--eigsolve-krylovdim" not in argv:
            raise ValueError(f"{cell_id} 缺显式 Krylov 参数")
        index = argv.index("--eigsolve-krylovdim")
        if index + 1 >= len(argv) or argv[index + 1] != "8":
            raise ValueError(f"{cell_id} Krylov 参数不是 8")
        expected = {
            "--maxdim": "1200",
            "--nsweeps": "64",
            "--cutoff": "1e-11",
            "--init-modes": "center,ferro_j2",
            "--noise-profile": "legacy",
        }
        for flag, value in expected.items():
            if flag not in argv or argv[argv.index(flag) + 1] != value:
                raise ValueError(f"{cell_id} {flag} 配置错误")
        if "--save-state" not in argv or "--enriched-diagnostics" not in argv:
            raise ValueError(f"{cell_id} 缺保存态或增强观测")
        if "128" in " ".join(argv) or any("warm" in item.lower() or "retry" in item.lower() for item in argv):
            raise ValueError(f"{cell_id} 意外包含 128/warmstart/retry")


def run_dry_run(run_spec: Path, manifest_sha256: str) -> tuple[list[dict[str, Any]], list[str], int]:
    command = [
        sys.executable,
        str(BATCH_SCRIPT),
        "--run-spec",
        str(run_spec),
        "--outdir",
        str(RUN),
        "--standard-sha256",
        sha256(STANDARD),
        "--expected-manifest-sha256",
        manifest_sha256,
        "--expected-julia-version",
        "1.12.3",
        "--source-commit",
        "static-krylov-controls-r1-prepared",
        "--julia",
        "auto",
        "--dry-run",
    ]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    rows: list[dict[str, Any]] = []
    for line in lines:
        if line.startswith("{"):
            rows.append(json.loads(line))
    if result.returncode != 0 or not lines or not lines[-1].startswith("DRY_RUN_OK cells=2"):
        raise RuntimeError(f"dry-run 失败：rc={result.returncode}; stdout={result.stdout}; stderr={result.stderr}")
    validate_dry_run_rows(rows)
    return rows, command, result.returncode


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harness-plan", required=True, type=Path, help="harness parameter_scan.py 生成的 run_spec.json")
    args = parser.parse_args(argv)
    if RUN.exists():
        raise FileExistsError(f"拒绝覆盖已有目录：{RUN}")
    if not PILOT_SCRIPT.is_file() or not BATCH_SCRIPT.is_file():
        raise FileNotFoundError("缺少主 pilot 或 batch 构建器")
    if not STANDARD.is_file() or not AUDIT.is_file():
        raise FileNotFoundError("缺少收敛标准或负区审计输入")
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    if audit.get("verdict") != "new_thermodynamic_phase_not_confirmed":
        raise ValueError("负区审计状态不匹配，拒绝准备新批次")

    source_hashes = validate_sources()
    harness_plan_path = args.harness_plan.resolve()
    harness_plan = load_harness_plan(harness_plan_path)
    manifest_sha256 = sha256(ROOT / "Manifest.toml")
    standard_sha256 = sha256(STANDARD)
    settings: dict[str, Any] = {
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
    validate_harness_settings(harness_plan, settings)
    cells = build_cells_from_harness(harness_plan)
    plan_backend = {
        "requested": "quantum.harness/scripts/parameter_scan.py plan",
        "path": str(PARAMETER_SCAN),
        "available": True,
        "sha256": sha256(PARAMETER_SCAN),
        "input_run_spec": str(harness_plan_path),
        "input_run_spec_sha256": sha256(harness_plan_path),
        "schema": "harness generic run_spec -> consumer cell metadata mapping",
    }
    provenance = {
        "negative_alpha_included": True,
        "phase_label_assigned": False,
        "source_commit": git_head(),
        "git_dirty": bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()),
        "standard_sha256": standard_sha256,
        "audit_sha256": sha256(AUDIT),
        "manifest_sha256": manifest_sha256,
        "pilot_builder": str(PILOT_SCRIPT.relative_to(ROOT)).replace("\\", "/"),
        "code_sha256": source_hashes,
        "parameter_plan_backend": plan_backend,
        "remote_launch": "not_started",
    }
    plan = {
        "schema_version": 1,
        "run_id": "pentamer-negative-alpha-static-krylov-controls-r1-20260919",
        "run_dir": RUN_REL,
        "axes": AXES,
        "cells": cells,
        "generator": MAKER,
        "plan_backend": plan_backend,
    }
    run_spec = {
        "schema_version": 1,
        "run_id": plan["run_id"],
        "run_dir": RUN_REL,
        "scope": "two existing negative-alpha L80 points; Krylov 3->8 control only",
        "cells": cells,
        "settings": settings,
        "acceptance": {
            "status": "prepared_only",
            "success_receipt": False,
            "required_files": ["state_sz0.jld2", "entropy_profile_full.csv", "bond_bond_connected.csv"],
            "no_warmstart": True,
            "no_128": True,
            "no_retry": True,
        },
        "provenance": provenance,
    }

    RUN.mkdir(parents=True)
    write_json(RUN / "axes.json", AXES)
    write_json(RUN / "parameter-scan.plan.json", plan)
    write_json(RUN / "parameter-scan.run_spec.json", run_spec)
    write_json(RUN / "settings.json", settings)
    write_json(RUN / "provenance.json", provenance)
    (RUN / "source_hashes.sha256").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in source_hashes.items()), encoding="utf-8"
    )
    spec_hash = sha256(RUN / "parameter-scan.run_spec.json")
    source_hash_file_hash = sha256(RUN / "source_hashes.sha256")
    contract = {
        "schema_version": 1,
        "status": "prepared_only",
        "launch_ready": False,
        "dry_run_only": True,
        "cell_count": len(cells),
        "concurrency": 1,
        "stop_on_first_failure": True,
        "retry_policy": "none",
        "input_file_count": len(source_hashes) + 3,
        "run_spec_sha256": spec_hash,
        "source_hashes_sha256": source_hash_file_hash,
        "standard_sha256": standard_sha256,
        "manifest_sha256": manifest_sha256,
    }
    write_json(RUN / "launch-contract.json", contract)

    dry_rows, dry_command, dry_returncode = run_dry_run(RUN / "parameter-scan.run_spec.json", manifest_sha256)
    (RUN / "dry_run_command.txt").write_text(subprocess.list2cmdline([str(item) for item in dry_command]) + "\n", encoding="utf-8")
    (RUN / "dry_run.stdout.txt").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in dry_rows) + "\nDRY_RUN_OK cells=2\n",
        encoding="utf-8",
    )
    preflight = {
        "schema_version": 1,
        "status": "prepared_only",
        "launch_started": False,
        "cell_count": len(cells),
        "input_file_count": len(source_hashes) + 3,
        "source_hash_lines": len(source_hashes),
        "dry_run_returncode": dry_returncode,
        "dry_run_cells": len(dry_rows),
        "checks": {
            "two_cells": len(cells) == 2,
            "argv_krylov8": True,
            "nsweeps_64": True,
            "maxdim_1200": True,
            "save_state_and_enriched": True,
            "single_concurrency_stop_first": True,
            "no_warmstart_128_retry": True,
            "helper_in_sources": HELPER in source_hashes,
        },
        "parameter_plan": plan_backend,
    }
    write_json(RUN / "preflight.json", preflight)
    (RUN / "README.md").write_text(
        "# static_krylov_controls_r1\n\n"
        "本目录仅是本地准备结果，未启动 Julia、SSH 或远端上传。\n\n"
        "两 cell 为 alpha=-0.1、-0.175，beta=0.25、L=80；双初态 center/ferro_j2，Sz=0/1，64 sweeps，maxdim=1200，cutoff=1e-11，legacy noise，Krylov=8，maxiter=1，tol=1e-14。无 warmstart、128 晋级和 retry。\n\n"
        "历史 StageA/Rx 生成器未批量修改；在依赖预检完成前不能直接复用新 Krylov hook。当前主 pilot 的 SOURCES 已补入 negative_dmrg_options.py。\n\n"
        "未来生成必须传入 harness parameter_scan.py 已生成的 run_spec.json；准备器会 fail-closed 校验两 cell 映射与 shared settings。当前 r1 的 harness 审计证明见 harness_parameter_scan_preflight/schema_conversion.json。\n",
        encoding="utf-8",
    )

    upload_names = list(source_hashes) + [
        f"{RUN_REL}/parameter-scan.run_spec.json",
        f"{RUN_REL}/source_hashes.sha256",
        f"{RUN_REL}/launch-contract.json",
    ]
    if len(upload_names) != 18:
        raise AssertionError(f"预期 18 个输入文件，实际 {len(upload_names)}")
    write_json(
        RUN / "server_upload_manifest.json",
        {
            "schema_version": 1,
            "status": "prepared_only",
            "launch_allowed": False,
            "cell_count": len(cells),
            "concurrency": 1,
            "stop_on_first_failure": True,
            "files": [
                {"path": name, "sha256": sha256(ROOT / name), "bytes": (ROOT / name).stat().st_size}
                for name in upload_names
            ],
        },
    )
    print(json.dumps({"status": "prepared_only", "cells": len(cells), "input_files": len(upload_names), "dry_run": "DRY_RUN_OK cells=2", "launch_started": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
