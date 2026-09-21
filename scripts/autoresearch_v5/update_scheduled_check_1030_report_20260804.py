"""登记 10:30 一次性只读检查。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
TITLE = "2026-08-04 round31 10:30 一次性只读检查已安排"


def main() -> None:
    armed = json.loads((ROOT / "results/research_progress/qpi_cv_extension_scheduled_check_1030_20260804.json").read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "仅安排一次恢复检查，不循环、不写远端、不启动第二个 Julia。",
        "blocks": [
            {"kind": "verdict", "status": "good", "label": "10:30 检查已挂起", "why": "当前 high-100 仍在正常 linsolve；下一次检查留出约两小时，避免短间隔轮询。"},
            {"kind": "kv", "pairs": [["目标时间", "2026-08-04 10:30:00 +08:00"], ["后台 PID", str(armed["process_id"])], ["输出", "results/research_progress/qpi_cv_extension_remote_status_20260804_1030.json"], ["范围", "0 <= alpha,beta <= 1；排除负 alpha 与 Fig. 9"]]},
            {"kind": "note", "label": "保护规则", "style": "pending", "text": "若 high-100 终态，主流程先做远端 checksum、非覆盖回传和 validator；若仍运行，只登记资源与 ETA，不启动第二个 Julia。"},
        ],
    }
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    report["sections"] = [section] + [s for s in report["sections"] if s.get("title") != TITLE]
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · NEXT CHECK 10:30"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"title": TITLE, "pid": armed["process_id"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
