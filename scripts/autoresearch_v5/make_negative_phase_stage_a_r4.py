#!/usr/bin/env python3
"""生成 Stage A R4 单元严格重试包。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results" / "autoresearch_v5_20260809" / "round44_phase_diagram_full_alpha"
STAGE = RUN / "stage-a-beta050-calibration-r4-a0250-L060"
R3_STAGE = RUN / "stage-a-beta050-calibration-r3-remaining13"
R3_SPEC = R3_STAGE / "parameter-scan.run_spec.json"
R3_INGEST = RUN / "phase-diagram-v2" / "r3_partial_ingestion_summary.json"
OBSERVATIONS = RUN / "phase-diagram-v2" / "observations.json"
STATE = RUN / "phase-diagram-v2" / "state.json"
STANDARD = ROOT / "docs" / "full_phase_diagram_negative_standard_20260809.md"
R3_CELL = "nega-r3-a0250-b0500-L060"
R4_CELL = "nega-r4-a0250-b0500-L060"
ACTION_ID = "act-bd120db6bdbc305ddf42"
TARGET_KEY = (-0.25, 0.5, 60)
SOURCE_FILES = [
    "Project.toml",
    "Manifest.toml",
    "docs/full_phase_diagram_negative_standard_20260809.md",
    "src/PentamerChain.jl",
    "src/hamiltonian.jl",
    "src/order_parameters.jl",
    "scripts/autoresearch_v5/progress.py",
    "scripts/autoresearch_v5/negative_static_cell.jl",
    "scripts/autoresearch_v5/run_negative_static_cell.py",
    "scripts/autoresearch_v5/run_negative_phase_structure_cell.py",
    "scripts/autoresearch_v5/run_negative_phase_structure_batch.py",
    "scripts/autoresearch_v5/validate_negative_phase_run.py",
]


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    handle, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    except BaseException:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass
        raise


def key(params: dict[str, Any]) -> tuple[float, float, int]:
    return float(params["alpha"]), float(params["beta"]), int(params["L"])


def discover_validation() -> Path:
    pattern = "stage-a-beta050-calibration-r3-remaining13-*/validation/summary.json"
    matches = sorted((RUN / "fetches").glob(pattern))
    if len(matches) != 1:
        raise ValueError(f"R3 validator summary 必须唯一，当前 {len(matches)} 个")
    return matches[0]


def target_cell() -> dict[str, Any]:
    spec = load(R3_SPEC)
    cells = spec.get("cells", [])
    matches = [cell for cell in cells if cell.get("cell_id") == R3_CELL]
    if len(cells) != 13 or len({cell.get("cell_id") for cell in cells}) != 13 or len(matches) != 1:
        raise ValueError("R3 run spec 身份或单元数不匹配")
    cell = matches[0]
    if (
        key(cell.get("params", {})) != TARGET_KEY
        or int(cell.get("budget", -1)) != 32
        or cell.get("controller_action_id") != ACTION_ID
        or bool(cell.get("calibration_only"))
    ):
        raise ValueError("R3 目标 cell 合同不匹配")
    return cell


def validate_r3(validation_path: Path, ingest_path: Path) -> None:
    validation = load(validation_path)
    rows = validation.get("rows")
    if (
        validation.get("status") != "fail"
        or validation.get("cell_count") != 3
        or validation.get("counts") != {"pass": 2, "fail": 1}
        or not isinstance(rows, list)
        or len(rows) != 3
    ):
        raise ValueError("R3 validator 必须严格为 2 pass / 1 fail")
    by_id = {str(row.get("cell_id")): row for row in rows}
    expected_pass = {"nega-r3-a0350-b0500-L080", "nega-r3-a0250-b0500-L040"}
    if set(by_id) != expected_pass | {R3_CELL}:
        raise ValueError("R3 validator cell 集合不匹配")
    for cell_id in expected_pass:
        row = by_id[cell_id]
        if row.get("validator_status") != "pass" or row.get("exit_code") != 0:
            raise ValueError(f"R3 pass 证据无效: {cell_id}")
    failed = by_id[R3_CELL]
    if failed.get("validator_status") != "fail" or failed.get("exit_code") != 1:
        raise ValueError("R3 目标失败证据无效")
    detail_path = Path(str(failed.get("output", "")))
    if not detail_path.is_file() or sha256(detail_path) != failed.get("sha256"):
        raise ValueError("R3 目标 validator 明细或哈希无效")
    detail = load(detail_path)
    if detail.get("cell_id") != R3_CELL or detail.get("status") != "fail":
        raise ValueError("R3 目标 validator 明细身份不匹配")
    failures = detail.get("failures", [])
    if not any("variance/site sz0 超门" in item for item in failures):
        raise ValueError("R3 目标失败原因不是声明的 Sz0 方差门")
    checks = detail.get("checks", {})
    if checks.get("terminal_acceptance") is not False or any(
        value is not True for name, value in checks.items() if name != "terminal_acceptance"
    ):
        raise ValueError("R3 目标失败证据含其他验收异常")

    ingest = load(ingest_path)
    counts = ingest.get("counts", {})
    expected_counts = {
        "fetched_terminal": 3,
        "validator_pass": 2,
        "validator_fail": 1,
        "controller_success_total": 9,
        "controller_failed_total": 1,
        "controller_pending_total": 6,
        "calibration_accepted_r3": 1,
    }
    if ingest.get("status") != "blocked_by_validation_failure" or any(
        counts.get(name) != value for name, value in expected_counts.items()
    ):
        raise ValueError("R3 accepted-only ingest 状态或计数不匹配")
    if ingest.get("failed_controller_keys") != [{"alpha": -0.25, "beta": 0.5, "L": 60}]:
        raise ValueError("R3 ingest 失败键不匹配")
    failure = ingest.get("failed_evidence", {})
    if failure.get("validator_status") != "fail" or failure.get("validator_sha256") != sha256(detail_path):
        raise ValueError("R3 ingest 未绑定目标 validator 明细")
    handoff_path = ROOT / str(ingest.get("source", {}).get("handoff_summary", ""))
    if not handoff_path.is_file() or sha256(handoff_path) != ingest.get("source", {}).get("handoff_summary_sha256"):
        raise ValueError("R3 ingest handoff 绑定无效")
    handoff = load(handoff_path)
    if handoff.get("validation_summary", {}).get("sha256") != sha256(validation_path):
        raise ValueError("R3 handoff 未绑定当前 validator summary")

    records = load(OBSERVATIONS).get("records", [])
    matched = [row for row in records if key(row.get("params", {})) == TARGET_KEY]
    if len(matched) != 1:
        raise ValueError("R3 controller 目标 observation 不唯一")
    record = matched[0]
    if record.get("status") != "failed" or record.get("controller_action_id") != ACTION_ID:
        raise ValueError("R3 controller 目标未记录为 declared failed")
    if "value" in record or "error" in record:
        raise ValueError("R3 failed observation 不得含 value/error")
    actions = {item.get("action_id"): item for item in load(STATE).get("actions", [])}
    action = actions.get(ACTION_ID)
    expected_spec = {
        "kind": "phase-diagram-cell",
        "params": {"alpha": -0.25, "beta": 0.5, "L": 60},
        "budget": 32,
    }
    if not action or action.get("state") != "REGISTERED" or action.get("spec") != expected_spec:
        raise ValueError("R4 未继承有效的 controller action")


def ensure_safe(refresh: bool) -> None:
    generated = [
        STAGE / "parameter-scan.run_spec.json",
        STAGE / "r4_source_hashes.sha256",
        STAGE / "launch-contract.json",
    ]
    if any(path.exists() for path in generated) and not refresh:
        raise ValueError("R4 launch-ready 文件已存在，拒绝覆盖")
    forbidden = [STAGE / name for name in ("run_status.json", "run.json", "batch.pid", "submission-receipt.json")]
    cells_dir = STAGE / "cells"
    if any(path.exists() for path in forbidden) or (cells_dir.exists() and any(cells_dir.iterdir())):
        raise ValueError("R4 已有提交或 cell 证据，拒绝刷新")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--r3-validation-summary", type=Path)
    parser.add_argument("--r3-ingest-summary", type=Path, default=R3_INGEST)
    parser.add_argument("--preview-output", type=Path, default=STAGE / "blocked-preview.json")
    parser.add_argument("--preview-only", action="store_true")
    parser.add_argument("--refresh-generated", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = target_cell()
    cell = {
        "cell_id": R4_CELL,
        "params": {"alpha": -0.25, "beta": 0.5, "L": 60, "n_units": 12},
        "budget": 64,
        "stage": "A-R4",
        "retry_policy": "仅该失败单元 32->64 sweeps；若仍失败仅考虑 64->128；门槛不变",
        "retry_of": R3_CELL,
        "controller_action_id": source["controller_action_id"],
        "calibration_only": False,
    }
    preview = {
        "schema_version": 1,
        "status": "blocked",
        "launch_ready": False,
        "reason": "等待 R3 validator 2 pass / 1 fail 与 accepted-only ingest 双证据",
        "cell_count": 1,
        "eta_minutes": {"low": 20, "high": 40, "basis": "R3 L60 双初态实测"},
        "cell": cell,
    }
    validation_path = args.r3_validation_summary.resolve() if args.r3_validation_summary else None
    ingest_path = args.r3_ingest_summary.resolve()
    try:
        validation_path = validation_path or discover_validation()
        validate_r3(validation_path, ingest_path)
    except (FileNotFoundError, ValueError, json.JSONDecodeError, KeyError) as error:
        preview["gate_error"] = str(error)
        write_json(args.preview_output.resolve(), preview)
        print(json.dumps(preview, ensure_ascii=False))
        return 0 if args.preview_only else 2
    if args.preview_only:
        preview |= {"status": "ready_preview", "launch_ready": True, "reason": "R3 双证据已通过；未写 launch-ready 文件"}
        write_json(args.preview_output.resolve(), preview)
        print(json.dumps(preview, ensure_ascii=False))
        return 0

    ensure_safe(args.refresh_generated)
    code_hashes = {relative: sha256(ROOT / relative) for relative in SOURCE_FILES}
    run_spec = {
        "schema_version": 1,
        "run_id": "pentamer-negative-phase-stage-a-r4-a0250-L060-20260810",
        "scope": "alpha=-0.25, beta=0.5, L=60; one-cell strict retry; Fig.9 excluded",
        "controller": "local_only",
        "cells": [cell],
        "settings": {
            "method": "finite_dmrg_multistart_fullq",
            "boundary": "OBC",
            "hamiltonian": "five-site unit cell Heisenberg chain, J1=1, J2=alpha, J3=beta",
            "sectors": ["Sz=0", "Sz=1"],
            "maxdim_by_L": {"60": 1000},
            "nsweeps": 64,
            "cutoff": 1e-11,
            "threads": 8,
            "q_count": 401,
            "init_modes": ["center", "ferro_j2"],
            "budget_definition": "每个独立初态均为 64 sweeps",
            "acceptance": {
                "variance_per_site_max": 1e-8,
                "final_truncation_error_max": 1e-9,
                "sector_tolerance": 1e-8,
                "q_count_min": 401,
            },
            "offline": True,
            "execution": "direct SSH; concurrency=1; stop on first failed cell",
        },
        "provenance": {
            "negative_alpha_included": True,
            "r4_reason": "R3 目标双初态 Sz=0 方差/site 略高于 1e-8，按声明策略 32->64 单元重试",
            "retry_source_cell": R3_CELL,
            "controller_action_id": ACTION_ID,
            "r3_run_spec_sha256": sha256(R3_SPEC),
            "r3_validation_summary_sha256": sha256(validation_path),
            "r3_ingestion_summary_sha256": sha256(ingest_path),
            "standard_sha256": sha256(STANDARD),
            "manifest_sha256": sha256(ROOT / "Manifest.toml"),
            "project_sha256": sha256(ROOT / "Project.toml"),
            "source_commit": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
            ).stdout.strip(),
            "code_sha256": code_hashes,
            "r3_evidence_preserved": True,
            "thresholds_relaxed": False,
            "exploratory_data_not_accepted": True,
        },
    }
    run_spec_path = STAGE / "parameter-scan.run_spec.json"
    source_hashes_path = STAGE / "r4_source_hashes.sha256"
    write_json(run_spec_path, run_spec)
    with source_hashes_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("".join(f"{digest}  {relative}\n" for relative, digest in code_hashes.items()))
    contract = {
        "schema_version": 1,
        "launch_ready": True,
        "cell_count": 1,
        "concurrency": 1,
        "offline": True,
        "eta_minutes": {"low": 20, "high": 40},
        "run_spec_sha256": sha256(run_spec_path),
        "source_hashes_sha256": sha256(source_hashes_path),
        "standard_sha256": sha256(STANDARD),
        "manifest_sha256": sha256(ROOT / "Manifest.toml"),
        "r3_validation_summary_sha256": sha256(validation_path),
        "r3_ingestion_summary_sha256": sha256(ingest_path),
        "controller_action_id": ACTION_ID,
        "thresholds_relaxed": False,
    }
    write_json(STAGE / "launch-contract.json", contract)
    write_json(args.preview_output.resolve(), preview | {"status": "released", "launch_ready": True, "reason": "R3 双证据已通过"})
    print(json.dumps({"run_spec": str(run_spec_path), "source_hashes": str(source_hashes_path), "cells": 1}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
