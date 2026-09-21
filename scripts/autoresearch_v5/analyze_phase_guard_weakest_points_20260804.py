"""提取最接近 crossing guard 门槛的正区内部点。"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "results/autoresearch_v5_20260802/round19_phase_diagram_positive_mesh/phase-diagram/phase-size-differences.csv"
OUTPUT = ROOT / "results/autoresearch_v5_20260804/round35_phase_guard_weakest_points/summary.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    with SOURCE.open(encoding="utf-8", newline="") as handle:
        rows = []
        for row in csv.DictReader(handle):
            alpha = float(row["alpha"])
            if alpha <= 0.0:
                continue
            delta = float(row["delta_R"])
            error = float(row["error"])
            rows.append({
                "beta": float(row["beta"]),
                "alpha": alpha,
                "size_pair": row["size_pair"],
                "delta_R": delta,
                "error": error,
                "guard_margin": abs(delta) - 2.0 * error,
                "abs_delta_over_2sigma": abs(delta) / max(2.0 * error, 1e-30),
                "significant_2sigma": abs(delta) > 2.0 * error,
            })
    weakest = sorted(rows, key=lambda row: (row["guard_margin"], row["abs_delta_over_2sigma"]))[:12]
    result = {
        "schema_version": 1,
        "status": "pass" if len(rows) == 56 and all(row["significant_2sigma"] for row in rows) else "fail",
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": sha256(SOURCE),
        "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True, "alpha_zero_boundary_excluded": True},
        "internal_count": len(rows),
        "weakest_points": weakest,
        "selection_rule": "按 |ΔR|-2σ 升序；同值再按 |ΔR|/(2σ) 升序；只用于下一次验证优先级，不自动生成 action。",
        "next_compute_recommendation": "若服务器 round31 终态后仍需补算，优先复核 weakest_points 前 4 个控制点的独立初态和更高统计预算；先不扩大 alpha/beta 边界。",
        "interpretation": "所有内部点仍通过既定 2σ guard；weakest 列表只表示数值裕量较小，不表示发现相界。",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "internal_count": len(rows), "weakest": weakest[:4]}, ensure_ascii=False))
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
