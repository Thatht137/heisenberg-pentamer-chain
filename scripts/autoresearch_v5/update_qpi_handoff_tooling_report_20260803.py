"""把严格 q=pi 回传、验收和出图工具链状态写入报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
TITLE = "2026-08-03 20:19 严格 q=pi 本地交接工具链"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    sections = [section for section in report["sections"] if section["title"] != TITLE]
    sections.insert(
        0,
        {
            "title": TITLE,
            "note": "不执行下载或新计算；为用户确认后的连续交接预先完成",
            "blocks": [
                {
                    "kind": "verdict",
                    "status": "good",
                    "label": "回传到论文图的本地流水线已 dry-run 就绪",
                    "why": "非覆盖式回传器、本地独立验收入口和 Python-only 论文图脚本均通过语法检查；严格 q=pi 两组测试合计 12/12 通过。",
                },
                {
                    "kind": "table",
                    "columns": ["阶段", "保护条件", "当前验证"],
                    "rows": [
                        ["回传", "必须 --confirmed；目标不存在；临时目录下载后原子落位", "dry-run 通过；26 文件、490122 bytes 已锁定"],
                        ["传输完整性", "22 个远端哈希、文件数、总字节、overall hash 再比较", "实现完成；失败不生成最终目录"],
                        ["本地独立验收", "重新读取 status/manifest/checksums，不信任传输 receipt", "dry-run 通过；接入 tmax=25/30 与四点 CV anchor"],
                        ["论文图", "同 alpha/beta/L/q/eta/OBC/Sz=0 实例锁", "Python 脚本语法与依赖通过"],
                        ["报告", "只写 HTML，不修改 paper/", "终态、验收和图形结果按新章节追加"],
                    ],
                    "widths": ["20%", "48%", "32%"],
                },
                {
                    "kind": "kv",
                    "pairs": [
                        ["绘图运行时", "D:/program/Anaconda3_2025.06/python.exe"],
                        ["绘图库", "matplotlib 3.10.0；NumPy 2.1.3；Pillow 11.1.0；无需联网安装"],
                        ["图契约", "183 x 105 mm；上方主谱，下方频率分辨谱差与门槛占用率"],
                        ["输出", "SVG/PDF/TIFF 600 dpi/PNG 300 dpi/sources JSON；文本保持可编辑"],
                        ["结论边界", "CV 稀疏点不覆盖主峰和主要积分权重时，完整动力学状态保持 incomplete"],
                    ],
                },
                {
                    "kind": "code",
                    "title": "确认后的执行链",
                    "text": "scripts/autoresearch_v5/fetch_qpi_tebd_results.py --confirmed\nscripts/autoresearch_v5/run_qpi_tebd_local_handoff.py\nD:/program/Anaconda3_2025.06/python.exe scripts/autoresearch_v5/plot_qpi_tebd_production.py\npython scripts/autoresearch_v5/<terminal-report-updater>.py\npython C:/Users/hh250/.codex/skills/report/render_report.py results/research_progress",
                },
                {
                    "kind": "code",
                    "title": "新增实现",
                    "text": "scripts/autoresearch_v5/fetch_qpi_tebd_results.py\nscripts/autoresearch_v5/run_qpi_tebd_local_handoff.py\nscripts/autoresearch_v5/plot_qpi_tebd_production.py",
                },
                {
                    "kind": "note",
                    "label": "授权状态",
                    "style": "pending",
                    "text": "实际下载仍未执行；fetch_authorized=false。本节只证明工具链准备完成，不替代用户对非覆盖式回传的明确确认。",
                },
            ],
        },
    )
    report["sections"] = sections
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03 20:19 CST"
    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"section": TITLE, "tests": "12/12"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
