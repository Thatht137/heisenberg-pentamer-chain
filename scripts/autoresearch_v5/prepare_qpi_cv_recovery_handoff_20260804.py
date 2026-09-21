"""准备 q=pi CV 回传后的本地交接预检，不连接服务器。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
OUTPUT = ROOT / "results/research_progress/qpi_cv_recovery_handoff_preflight_20260804.json"
TITLE = "2026-08-04 q=pi CV 回传交接预检"


def load(path: str) -> dict[str, object]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def main() -> None:
    high_path = "results/research_progress/round31_high055_validator_20260804_recheck.json"
    low_path = "results/research_progress/round31_low_validator_20260804_recheck.json"
    high = load(high_path)
    low = load(low_path)
    required_tools = [
        "scripts/autoresearch_v5/validate_cv_run.py",
        "scripts/autoresearch_v5/assemble_qpi_cv_anchors.py",
        "scripts/autoresearch_v5/analyze_cv_tebd_crosscheck.py",
        "scripts/autoresearch_v5/fetch_qpi_cv_extension_results.py",
        "scripts/autoresearch_v5/audit_local_integrity_20260803.py",
    ]
    tools_ok = {path: (ROOT / path).is_file() for path in required_tools}
    target = ROOT / "results/autoresearch_v5_20260804/qpi_cv_extension_recovery_fetch"
    result = {
        "schema_version": 1,
        "checked_at": "2026-08-04T09:10:00+08:00",
        "status": "ready_for_recovery_check" if high.get("status") == "pass" and low.get("status") == "fail" and all(tools_ok.values()) else "not_ready",
        "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True},
        "cell_rechecks": {
            "high055": {"status": high.get("status"), "max_cv_residual": high.get("diagnostics", {}).get("max_cv_residual"), "evidence": high_path},
            "low000_020": {"status": low.get("status"), "max_cv_residual": low.get("diagnostics", {}).get("max_cv_residual"), "expected_failure": True, "evidence": low_path},
        },
        "required_tools": tools_ok,
        "non_clobber_target": str(target.relative_to(ROOT)).replace("\\", "/"),
        "handoff_order": [
            "read overall_progress/status/progress/manifest",
            "remote sha256sum -c checksums.sha256",
            "non-clobber fetch to a new local directory",
            "local checksum and validate_cv_run.py",
            "assemble_qpi_cv_anchors.py using accepted cells only",
            "analyze_cv_tebd_crosscheck.py",
            "update HTML report and rerun integrity audit",
        ],
        "guard": "low residual failure remains isolated; no threshold relaxation or overwrite",
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "只做本地交接预检；服务器恢复前不执行 fetch、不覆盖旧结果、不启动第二个 Julia。",
        "blocks": [
            {"kind": "verdict", "status": "good" if result["status"] == "ready_for_recovery_check" else "bad", "label": "回传后可按顺序验收", "why": "high-055 独立重验通过；low-000–020 独立重验按预期保留 residual 失败；所需脚本齐全。"},
            {"kind": "table", "columns": ["cell", "重验状态", "max residual", "处理"], "rows": [["high-055", str(high.get("status")), f"{high.get('diagnostics', {}).get('max_cv_residual'):.6e}", "可纳入 accepted sparse anchors"], ["low-000–020", str(low.get("status")), f"{low.get('diagnostics', {}).get('max_cv_residual'):.6e}", "保留失败证据，不纳入锚点"]], "widths": ["22%", "20%", "25%", "33%"]},
            {"kind": "list", "title": "回传后的固定顺序", "items": result["handoff_order"]},
            {"kind": "kv", "pairs": [["预检 JSON", "results/research_progress/qpi_cv_recovery_handoff_preflight_20260804.json"], ["非覆盖目标", "服务器恢复后新建的预案目录（当前尚未创建）"], ["范围", "0 <= alpha,beta <= 1；排除负 alpha 和 Fig.9"]]},
        ],
    }
    report["sections"] = [entry for entry in report["sections"] if entry.get("title") != TITLE]
    report["sections"].insert(2, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · CV RECOVERY HANDOFF PREFLIGHT"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "tools_ok": all(tools_ok.values()), "high055": high.get("status"), "low000_020": low.get("status")}, ensure_ascii=False))
    if result["status"] != "ready_for_recovery_check":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
