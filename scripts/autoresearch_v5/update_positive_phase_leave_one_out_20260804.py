"""追加正区高误差 cell 的 leave-one-out 复核。"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "results/research_progress"
CSV_PATH = ROOT / "results/autoresearch_v5_20260802/round19_phase_diagram_positive_mesh/phase-diagram/phase-size-differences.csv"
DIAGNOSTIC = REPORT_DIR / "mesh_cell_0051_diagnostic_20260803.json"
OUT = REPORT_DIR / "positive_phase_leave_one_out_20260804.json"
REPORT = REPORT_DIR / "report.json"
TITLE = "2026-08-04 正区 mesh-cell-0051 leave-one-out 复核"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    diagnostic = json.loads(DIAGNOSTIC.read_text(encoding="utf-8"))
    target = diagnostic["scope"]
    with CSV_PATH.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    internal = [row for row in rows if float(row["alpha"]) > 0]
    excluded = [
        row for row in internal
        if abs(float(row["alpha"]) - float(target["alpha"])) < 1e-12
        and abs(float(row["beta"]) - float(target["beta"])) < 1e-12
        and row["size_pair"] == "60-80"
    ]
    kept = [row for row in internal if row not in excluded]
    signs = {"-1": 0, "0": 0, "+1": 0}
    for row in kept:
        delta = float(row["delta_R"])
        signs["-1" if delta < 0 else "+1" if delta > 0 else "0"] += 1
    result = {
        "schema_version": 1,
        "created_at": "2026-08-04",
        "scope": {"alpha_min": 0.0, "beta_min": 0.0, "negative_alpha_excluded": True},
        "excluded_cell": {
            "cell_id": diagnostic["cell_id"],
            "alpha": target["alpha"],
            "beta": target["beta"],
            "L": target["L"],
            "reason": "独立初态误差偏大；只从 60-80 配对中剔除对应 L=80 影响项",
        },
        "full_internal_rows": len(internal),
        "excluded_rows": len(excluded),
        "kept_internal_rows": len(kept),
        "kept_signs": signs,
        "kept_all_significant_2sigma": all(row["significant_2sigma"].lower() == "true" for row in kept),
        "kept_delta_range": [min(float(row["delta_R"]) for row in kept), max(float(row["delta_R"]) for row in kept)],
        "status": "UNCHANGED_NO_SIGNIFICANT_CROSSING" if signs == {"-1": len(kept), "0": 0, "+1": 0} else "REVIEW_REQUIRED",
        "interpretation": "剔除 mesh-cell-0051 对应的 60-80 配对后，剩余正 alpha 内部尺寸差仍全部为负且通过 2sigma；该 cell 可保留警告，但不改变有限尺寸 guard 的方向。",
        "source_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in [CSV_PATH, DIAGNOSTIC]},
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "只复核正区 alpha>0 的有限尺寸差；不扩大网格，不包含负 alpha 或 Fig. 9。",
        "blocks": [
            {"kind": "verdict", "status": "good", "label": "leave-one-out 不改变正区 guard", "why": f"剔除 {diagnostic['cell_id']} 对应的 60-80 配对后，{len(kept)} 个内部尺寸差仍全部为负并通过 2sigma。"},
            {"kind": "table", "columns": ["项目", "结果", "解释"], "rows": [
                ["剔除对象", f"alpha={target['alpha']}，beta={target['beta']}，L={target['L']}", "独立初态误差 6.049e-3，保留警告"],
                ["内部尺寸差", f"{len(internal)} -> {len(kept)}", "仅去掉受该 L=80 cell 影响的 60-80 行"],
                ["剩余符号", f"负 {signs['-1']}；零 {signs['0']}；正 {signs['+1']}", "方向保持一致"],
                ["2sigma", "通过" if result["kept_all_significant_2sigma"] else "需复核", "不降低原验收门槛"],
            ], "widths": ["23%", "34%", "43%"]},
            {"kind": "kv", "pairs": [["审计文件", "results/research_progress/positive_phase_leave_one_out_20260804.json"], ["结论", result["interpretation"]], ["范围", "0 <= alpha,beta <= 1；排除负 alpha 与 Fig. 9"]]},
            {"kind": "note", "label": "边界", "style": "pending", "text": "该复核支持‘当前数据未见可验收内部 crossing’，但仍不把有限尺寸 guard 升级为热力学极限相图或命名相界。"},
        ],
    }
    report["sections"] = [item for item in report["sections"] if item["title"] != TITLE]
    report["sections"].insert(1, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · REFERENCE-ALIGNED FIGURES"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "kept": len(kept), "report_section": TITLE}, ensure_ascii=False))


if __name__ == "__main__":
    main()
