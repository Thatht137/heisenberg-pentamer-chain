#!/usr/bin/env python3
"""生成 Stage A R4 单元的离线上传清单。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REL_STAGE = "results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha/stage-a-beta050-calibration-r4-a0250-L060"
STAGE = ROOT / REL_STAGE
OUTPUT = STAGE / "server_upload_manifest.json"
FILES = [
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
    "scripts/autoresearch_v5/launch_negative_phase_stage_a_r4_a0250_L060.sh",
    f"{REL_STAGE}/parameter-scan.run_spec.json",
    f"{REL_STAGE}/r4_source_hashes.sha256",
    f"{REL_STAGE}/launch-contract.json",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-generated", action="store_true")
    args = parser.parse_args()
    if OUTPUT.exists() and not args.refresh_generated:
        raise SystemExit(f"拒绝覆盖既有 R4 上传清单: {OUTPUT}")
    contract_path = STAGE / "launch-contract.json"
    if not contract_path.is_file():
        raise SystemExit("R4 launch contract 缺失，上传封闭")
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if (
        contract.get("launch_ready") is not True
        or contract.get("cell_count") != 1
        or contract.get("concurrency") != 1
        or contract.get("offline") is not True
        or contract.get("thresholds_relaxed") is not False
    ):
        raise SystemExit("R4 launch contract 未放行")
    spec = STAGE / "parameter-scan.run_spec.json"
    hashes = STAGE / "r4_source_hashes.sha256"
    if sha256(spec) != contract.get("run_spec_sha256") or sha256(hashes) != contract.get("source_hashes_sha256"):
        raise SystemExit("R4 launch contract 哈希不匹配")
    entries = []
    for relative in FILES:
        path = ROOT / relative
        if not path.is_file():
            raise SystemExit(f"上传文件缺失: {relative}")
        entries.append({"path": relative, "sha256": sha256(path), "bytes": path.stat().st_size})
    payload = {
        "schema_version": 1,
        "target": "/home/wangjieren/code/1x5_Heisenberg_Pentamer",
        "mode": "offline_upload_only",
        "launch_ready": True,
        "negative_alpha_included": True,
        "stage": "A-R4-a0250-L060",
        "cell_count": 1,
        "concurrency": 1,
        "eta_minutes": {"low": 20, "high": 40},
        "remote_git_pull": False,
        "files": entries,
        "post_upload": [
            "逐文件 sha256sum 对照",
            "远端 batch dry-run=1",
            "确认无其他 Julia 后以全局 flock + PID 单并发启动",
            "终态远端 checksum 后非覆盖回传并独立验收",
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"manifest": str(OUTPUT), "files": len(entries), "cells": 1}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
