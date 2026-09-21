#!/usr/bin/env python3
"""在 R8 严格接入后生成 Stage A 剩余七单元。"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha"
PHASE = RUN / "phase-diagram-v2"
STAGE = RUN / "stage-a-beta050-calibration-r9-remaining7"
R7_SPEC = RUN / "stage-a-beta050-calibration-r7-remaining8/parameter-scan.run_spec.json"
R8_SPEC = RUN / "stage-a-beta050-calibration-r8-a0100-L060/parameter-scan.run_spec.json"
R8_INGEST = PHASE / "r8_ingestion_summary.json"
OBSERVATIONS = PHASE / "observations.json"
STANDARD = ROOT / "docs/full_phase_diagram_negative_standard_20260809.md"
DROP = (-0.1, 0.5, 60)
SOURCES = [
    "Project.toml", "Manifest.toml", "docs/full_phase_diagram_negative_standard_20260809.md",
    "src/PentamerChain.jl", "src/hamiltonian.jl", "src/order_parameters.jl",
    "scripts/autoresearch_v5/progress.py", "scripts/autoresearch_v5/negative_static_cell.jl",
    "scripts/autoresearch_v5/run_negative_static_cell.py", "scripts/autoresearch_v5/run_negative_phase_structure_cell.py",
    "scripts/autoresearch_v5/run_negative_phase_structure_batch.py", "scripts/autoresearch_v5/validate_negative_phase_run.py",
    "scripts/autoresearch_v5/launch_negative_phase_stage_a_r9_remaining7.sh",
]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
            stream.flush(); os.fsync(stream.fileno())
        os.replace(name, path)
    except BaseException:
        try: os.unlink(name)
        except FileNotFoundError: pass
        raise


def key(cell: dict) -> tuple[float, float, int]:
    p = cell["params"]
    return float(p["alpha"]), float(p["beta"]), int(p["L"])


def main() -> int:
    generated = [STAGE / name for name in ("parameter-scan.run_spec.json", "r9_source_hashes.sha256", "launch-contract.json")]
    if any(path.exists() for path in generated):
        raise ValueError("R9 launch-ready 文件已存在，拒绝覆盖")
    ingest = load(R8_INGEST)
    if (
        ingest.get("status") != "accepted"
        or ingest.get("counts") != {"validator_pass": 1, "controller_success_total": 12,
                                    "controller_failed_total": 0, "controller_pending_total": 4,
                                    "calibration_accepted_total": 5}
        or ingest.get("r7_failure_preserved") is not True
        or ingest.get("observations", {}).get("sha256") != sha256(OBSERVATIONS)
    ):
        raise ValueError("R8 accepted-only 基线不匹配")
    observations = load(OBSERVATIONS).get("records", [])
    counts = {name: sum(row.get("status") == name for row in observations) for name in ("success", "failed", "pending")}
    if counts != {"success": 12, "failed": 0, "pending": 4}:
        raise ValueError(f"R8 controller 计数异常: {counts}")
    r7 = load(R7_SPEC)
    sources = [cell for cell in r7.get("cells", []) if key(cell) != DROP]
    if len(sources) != 7:
        raise ValueError("R7 剩余来源不是七项")
    cells = []
    for source in sources:
        cell = dict(source)
        cell["cell_id"] = source["cell_id"].replace("nega-r7-", "nega-r9-")
        cell["stage"] = "A-R9-remaining7"
        cell["continued_from"] = source["cell_id"]
        cells.append(cell)
    code_hashes = {name: sha256(ROOT / name) for name in SOURCES}
    settings = dict(r7["settings"])
    spec = {
        "schema_version": 1,
        "run_id": "pentamer-negative-phase-stage-a-r9-remaining7-20260811",
        "scope": "beta=0.5 Stage A remaining 7 cells; -0.1<=alpha<=-0.025; Fig.9 excluded",
        "controller": "local_only", "cells": cells, "settings": settings,
        "provenance": {
            "negative_alpha_included": True,
            "continuation_reason": "R8严格接入后续跑Stage A剩余四个controller点与三个L80校准点",
            "r7_run_spec_sha256": sha256(R7_SPEC), "r8_run_spec_sha256": sha256(R8_SPEC),
            "r8_ingestion_summary_sha256": sha256(R8_INGEST), "observations_sha256": sha256(OBSERVATIONS),
            "standard_sha256": sha256(STANDARD), "manifest_sha256": sha256(ROOT / "Manifest.toml"),
            "project_sha256": sha256(ROOT / "Project.toml"),
            "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip(),
            "code_sha256": code_hashes, "r7_r8_evidence_preserved": True,
            "r6_initial_state_sensitivity_half_difference": 0.011877542575884303,
            "thresholds_relaxed": False, "exploratory_data_not_accepted": True,
        },
    }
    STAGE.mkdir(parents=True, exist_ok=True)
    spec_path = STAGE / "parameter-scan.run_spec.json"
    hashes_path = STAGE / "r9_source_hashes.sha256"
    write_json(spec_path, spec)
    with hashes_path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("".join(f"{digest}  {name}\n" for name, digest in code_hashes.items()))
    contract = {
        "schema_version": 1, "launch_ready": True, "cell_count": 7,
        "controller_cell_count": 4, "calibration_cell_count": 3,
        "concurrency": 1, "offline": True, "eta_hours": {"low": 3, "high": 5},
        "run_spec_sha256": sha256(spec_path), "source_hashes_sha256": sha256(hashes_path),
        "standard_sha256": sha256(STANDARD), "manifest_sha256": sha256(ROOT / "Manifest.toml"),
        "r8_ingestion_summary_sha256": sha256(R8_INGEST), "observations_sha256": sha256(OBSERVATIONS),
        "r7_r8_evidence_preserved": True, "thresholds_relaxed": False,
    }
    write_json(STAGE / "launch-contract.json", contract)
    print(json.dumps({"run_spec": str(spec_path), "cells": 7, "eta_hours": [3, 5]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
