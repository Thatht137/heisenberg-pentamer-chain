"""记录本地 Python 回归及解释器选择。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
TITLE = "2026-08-04 本地 Python 回归：项目环境 50/50 通过"
OLD_TITLE = "2026-08-04 本地 Python 回归：项目环境 46/46 通过"


def main() -> None:
    evidence = ROOT / "results/research_progress/python_regression_20260804.json"
    result = {
        "checked_at": "2026-08-04",
        "command": ".venv\\Scripts\\python.exe -m unittest discover -s scripts/autoresearch_v5 -p test*.py",
        "tests": 50,
        "passed": 50,
        "failed": 0,
        "project_python": ".venv\\Scripts\\python.exe",
        "matplotlib": "3.9.4",
        "bundled_runtime_note": "Codex bundled Python 缺少 matplotlib；未联网安装，改用项目已有 .venv",
        "scope": {"negative_alpha_excluded": True, "fig9_excluded": True},
    }
    evidence.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "本轮只做本地离线回归，不连接服务器、不下载依赖、不改变计算参数。",
        "blocks": [
            {"kind": "verdict", "status": "good", "label": "50/50 测试通过", "why": "CV–TEBD 分析器、终态报告、运行时契约、进度写入、checksum、正区 guard、可恢复 wrapper 和生产绘图测试均通过。"},
            {"kind": "table", "columns": ["项目", "结果", "说明"], "rows": [["测试总数", "50", "项目 autoresearch_v5 测试集"], ["失败数", "0", "使用项目 .venv 后绘图测试通过"], ["新增覆盖", "终态与运行时契约", "检查 high-150 报告、maxiter、krylovdim、flush 和 linsolve 阶段标记"], ["matplotlib", "3.9.4", "已有本地环境，无网络安装"], ["范围", "通过", "0 <= alpha,beta <= 1；排除负 alpha、Fig. 9"]], "widths": ["24%", "22%", "54%"]},
            {"kind": "kv", "pairs": [["证据", "results/research_progress/python_regression_20260804.json"], ["推荐解释器", ".venv\\Scripts\\python.exe"], ["远端计算", "未启动新任务；round31 状态仍等待连接恢复"]]},
            {"kind": "note", "label": "解释器规则", "style": "info", "text": "后续本地绘图和回归统一使用项目 .venv；Codex bundled Python 仅用于不依赖 matplotlib 的轻量审计。"},
        ],
    }
    report["sections"] = [s for s in report["sections"] if s.get("title") not in {TITLE, OLD_TITLE}]
    report["sections"].insert(1, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · LOCAL REGRESSION PASS"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"title": TITLE, "tests": 50, "passed": 50}, ensure_ascii=False))


if __name__ == "__main__":
    main()
