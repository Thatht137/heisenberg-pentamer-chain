#!/usr/bin/env python3
"""在 R6 严格接入后生成 Stage A R7 剩余八单元。"""

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
STAGE = RUN / "stage-a-beta050-calibration-r7-remaining8"
R5_SPEC = RUN / "stage-a-beta050-calibration-r5-remaining10" / "parameter-scan.run_spec.json"
R5_INGEST = PHASE / "r5_partial_ingestion_summary.json"
R6_SPEC = RUN / "stage-a-beta050-calibration-r6-a0100-L040" / "parameter-scan.run_spec.json"
R6_INGEST = PHASE / "r6_ingestion_summary.json"
OBSERVATIONS = PHASE / "observations.json"
STATE = PHASE / "state.json"
STANDARD = ROOT / "docs" / "full_phase_diagram_negative_standard_20260809.md"
EXPECTED_KEYS = {
    (-0.1, 0.5, 60), (-0.1, 0.5, 80),
    (-0.05, 0.5, 40), (-0.05, 0.5, 60), (-0.05, 0.5, 80),
    (-0.025, 0.5, 40), (-0.025, 0.5, 60), (-0.025, 0.5, 80),
}
EXPECTED_ACTIONS = {
    (-0.1, 0.5, 60): "act-6a4963c3064243f17ed8",
    (-0.05, 0.5, 40): "act-fffdf93a9cae183cb1c1",
    (-0.05, 0.5, 60): "act-7016420e7cbf8fc354b7",
    (-0.025, 0.5, 40): "act-4503b7acb169c6a5092f",
    (-0.025, 0.5, 60): "act-3d1ab066156655e22ec8",
}
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


def key(cell: dict[str, Any]) -> tuple[float, float, int]:
    params = cell["params"]
    return float(params["alpha"]), float(params["beta"]), int(params["L"])


def label(alpha: float) -> str:
    return f"{abs(alpha):.3f}".replace(".", "")


def discover_r6_validation() -> Path:
    pattern = "stage-a-beta050-calibration-r6-a0100-L040-*/validation/summary.json"
    matches = sorted((RUN / "fetches").glob(pattern))
    if len(matches) != 1:
        raise ValueError(f"R6 validator summary 必须唯一，当前 {len(matches)} 个")
    return matches[0]


