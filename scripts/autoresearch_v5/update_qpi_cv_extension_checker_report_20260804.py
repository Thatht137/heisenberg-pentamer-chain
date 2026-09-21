"""把 round31 只读检查器登记到 HTML。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
TITLE = "2026-08-04 round31 q=pi CV 只读检查器就绪"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "只登记本地检查器；当前不执行 SSH，不修改远端进程。",
        "blocks": [
            {"kind": "verdict", "status": "good", "label": "恢复后可一次性读取 round31 全部 cell", "why": "检查器固定使用私钥、BatchMode 和 15 秒超时，只读 overall_progress、overall_status、四个 cell 的 progress/status/manifest/checkpoint 以及 Julia 进程表。"},
            {"kind": "kv", "pairs": [["脚本", "scripts/autoresearch_v5/check_qpi_cv_extension_remote_20260804.py"], ["输出建议", "保存新的只读状态快照"], ["远端写入", "False；不启动、不取消、不并行"]]},
            {"kind": "list", "title": "恢复后固定动作", "items": ["先运行只读检查器并保存快照", "若 cell 已终态，远端 checksum -> 新目录非覆盖回传 -> 本地 checksum", "validate_cv_run.py -> assemble_qpi_cv_anchors.py -> CV/TEBD 交叉分析"]},
            {"kind": "note", "label": "范围", "style": "pending", "text": "只允许 0 <= alpha,beta <= 1；排除负 alpha 和 Fig. 9；在只读快照确认前不启动第二个 Julia。"},
        ],
    }
    report["sections"] = [item for item in report["sections"] if item["title"] != TITLE]
    report["sections"].insert(1, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · ROUND31 RECOVERY READY"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"title": TITLE}, ensure_ascii=False))


if __name__ == "__main__":
    main()
