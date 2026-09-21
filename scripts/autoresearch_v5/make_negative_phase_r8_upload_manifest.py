#!/usr/bin/env python3
"""生成 Stage A R8 单元离线上传清单。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REL = "results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha/stage-a-beta050-calibration-r8-a0100-L060"
STAGE = ROOT / REL
OUTPUT = STAGE / "server_upload_manifest.json"
FILES = [
    "Project.toml", "Manifest.toml", "docs/full_phase_diagram_negative_standard_20260809.md",
    "src/PentamerChain.jl", "src/hamiltonian.jl", "src/order_parameters.jl",
    "scripts/autoresearch_v5/progress.py", "scripts/autoresearch_v5/negative_static_cell.jl",
    "scripts/autoresearch_v5/run_negative_static_cell.py", "scripts/autoresearch_v5/run_negative_phase_structure_cell.py",
    "scripts/autoresearch_v5/run_negative_phase_structure_batch.py", "scripts/autoresearch_v5/validate_negative_phase_run.py",
    "scripts/autoresearch_v5/launch_negative_phase_stage_a_r8_a0100_L060.sh",
    f"{REL}/parameter-scan.run_spec.json", f"{REL}/r8_source_hashes.sha256", f"{REL}/launch-contract.json",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OUTPUT.exists():
        raise SystemExit(f"拒绝覆盖既有 R8 上传清单: {OUTPUT}")
    contract = json.loads((STAGE / "launch-contract.json").read_text(encoding="utf-8"))
    if (
        contract.get("launch_ready") is not True
        or contract.get("cell_count") != 1
        or contract.get("concurrency") != 1
        or contract.get("r6_r7_evidence_preserved") is not True
        or contract.get("gap_gate_enforced") is not True
        or contract.get("thresholds_relaxed") is not False
    ):
        raise SystemExit("R8 launch contract 未放行")
    if sha256(STAGE / "parameter-scan.run_spec.json") != contract["run_spec_sha256"] or sha256(STAGE / "r8_source_hashes.sha256") != contract["source_hashes_sha256"]:
        raise SystemExit("R8 contract 哈希不匹配")
    entries = [{"path": relative, "sha256": sha256(ROOT / relative), "bytes": (ROOT / relative).stat().st_size} for relative in FILES]
    payload = {
        "schema_version": 1,
        "target": "/home/wangjieren/code/1x5_Heisenberg_Pentamer",
        "mode": "offline_upload_only",
        "launch_ready": True,
        "negative_alpha_included": True,
        "stage": "A-R8-a0100-L060",
        "cell_count": 1,
        "concurrency": 1,
        "eta_minutes": {"low": 15, "high": 30},
        "remote_git_pull": False,
        "files": entries,
    }
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"manifest": str(OUTPUT), "files": len(entries)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
