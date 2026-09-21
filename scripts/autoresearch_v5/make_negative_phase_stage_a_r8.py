#!/usr/bin/env python3
"""生成 Stage A R8 的 L60 单点严格重试包。"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results" / "autoresearch_v5_20260809" / "round44_phase_diagram_full_alpha"
PHASE = RUN / "phase-diagram-v2"
STAGE = RUN / "stage-a-beta050-calibration-r8-a0100-L060"
R7_SPEC = RUN / "stage-a-beta050-calibration-r7-remaining8" / "parameter-scan.run_spec.json"
R7_INGEST = PHASE / "r7_failure_ingestion_summary.json"
R6_INGEST = PHASE / "r6_ingestion_summary.json"
OBSERVATIONS = PHASE / "observations.json"
STANDARD = ROOT / "docs" / "full_phase_diagram_negative_standard_20260809.md"
R7_CELL = "nega-r7-a0100-b0500-L060"
R8_CELL = "nega-r8-a0100-b0500-L060"
ACTION = "act-6a4963c3064243f17ed8"
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
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
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


def contains_value_error(value: Any) -> bool:
    if isinstance(value, dict):
        return any(name in {"value", "error"} or contains_value_error(item) for name, item in value.items())
    if isinstance(value, list):
        return any(contains_value_error(item) for item in value)
    return False


def ensure_safe() -> None:
    generated = [STAGE / name for name in ("parameter-scan.run_spec.json", "r8_source_hashes.sha256", "launch-contract.json")]
    if any(path.exists() for path in generated):
        raise ValueError("R8 launch-ready 文件已存在，拒绝覆盖")
    forbidden = [STAGE / name for name in ("run_status.json", "batch.pid", "submission-receipt.json")]
    if any(path.exists() for path in forbidden) or ((STAGE / "cells").exists() and any((STAGE / "cells").iterdir())):
        raise ValueError("R8 已有提交或 cell 证据，拒绝生成")


def main() -> int:
    ensure_safe()
    r7 = load(R7_INGEST)
    expected_counts = {
        "controller_success_total": 11,
        "controller_failed_total": 1,
        "controller_pending_total": 4,
        "calibration_accepted_total": 5,
    }
    if (
        r7.get("status") != "blocked_by_validation_failure"
        or r7.get("cell_id") != R7_CELL
        or r7.get("failed_key") != {"alpha": -0.1, "beta": 0.5, "L": 60}
        or r7.get("counts") != expected_counts
        or contains_value_error(r7.get("failure_evidence", {}))
        or r7.get("observations", {}).get("sha256") != sha256(OBSERVATIONS)
    ):
        raise ValueError("R7 failure ingest 基线不匹配")
    validation_ref = r7.get("provenance", {}).get("validation_summary", {})
    validation_path = ROOT / str(validation_ref.get("artifact", ""))
    if not validation_path.is_file() or sha256(validation_path) != validation_ref.get("sha256"):
        raise ValueError("R7 validation summary 哈希不匹配")
    validation = load(validation_path)
    rows = validation.get("rows", [])
    if (
        validation.get("status") != "fail"
        or validation.get("counts") != {"pass": 0, "fail": 1}
        or len(rows) != 1
        or rows[0].get("cell_id") != R7_CELL
        or rows[0].get("validator_status") != "fail"
        or rows[0].get("exit_code") != 1
    ):
        raise ValueError("R7 validator 不是严格 0 pass / 1 fail")

    observations = load(OBSERVATIONS)
    records = observations.get("records", [])
    counts = {status: sum(record.get("status") == status for record in records) for status in ("success", "failed", "pending")}
    targets = [record for record in records if record.get("params") == {"alpha": -0.1, "beta": 0.5, "L": 60}]
    if len(records) != 16 or counts != {"success": 11, "failed": 1, "pending": 4} or len(targets) != 1:
        raise ValueError("R7 observations 计数或目标键异常")
    target = targets[0]
    if (
        target.get("status") != "failed"
        or int(target.get("budget", -1)) != 32
        or target.get("controller_action_id") != ACTION
        or target.get("failure_evidence") != r7.get("failure_evidence")
        or contains_value_error(target)
    ):
        raise ValueError("R7 failed observation 身份或无值约束不匹配")

    r6_ref = r7.get("provenance", {}).get("r6", {}).get("ingestion_summary", {})
    if r6_ref.get("artifact") != R6_INGEST.relative_to(ROOT).as_posix() or r6_ref.get("sha256") != sha256(R6_INGEST):
        raise ValueError("R7 未绑定当前 R6 ingest")
    r6 = load(R6_INGEST)
    sensitivity = r6.get("initial_state_sensitivity", {})
    if (
        r6.get("status") != "accepted_with_initial_state_sensitivity"
        or sensitivity.get("kind") != "initial_state_half_difference"
        or sensitivity.get("systematic_caution_required") is not True
        or sensitivity.get("reported_as_observable_error") is not True
        or r7.get("provenance", {}).get("r6", {}).get("r5_failure_provenance_preserved") is not True
    ):
        raise ValueError("R6 初态敏感性或 R5 provenance 未保留")

    r7_spec = load(R7_SPEC)
    source = next((cell for cell in r7_spec.get("cells", []) if cell.get("cell_id") == R7_CELL), None)
    if source is None or source.get("params") != {"alpha": -0.1, "beta": 0.5, "L": 60, "n_units": 12} or int(source.get("budget", -1)) != 32:
        raise ValueError("R7 run spec 目标 cell 不匹配")
    runner_text = (ROOT / "scripts/autoresearch_v5/run_negative_static_cell.py").read_text(encoding="utf-8")
    if '"nonnegative_gap"' not in runner_text or ">= -1e-8" not in runner_text:
        raise ValueError("现有 runner 未执行 nonnegative gap 门")

    code_hashes = {relative: sha256(ROOT / relative) for relative in SOURCE_FILES}
    cell = {
        "cell_id": R8_CELL,
        "params": {"alpha": -0.1, "beta": 0.5, "L": 60, "n_units": 12},
        "budget": 64,
        "stage": "A-R8",
        "retry_policy": "仅R7失败单元32→64 sweeps；方差、gap及其余门槛不变",
        "retry_of": R7_CELL,
        "controller_action_id": ACTION,
        "calibration_only": False,
    }
    settings = {
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
        "budget_definition": "每个独立初态均为64 sweeps",
        "acceptance": {
            "variance_per_site_max": 1e-8,
            "final_truncation_error_max": 1e-9,
            "sector_tolerance": 1e-8,
            "spin_gap_min": -1e-8,
            "nonnegative_gap_required": True,
            "q_count_min": 401,
        },
        "offline": True,
        "execution": "direct SSH; concurrency=1; stop on first failed cell",
    }
    run_spec = {
        "schema_version": 1,
        "run_id": "pentamer-negative-phase-stage-a-r8-a0100-L060-20260811",
        "scope": "alpha=-0.1, beta=0.5, L=60; one-cell strict retry; Fig.9 excluded",
        "controller": "local_only",
        "cells": [cell],
        "settings": settings,
        "provenance": {
            "negative_alpha_included": True,
            "r8_reason": "R7双初态方差超门且center gap为负，按32→64单点重试",
            "r7_run_spec_sha256": sha256(R7_SPEC),
            "r7_validation_summary_sha256": sha256(validation_path),
            "r7_failure_ingestion_summary_sha256": sha256(R7_INGEST),
            "r7_failure_provenance": r7.get("failure_evidence"),
            "r6_ingestion_summary_sha256": sha256(R6_INGEST),
            "r6_initial_state_sensitivity": sensitivity,
            "standard_sha256": sha256(STANDARD),
            "manifest_sha256": sha256(ROOT / "Manifest.toml"),
            "project_sha256": sha256(ROOT / "Project.toml"),
            "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip(),
            "code_sha256": code_hashes,
            "r6_r7_evidence_preserved": True,
            "gap_gate_enforced": True,
            "thresholds_relaxed": False,
            "exploratory_data_not_accepted": True,
        },
    }
    STAGE.mkdir(parents=True, exist_ok=True)
    run_spec_path = STAGE / "parameter-scan.run_spec.json"
    hashes_path = STAGE / "r8_source_hashes.sha256"
    write_json(run_spec_path, run_spec)
    with hashes_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("".join(f"{digest}  {relative}\n" for relative, digest in code_hashes.items()))
    contract = {
        "schema_version": 1,
        "launch_ready": True,
        "cell_count": 1,
        "concurrency": 1,
        "offline": True,
        "eta_minutes": {"low": 15, "high": 30},
        "run_spec_sha256": sha256(run_spec_path),
        "source_hashes_sha256": sha256(hashes_path),
        "standard_sha256": sha256(STANDARD),
        "manifest_sha256": sha256(ROOT / "Manifest.toml"),
        "r7_validation_summary_sha256": sha256(validation_path),
        "r7_failure_ingestion_summary_sha256": sha256(R7_INGEST),
        "r6_ingestion_summary_sha256": sha256(R6_INGEST),
        "observations_sha256": sha256(OBSERVATIONS),
        "r6_r7_evidence_preserved": True,
        "gap_gate_enforced": True,
        "nonnegative_gap_min": -1e-8,
        "thresholds_relaxed": False,
    }
    write_json(STAGE / "launch-contract.json", contract)
    print(json.dumps({"run_spec": str(run_spec_path), "source_hashes": str(hashes_path), "cells": 1, "eta_minutes": [15, 30]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
