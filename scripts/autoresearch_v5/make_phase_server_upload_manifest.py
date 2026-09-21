#!/usr/bin/env python3
"""生成直连服务器所需的最小离线上传清单。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results" / "autoresearch_v5_20260731" / "round17_phase_diagram_positive"
OUTPUT = RUN / "server_upload_manifest.json"


FILES = [
    "Project.toml",
    "Manifest.toml",
    "docs/pentamer_reproduction_standard.md",
    "src/PentamerChain.jl",
    "src/hamiltonian.jl",
    "src/order_parameters.jl",
    "scripts/autoresearch_v5/positive_static_cell.jl",
    "scripts/autoresearch_v5/run_positive_static_cell.py",
    "scripts/autoresearch_v5/run_phase_structure_ratio_cell.py",
    "scripts/autoresearch_v5/run_phase_structure_batch.py",
    "scripts/autoresearch_v5/launch_phase_batch_remote.sh",
    "results/autoresearch_v5_20260731/round17_phase_diagram_positive/parameter-scan.run_spec.json",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
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
        "negative_alpha_excluded": True,
        "remote_git_pull": False,
        "files": entries,
        "post_upload": [
            "远端逐文件 sha256sum 对照",
            "Julia 1.12.3 离线 smoke",
            "先运行 --dry-run，再提交单个重任务",
            "每个 cell 回传并校验后再继续",
        ],
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(OUTPUT), "files": len(entries)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
