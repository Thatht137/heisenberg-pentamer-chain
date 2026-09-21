#!/usr/bin/env python3
"""生成 Stage A R14 离线上传清单。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REL = "results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha/stage-a-beta050-calibration-r14-remaining4"
STAGE = ROOT / REL
OUTPUT = STAGE / "server_upload_manifest.json"
FILES = ["Project.toml", "Manifest.toml", "docs/full_phase_diagram_negative_standard_20260809.md",
    "src/PentamerChain.jl", "src/hamiltonian.jl", "src/order_parameters.jl",
    "scripts/autoresearch_v5/progress.py", "scripts/autoresearch_v5/negative_static_cell.jl",
    "scripts/autoresearch_v5/run_negative_static_cell.py", "scripts/autoresearch_v5/run_negative_phase_structure_cell.py",
    "scripts/autoresearch_v5/run_negative_phase_structure_batch.py", "scripts/autoresearch_v5/validate_negative_phase_run.py",
    "scripts/autoresearch_v5/launch_negative_phase_stage_a_r14_remaining4.sh",
    f"{REL}/parameter-scan.run_spec.json", f"{REL}/r14_source_hashes.sha256", f"{REL}/launch-contract.json"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OUTPUT.exists(): raise SystemExit(f"拒绝覆盖既有 R14 上传清单: {OUTPUT}")
    contract = json.loads((STAGE / "launch-contract.json").read_text(encoding="utf-8"))
    if (
        contract.get("launch_ready") is not True or contract.get("cell_count") != 4
        or contract.get("controller_cell_count") != 2 or contract.get("calibration_cell_count") != 2
        or contract.get("concurrency") != 1 or contract.get("stop_on_first_failure") is not True
        or contract.get("history_evidence_preserved") is not True or contract.get("gap_gate_enforced") is not True
        or contract.get("thresholds_relaxed") is not False
        or sha256(STAGE / "parameter-scan.run_spec.json") != contract.get("run_spec_sha256")
        or sha256(STAGE / "r14_source_hashes.sha256") != contract.get("source_hashes_sha256")
    ): raise SystemExit("R14 launch contract 未放行")
    entries = [{"path": name, "sha256": sha256(ROOT / name), "bytes": (ROOT / name).stat().st_size} for name in FILES]
    payload = {"schema_version": 1, "target": "/home/wangjieren/code/1x5_Heisenberg_Pentamer",
        "mode": "offline_upload_only", "launch_ready": True, "negative_alpha_included": True,
        "stage": "A-R14-remaining4", "cell_count": 4, "controller_cell_count": 2,
        "calibration_cell_count": 2, "concurrency": 1, "stop_on_first_failure": True,
        "eta_hours": {"low": 1.0, "high": 2.0}, "remote_git_pull": False, "files": entries}
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"manifest": str(OUTPUT), "files": len(entries)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