def validate_r6(validation_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    summary = load(R6_INGEST)
    expected_counts = {
        "validator_pass": 1,
        "controller_success_total": 11,
        "controller_failed_total": 0,
        "controller_pending_total": 5,
        "calibration_accepted_total": 5,
    }
    sensitivity = summary.get("initial_state_sensitivity", {})
    if (
        summary.get("status") != "accepted_with_initial_state_sensitivity"
        or summary.get("cell_id") != "nega-r6-a0100-b0500-L040"
        or summary.get("counts") != expected_counts
        or summary.get("r7_started") is not False
        or sensitivity.get("kind") != "initial_state_half_difference"
        or sensitivity.get("systematic_caution_required") is not True
        or sensitivity.get("reported_as_observable_error") is not True
        or summary.get("r5_failure", {}).get("preserved_in_observation") is not True
        or summary.get("observations", {}).get("sha256") != sha256(OBSERVATIONS)
    ):
        raise ValueError("R6 accepted-only 基线或初态敏感性不匹配")
    validation = load(validation_path)
    rows = validation.get("rows", [])
    if (
        validation.get("status") != "pass"
        or validation.get("cell_count") != 1
        or validation.get("counts") != {"pass": 1, "fail": 0}
        or len(rows) != 1
        or rows[0].get("cell_id") != "nega-r6-a0100-b0500-L040"
        or rows[0].get("validator_status") != "pass"
        or rows[0].get("exit_code") != 0
    ):
        raise ValueError("R6 validator summary 未严格通过")
    detail = Path(str(rows[0].get("output", "")))
    if not detail.is_file() or rows[0].get("sha256") != sha256(detail):
        raise ValueError("R6 validator 明细或哈希无效")
    detail_data = load(detail)
    checks = detail_data.get("checks", {})
    if detail_data.get("status") != "pass" or not checks or not all(value is True for value in checks.values()) or detail_data.get("failures"):
        raise ValueError("R6 validator 明细含失败门")
    return summary, validation


def validate_pending() -> None:
    observations = load(OBSERVATIONS)
    records = observations.get("records", [])
    counts = {status: sum(record.get("status") == status for record in records) for status in ("success", "failed", "pending")}
    if len(records) != 16 or counts != {"success": 11, "failed": 0, "pending": 5}:
        raise ValueError(f"R6 observations 计数异常: {counts}")
    pending = {key(record): record for record in records if record.get("status") == "pending"}
    if set(pending) != set(EXPECTED_ACTIONS):
        raise ValueError("R7 controller pending 集合不是声明的五项")
    state = load(STATE)
    actions = {item.get("action_id"): item for item in state.get("actions", [])}
    for params, action_id in EXPECTED_ACTIONS.items():
        record = pending[params]
        action = actions.get(action_id)
        expected_spec = {
            "kind": "phase-diagram-cell",
            "params": {"alpha": params[0], "beta": params[1], "L": params[2]},
            "budget": 32,
        }
        if (
            int(record.get("budget", -1)) != 32
            or not record.get("receipt")
            or not record.get("artifact")
            or action is None
            or action.get("state") != "REGISTERED"
            or action.get("spec") != expected_spec
        ):
            raise ValueError(f"R7 pending/action 身份不匹配: {params}")


def planned_cells() -> list[dict[str, Any]]:
    r5 = load(R5_SPEC)
    sources = {key(cell): cell for cell in r5.get("cells", []) if key(cell) in EXPECTED_KEYS}
    if len(sources) != 8 or set(sources) != EXPECTED_KEYS:
        raise ValueError("R5 未运行来源不是声明的八项")
    cells: list[dict[str, Any]] = []
    for params in sorted(EXPECTED_KEYS, key=lambda item: (item[0], item[2])):
        alpha, beta, length = params
        source = sources[params]
        calibration = length == 80
        action_id = None if calibration else EXPECTED_ACTIONS[params]
        if source.get("controller_action_id") != action_id or source.get("calibration_only") is not calibration:
            raise ValueError(f"R5 来源 action 身份不匹配: {params}")
        cells.append({
            "cell_id": f"nega-r7-a{label(alpha)}-b0500-L{length:03d}",
            "params": {"alpha": alpha, "beta": beta, "L": length, "n_units": length // 5},
            "budget": 64 if calibration else 32,
            "stage": "A-R7-remaining8",
            "retry_policy": "首次续跑；L40/L60=32、L80=64；失败仅按32→64→128或64→128",
            "continued_from": source["cell_id"],
            "controller_action_id": action_id,
            "calibration_only": calibration,
        })
    return cells


def settings() -> dict[str, Any]:
    return {
        "method": "finite_dmrg_multistart_fullq",
        "boundary": "OBC",
        "hamiltonian": "five-site unit cell Heisenberg chain, J1=1, J2=alpha, J3=beta",
        "sectors": ["Sz=0", "Sz=1"],
        "maxdim_by_L": {"40": 800, "60": 1000, "80": 1200},
        "nsweeps": 32,
        "cutoff": 1e-11,
        "threads": 8,
        "q_count": 401,
        "init_modes": ["center", "ferro_j2"],
        "budget_definition": "每个独立初态的sweeps；L40/L60=32，L80=64",
        "acceptance": {
            "variance_per_site_max": 1e-8,
            "final_truncation_error_max": 1e-9,
            "sector_tolerance": 1e-8,
            "q_count_min": 401,
        },
        "offline": True,
        "execution": "direct SSH; concurrency=1; stop on first failed cell",
    }


def ensure_safe() -> None:
    generated = [STAGE / name for name in ("parameter-scan.run_spec.json", "r7_source_hashes.sha256", "launch-contract.json")]
    if any(path.exists() for path in generated):
        raise ValueError("R7 launch-ready 文件已存在，拒绝覆盖")
    forbidden = [STAGE / name for name in ("run_status.json", "batch.pid", "submission-receipt.json")]
    if any(path.exists() for path in forbidden) or ((STAGE / "cells").exists() and any((STAGE / "cells").iterdir())):
        raise ValueError("R7 已有提交或 cell 证据，拒绝生成")


def main() -> int:
    ensure_safe()
    validation_path = discover_r6_validation()
    r6_summary, _ = validate_r6(validation_path)
    validate_pending()
    cells = planned_cells()
    code_hashes = {relative: sha256(ROOT / relative) for relative in SOURCE_FILES}
    r5_summary = load(R5_INGEST)
    if r5_summary.get("counts", {}).get("controller_failed_total") != 1 or r5_summary.get("failed_evidence", {}).get("validator_status") != "fail":
        raise ValueError("R5 失败 provenance 不完整")
    handoff_artifact = ROOT / r6_summary["handoff_audit"]["artifact"]
    if not handoff_artifact.is_file() or sha256(handoff_artifact) != r6_summary["handoff_audit"]["sha256"]:
        raise ValueError("R6 handoff audit 哈希不匹配")
    handoff = load(handoff_artifact)
    if handoff.get("status") != "pass_with_initial_state_sensitivity" or handoff.get("initial_state_sensitivity") != r6_summary["initial_state_sensitivity"]:
        raise ValueError("R6 handoff 未显式保留初态敏感性")
    run_spec = {
        "schema_version": 1,
        "run_id": "pentamer-negative-phase-stage-a-r7-remaining8-20260810",
        "scope": "beta=0.5 Stage A remaining 8 cells; -0.1<=alpha<=-0.025; Fig.9 excluded",
        "controller": "local_only",
        "cells": cells,
        "settings": settings(),
        "provenance": {
            "negative_alpha_included": True,
            "continuation_reason": "R6严格接入后续跑Stage A剩余五个controller点与三个L80校准点",
            "r5_run_spec_sha256": sha256(R5_SPEC),
            "r5_ingestion_summary_sha256": sha256(R5_INGEST),
            "r6_run_spec_sha256": sha256(R6_SPEC),
            "r6_validation_summary_sha256": sha256(validation_path),
            "r6_ingestion_summary_sha256": sha256(R6_INGEST),
            "observations_sha256": sha256(OBSERVATIONS),
            "standard_sha256": sha256(STANDARD),
            "manifest_sha256": sha256(ROOT / "Manifest.toml"),
            "project_sha256": sha256(ROOT / "Project.toml"),
            "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip(),
            "code_sha256": code_hashes,
            "initial_state_sensitivity_provenance": {
                "r5_failure": {
                    "summary": R5_INGEST.relative_to(ROOT).as_posix(),
                    "summary_sha256": sha256(R5_INGEST),
                    "validator_artifact": r5_summary["failed_evidence"]["validator_artifact"],
                    "validator_sha256": r5_summary["failed_evidence"]["validator_sha256"],
                    "diagnostics": r5_summary["failed_evidence"]["diagnostics"],
                },
                "r6_acceptance": {
                    "handoff_audit": handoff_artifact.relative_to(ROOT).as_posix(),
                    "handoff_audit_sha256": sha256(handoff_artifact),
                    "sensitivity": r6_summary["initial_state_sensitivity"],
                },
            },
            "r5_r6_evidence_preserved": True,
            "thresholds_relaxed": False,
            "exploratory_data_not_accepted": True,
        },
    }
    STAGE.mkdir(parents=True, exist_ok=True)
    run_spec_path = STAGE / "parameter-scan.run_spec.json"
    hashes_path = STAGE / "r7_source_hashes.sha256"
    write_json(run_spec_path, run_spec)
    with hashes_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("".join(f"{digest}  {relative}\n" for relative, digest in code_hashes.items()))
    contract = {
        "schema_version": 1,
        "launch_ready": True,
        "cell_count": 8,
        "controller_cell_count": 5,
        "calibration_cell_count": 3,
        "concurrency": 1,
        "offline": True,
        "eta_hours": {"low": 3, "high": 6},
        "run_spec_sha256": sha256(run_spec_path),
        "source_hashes_sha256": sha256(hashes_path),
        "standard_sha256": sha256(STANDARD),
        "manifest_sha256": sha256(ROOT / "Manifest.toml"),
        "r6_validation_summary_sha256": sha256(validation_path),
        "r6_ingestion_summary_sha256": sha256(R6_INGEST),
        "observations_sha256": sha256(OBSERVATIONS),
        "r5_r6_evidence_preserved": True,
        "initial_state_sensitivity_explicit": True,
        "thresholds_relaxed": False,
    }
    write_json(STAGE / "launch-contract.json", contract)
    print(json.dumps({"run_spec": str(run_spec_path), "source_hashes": str(hashes_path), "cells": 8, "eta_hours": [3, 6]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
