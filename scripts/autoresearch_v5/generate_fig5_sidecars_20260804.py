# -*- coding: utf-8 -*-
"""为 Fig.5 机制图生成标准来源 sidecar。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SUMMARY = ROOT / "results/autoresearch_v5_20260731/round9_model_mechanism_figures/model_mechanism_summary.json"
SOURCE_PATHS = [
    ROOT / "results/autoresearch_v3_20260729/round1_doublet_projection/projection_scan.csv",
    ROOT / "results/autoresearch_v4_20260730/round2_local_spectral_channels_v4/multiplet_scan.csv",
    ROOT / "results/autoresearch_v4_20260730/round2_local_spectral_channels_v4/folded_transition_weights.csv",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    common = {
        "backend": "Python/matplotlib",
        "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True},
        "source_files": [{"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)} for path in SOURCE_PATHS],
        "figure_contract": summary["figure_contract"],
        "checks": summary["checks"],
        "scope_boundary": summary["scope_boundary"],
    }
    outputs = {
        "pentamer_model_effective_chain_20260731": "五聚体模型与有效链示意；只陈述单胞投影和一阶有效耦合。",
        "pentamer_momentum_filter_20260731": "q=pi 动量过滤示意；最低双重态暗通道、四重态主导局域权重。",
    }
    for stem, claim in outputs.items():
        exports = [ROOT / f"figures/{stem}{suffix}" for suffix in (".svg", ".pdf", ".png", ".tiff")]
        sidecar = {**common, "figure": stem, "claim": claim, "exports": [path.relative_to(ROOT).as_posix() for path in exports]}
        (ROOT / f"figures/{stem}.sources.json").write_text(json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "pass", "figures": len(outputs), "sources": len(SOURCE_PATHS)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
