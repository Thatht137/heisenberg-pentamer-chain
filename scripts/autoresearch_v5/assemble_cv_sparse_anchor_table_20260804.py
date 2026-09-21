"""汇总已通过的 L=40 CV 稀疏锚点。"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
OUT_CSV = ROOT / "results/research_progress/cv_sparse_anchor_table_20260804.csv"
OUT_JSON = ROOT / "results/research_progress/cv_sparse_anchor_table_20260804.json"
TITLE = "2026-08-04 L=40 CV 稀疏锚点表扩展"

BASE = ROOT / "results/autoresearch_v5_20260802/round21_cv_triplet_warmstart/cell-0002-L40-qpi-w025-w035"
LEGACY = ROOT / "results/autoresearch_v5_20260730/round3_cv_L40_probe/cell-0001-L40-qpi-w020"
NEW = ROOT / "results/autoresearch_v5_20260803/round31_qpi_cv_extension_completed_cells_20260804/cell-l40-qpi-high-055"
NEW_HIGH = ROOT / "results/autoresearch_v5_20260803/round31_qpi_cv_extension_completed_cells_20260804/cell-l40-qpi-high-100"
LOW = ROOT / "results/autoresearch_v5_20260803/round31_qpi_cv_extension_completed_cells_20260804/cell-l40-qpi-low-000-020"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_spectrum(path: Path, source: str) -> list[dict[str, object]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [{"omega": float(row["omega"]), "intensity": float(row["intensity"]), "relative_residual": float(row["relative_residual"]), "source": source} for row in rows]


def main() -> None:
    rows = (read_spectrum(LEGACY / "spectrum.csv", "round3_w020")
            + read_spectrum(BASE / "spectrum.csv", "round21_triplet")
            + read_spectrum(NEW / "spectrum.csv", "round31_high055")
            + read_spectrum(NEW_HIGH / "spectrum.csv", "round31_high100"))
    rows.sort(key=lambda row: float(row["omega"]))
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["omega", "intensity", "relative_residual", "source", "acceptance"])
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "acceptance": "pass"})

    excluded = read_spectrum(LOW / "spectrum.csv", "round31_low_failed")
    payload = {
        "schema_version": 1,
        "status": "constrained_sparse_table",
        "accepted_points": len(rows),
        "accepted_omega": [row["omega"] for row in rows],
        "excluded_failed_points": len(excluded),
        "excluded_reason": "low cell max residual=1.3237623405931422e-5 > 1e-5",
        "coverage": {"omega_min": min(row["omega"] for row in rows), "omega_max": max(row["omega"] for row in rows), "tebd_peak_covered": False, "major_window_0_to_1_5_covered": False},
        "source_files": [{"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(path)} for path in (LEGACY / "spectrum.csv", LEGACY / "manifest.json", BASE / "spectrum.csv", BASE / "manifest.json", NEW / "spectrum.csv", NEW / "manifest.json", NEW_HIGH / "spectrum.csv", NEW_HIGH / "manifest.json", LOW / "spectrum.csv", LOW / "manifest.json")],
        "scope": {"alpha": 0.23, "beta": 0.5, "L": 40, "q": "pi", "negative_alpha_excluded": True, "fig9_excluded": True},
        "interpretation": "可用于 Fig.8 受限叠加和数据表；不关闭 CV-TEBD 交叉门，不替代 omega≈0.05 主峰或 [0,1.5] 积分窗。",
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "仅由已通过 validator 的 CV 点组成；low cell 的 5 个点因 residual 超门被排除。",
        "blocks": [
            {"kind": "verdict", "status": "warn", "label": f"{len(rows)} 个稀疏 CV 锚点可追溯，但动态门仍未关闭", "why": "新增 omega=1.00 已通过；集合仍不覆盖 omega≈0.05 主峰，也不覆盖 [0,1.5] 积分窗。"},
            {"kind": "table", "columns": ["omega/J1", "S(pi,omega)", "relative residual", "来源"], "rows": [[f"{row['omega']:.2f}", f"{row['intensity']:.7f}", f"{row['relative_residual']:.3e}", str(row['source'])] for row in rows], "numeric": [True, True, True, False], "widths": ["20%", "28%", "28%", "24%"]},
            {"kind": "kv", "pairs": [["CSV", "results/research_progress/cv_sparse_anchor_table_20260804.csv"], ["JSON", "results/research_progress/cv_sparse_anchor_table_20260804.json"], ["排除点", "low cell omega=0.00–0.20；5 点，max residual=1.3238e-5"], ["用途", "Fig.8 constrained overlay / 审阅表，不作 production dynamic claim"]]},
            {"kind": "note", "label": "验收边界", "style": "pending", "text": "只有 CV 网格包围 TEBD 主峰并覆盖主要积分窗，且 TEBD dt/dt2、时间窗和权重门槛通过后，才允许把 NotEvaluable 升级为 Agreement。"},
        ],
    }
    report["sections"] = [section] + [item for item in report["sections"] if item.get("title") != TITLE]
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · SPARSE CV ANCHORS"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"title": TITLE, "accepted_points": len(rows), "excluded_failed_points": len(excluded)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
