"""把本机 Julia 环境限制追加到离线研究报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results" / "research_progress" / "report.json"
TITLE = "2026-08-03 14:21 本机 Julia 环境边界复核"


def build_section() -> dict[str, object]:
    return {
        "title": TITLE,
        "note": "本机只读环境检查；未访问服务器、未启动计算",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "本地 Julia 项目测试被 Windows ACL 阻断",
                "why": "Julia 1.11.5 可以启动，但 Pkg.activate 无法写用户目录的 manifest_usage.toml.pid，Downloads 预编译又无法读取 ~/.ssh/known_hosts。",
            },
            {
                "kind": "table",
                "columns": ["检查", "结果", "解释"],
                "rows": [
                    ["Julia 版本", "1.11.5，可启动", "版本本身没有异常"],
                    ["项目测试", "未运行至 TestSet", "Pkg 日志锁在加载阶段失败"],
                    ["临时 depot", "已清理约 15 MB", "不留下本机测试残留"],
                    ["生产环境", "服务器 Julia 1.12.3 已审计", "以服务器 54/54 与生产 smoke 为准"],
                ],
                "widths": ["24%", "32%", "44%"],
            },
            {
                "kind": "verdict",
                "status": "good",
                "label": "Python 生产入口仍通过 21/21",
                "why": "progress、可恢复 CV、静态管线、oracle 和 TEBD 交叉验收均通过；compileall 与 HTML QA 也通过。",
            },
            {
                "kind": "kv",
                "pairs": [
                    ["结论边界", "ACL 错误不作为模型失败，不替代服务器数值验收"],
                    ["服务器策略", "不在断网服务器执行 Pkg.add/update/instantiate；继续使用已审计 Julia 1.12.3"],
                    ["下一动作", "北京时间 16:20 只读检查 L=80 anchor 和 TEBD supervisor"],
                    ["范围", "0 <= alpha,beta <= 1；负 alpha 与 Fig. 9 排除"],
                ],
            },
            {
                "kind": "code",
                "title": "证据文件",
                "text": "docs/julia_environment_audit_20260729.md\nresults/research_progress/server_resource_snapshot_20260803_1401.json\nscripts/autoresearch_v5/test_progress.py\nscripts/autoresearch_v5/test_resumable_wrapper.py\nscripts/autoresearch_v5/test_resume_oracle_analyzer.py\nscripts/autoresearch_v5/test_positive_static_pipeline.py\nscripts/autoresearch_v5/test_tebd_crosscheck_analyzer.py",
            },
        ],
    }


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    report["sections"] = [section for section in report["sections"] if section["title"] != TITLE]
    report["sections"].insert(0, build_section())
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(REPORT), "section": TITLE}, ensure_ascii=False))


if __name__ == "__main__":
    main()
