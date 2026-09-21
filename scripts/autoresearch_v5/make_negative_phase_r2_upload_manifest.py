#!/usr/bin/env python3
"""生成负 alpha 阶段 A R2 单元的离线上传清单。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results" / "autoresearch_v5_20260809" / "round44_phase_diagram_full_alpha" / "stage-a-beta050-calibration-r2-a0350-L060"
OUTPUT = RUN / "server_upload_manifest.json"
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
    "scripts/autoresearch_v5/launch_negative_phase_stage_a_r2_a0350_L060.sh",
    "results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha/stage-a-beta050-calibration-r2-a0350-L060/parameter-scan.run_spec.json",
    "results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha/stage-a-beta050-calibration-r2-a0350-L060/r2_source_hashes.sha256",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise SystemExit(f"拒绝覆盖既有 R2 上传清单: {OUTPUT}")
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
        "negative_alpha_included": True,
        "stage": "A-R2-a0350-L060",
        "concurrency": 1,
        "remote_git_pull": False,
        "files": entries,
        "post_upload": [
            "逐文件 sha256sum 对照",
            "远端 batch dry-run=1",
            "确认无其他 Julia 后以 flock + PID 启动",
            "终态远端 checksum 后非覆盖回传并独立验收",
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"manifest": str(OUTPUT), "files": len(entries)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
