#!/usr/bin/env python3
"""生成 Stage A R6 单元严格重试包。"""

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
STAGE = RUN / "stage-a-beta050-calibration-r6-a0100-L040"
R5_SPEC = RUN / "stage-a-beta050-calibration-r5-remaining10" / "parameter-scan.run_spec.json"
R5_VALIDATION = RUN / "fetches" / "stage-a-beta050-calibration-r5-remaining10-20260810-2048" / "validation" / "summary.json"
R5_INGEST = RUN / "phase-diagram-v2" / "r5_partial_ingestion_summary.json"
OBSERVATIONS = RUN / "phase-diagram-v2" / "observations.json"
STANDARD = ROOT / "docs" / "full_phase_diagram_negative_standard_20260809.md"
R5_CELL = "nega-r5-a0100-b0500-L040"
R6_CELL = "nega-r6-a0100-b0500-L040"
ACTION_ID = "act-cd2b4353726834318d6b"
SOURCE_FILES = [
    "Project.toml", "Manifest.toml", "docs/full_phase_diagram_negative_standard_20260809.md",
    "src/PentamerChain.jl", "src/hamiltonian.jl", "src/order_parameters.jl",
    "scripts/autoresearch_v5/progress.py", "scripts/autoresearch_v5/negative_static_cell.jl",
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


def validate_evidence() -> dict[str, Any]:
    spec = load(R5_SPEC)
    matches = [cell for cell in spec.get("cells", []) if cell.get("cell_id") == R5_CELL]
    if len(spec.get("cells", [])) != 10 or len(matches) != 1:
        raise ValueError("R5 run spec 或目标 cell 不匹配")
    source = matches[0]
    if (
        key(source["params"]) != (-0.1, 0.5, 40) or int(source["budget"]) != 32
        or source.get("controller_action_id") != ACTION_ID or bool(source.get("calibration_only"))
    ):
        raise ValueError("R5 目标 cell 合同不匹配")
    validation = load(R5_VALIDATION)
    rows = validation.get("rows", [])
    if validation.get("counts") != {"pass": 1, "fail": 1} or len(rows) != 2:
        raise ValueError("R5 validator summary 必须为 1 pass / 1 fail")
    row = next((item for item in rows if item.get("cell_id") == R5_CELL), None)
    if not row or row.get("validator_status") != "fail" or row.get("exit_code") != 1:
        raise ValueError("R5 目标失败 row 不匹配")
    detail_path = Path(str(row.get("output", "")))
    if not detail_path.is_file() or sha256(detail_path) != row.get("sha256"):
        raise ValueError("R5 目标 validator 明细或哈希无效")
    detail = load(detail_path)
    if detail.get("status") != "fail" or not any("variance/site sz0 超门" in item for item in detail.get("failures", [])):
        raise ValueError("R5 失败原因不是声明的方差门")
    ingest = load(R5_INGEST)
    counts = ingest.get("counts", {})
    expected = {"controller_success_total": 10, "controller_failed_total": 1, "controller_pending_total": 5, "calibration_accepted_total": 5}
    if ingest.get("status") != "blocked_by_validation_failure" or any(counts.get(name) != value for name, value in expected.items()):
        raise ValueError("R5 partial ingest 状态或计数不匹配")
    if ingest.get("failed_controller_key") != {"alpha": -0.1, "beta": 0.5, "L": 40}:
        raise ValueError("R5 ingest 失败键不匹配")
    evidence = ingest.get("failed_evidence", {})
    if evidence.get("validator_sha256") != sha256(detail_path) or evidence.get("validator_status") != "fail":
        raise ValueError("R5 ingest 未绑定目标 validator")
    records = load(OBSERVATIONS).get("records", [])
    target = [item for item in records if key(item["params"]) == (-0.1, 0.5, 40)]
    if len(target) != 1 or target[0].get("status") != "failed" or target[0].get("controller_action_id") != ACTION_ID:
        raise ValueError("R5 failed observation 身份不匹配")
    if "value" in target[0] or "error" in target[0]:
        raise ValueError("R5 failed observation 不得含 value/error")
    return source


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-generated", action="store_true")
    args = parser.parse_args()
    source = validate_evidence()
    generated = [STAGE / name for name in ("parameter-scan.run_spec.json", "r6_source_hashes.sha256", "launch-contract.json")]
    if any(path.exists() for path in generated) and not args.refresh_generated:
        raise ValueError("R6 launch-ready 文件已存在，拒绝覆盖")
    forbidden = [STAGE / name for name in ("run_status.json", "run.json", "batch.pid", "submission-receipt.json")]
    cells_dir = STAGE / "cells"
    if any(path.exists() for path in forbidden) or (cells_dir.exists() and any(cells_dir.iterdir())):
        raise ValueError("R6 已有提交或 cell 证据，拒绝刷新")
    code_hashes = {relative: sha256(ROOT / relative) for relative in SOURCE_FILES}
    cell = {
        "cell_id": R6_CELL, "params": {"alpha": -0.1, "beta": 0.5, "L": 40, "n_units": 8},
        "budget": 64, "stage": "A-R6", "retry_policy": "仅该失败单元 32->64 sweeps；门槛不变",
        "retry_of": R5_CELL, "controller_action_id": source["controller_action_id"], "calibration_only": False,
    }
    run_spec = {
        "schema_version": 1, "run_id": "pentamer-negative-phase-stage-a-r6-a0100-L040-20260810",
        "scope": "alpha=-0.1, beta=0.5, L=40; one-cell strict retry; Fig.9 excluded",
        "controller": "local_only", "cells": [cell],
        "settings": {
            "method": "finite_dmrg_multistart_fullq", "boundary": "OBC",
            "hamiltonian": "five-site unit cell Heisenberg chain, J1=1, J2=alpha, J3=beta",
            "sectors": ["Sz=0", "Sz=1"], "maxdim_by_L": {"40": 800}, "nsweeps": 64,
            "cutoff": 1e-11, "threads": 8, "q_count": 401, "init_modes": ["center", "ferro_j2"],
            "budget_definition": "每个独立初态均为 64 sweeps",
            "acceptance": {"variance_per_site_max": 1e-8, "final_truncation_error_max": 1e-9, "sector_tolerance": 1e-8, "q_count_min": 401},
            "offline": True, "execution": "direct SSH; concurrency=1; stop on first failed cell",
        },
        "provenance": {
            "negative_alpha_included": True, "r6_reason": "R5 双初态 Sz0/Sz1 方差超门，按 32->64 单元重试",
            "retry_source_cell": R5_CELL, "controller_action_id": ACTION_ID,
            "r5_run_spec_sha256": sha256(R5_SPEC), "r5_validation_summary_sha256": sha256(R5_VALIDATION),
            "r5_ingestion_summary_sha256": sha256(R5_INGEST), "standard_sha256": sha256(STANDARD),
            "manifest_sha256": sha256(ROOT / "Manifest.toml"), "project_sha256": sha256(ROOT / "Project.toml"),
            "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip(),
            "code_sha256": code_hashes, "r5_failure_provenance_preserved": True,
            "thresholds_relaxed": False, "exploratory_data_not_accepted": True,
        },
    }
    spec_path, hashes_path = STAGE / "parameter-scan.run_spec.json", STAGE / "r6_source_hashes.sha256"
    write_json(spec_path, run_spec)
    with hashes_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("".join(f"{digest}  {relative}\n" for relative, digest in code_hashes.items()))
    contract = {
        "schema_version": 1, "launch_ready": True, "cell_count": 1, "concurrency": 1, "offline": True,
        "eta_minutes": {"low": 15, "high": 30}, "run_spec_sha256": sha256(spec_path),
        "source_hashes_sha256": sha256(hashes_path), "standard_sha256": sha256(STANDARD),
        "manifest_sha256": sha256(ROOT / "Manifest.toml"), "r5_validation_summary_sha256": sha256(R5_VALIDATION),
        "r5_ingestion_summary_sha256": sha256(R5_INGEST), "controller_action_id": ACTION_ID, "thresholds_relaxed": False,
    }
    write_json(STAGE / "launch-contract.json", contract)
    print(json.dumps({"run_spec": str(spec_path), "source_hashes": str(hashes_path), "cells": 1}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
