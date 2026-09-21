#!/usr/bin/env python3
"""审计第二组五轮可复用证据与待补缺口。"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results" / "autoresearch_v2_20260729"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def count_csv(path: Path) -> int:
    with path.open(encoding="utf-8", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def main() -> None:
    outdir = RUN / "round1_gap_audit"
    outdir.mkdir(parents=True, exist_ok=False)
    targets = (0.14, 0.23, 0.33)
    assets = []
    for alpha in targets:
        label = f"{alpha:g}"
        checks = {
            "raw_tebd": ROOT / "data" / f"NDSF_pentamer_alpha={label}_beta=0.5_L=40_L40_t15.jld2",
            "spin_corr_L80": ROOT / "data" / "spin_correlations" / "tasks" / f"corr_a{alpha:.2f}_b0.50_L080.csv",
            "bond_corr_L100": ROOT / "data" / "bond_correlations" / f"bond_a{alpha:.2f}_b0.50_L100.csv",
            "entanglement_L80": ROOT / "data" / "entanglement_spectrum" / f"spectrum_a{alpha:.2f}_b0.50_L080.csv",
        }
        for kind, path in checks.items():
            assets.append({
                "alpha": alpha,
                "kind": kind,
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "present": path.is_file(),
                "bytes": path.stat().st_size if path.is_file() else 0,
                "sha256": sha256(path) if path.is_file() else "",
            })

    with (outdir / "reuse_matrix.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(assets[0]))
        writer.writeheader()
        writer.writerows(assets)

    prior = ROOT / "results" / "five_rounds_20260729"
    audit = {
        "scope": {"alpha_min": 0.0, "alpha_max": 1.0, "beta": 0.5, "fig9_excluded": True},
        "targets": list(targets),
        "prior_round_complete": (prior / "report.html").is_file(),
        "prior_validation_rows": count_csv(prior / "round4_validation" / "parameter-scan.csv"),
        "assets_present": sum(item["present"] for item in assets),
        "assets_expected": len(assets),
        "gaps": [
            "alpha=0.14 的 DMRG 方差余量较小且末 sweep 能量变化偏大",
            "alpha=0.23 缺五类中心切口纠缠谱",
            "单五聚体正区缺算符选择定则与谱权重",
            "正区 TEBD 原始数据尚未做未裁剪时间窗诊断，也没有 dt/2 数据",
        ],
        "reuse_decision": "不重算相图、不重复 Smoke；只补以上四个缺口",
        "negative_alpha_new_compute": False,
    }
    (outdir / "audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (outdir / "checksums.sha256").write_text(
        "".join(
            f"{sha256(path)}  {path.name}\n"
            for path in sorted(outdir.iterdir())
            if path.name != "checksums.sha256"
        ),
        encoding="utf-8",
    )
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == "__main__":
    main()
