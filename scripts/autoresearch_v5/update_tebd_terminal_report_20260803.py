"""把 TEBD 首轮终态失败原因登记到 HTML 报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
AUDIT = ROOT / "results/research_progress/tebd_crosscheck_20260803.json"
TITLE = "2026-08-03 16:35 TEBD 首轮终态审计"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    diagnostics = audit["diagnostics"]
    sections = [section for section in report["sections"] if section["title"] != TITLE]
    sections.insert(
        1,
        {
            "title": TITLE,
            "note": "正区 alpha=0.23、beta=0.5、L=40、dt=0.025、tmax=15；首轮结果只作失败审计",
            "blocks": [
                {
                    "kind": "verdict",
                    "status": "bad",
                    "label": "TEBD 执行完成，但 raw-spectrum 门失败",
                    "why": "TEBD 600/600 步、Fourier 81/81 个 q 均完成；原始 Fourier 谱最小值 -2.0709，7689/14661 个网格点为负，因此 manifest accepted=false。",
                },
                {
                    "kind": "table",
                    "columns": ["检查项", "结果", "解释"],
                    "rows": [
                        ["TEBD 执行", "通过", "returncode=0，600/600 steps，约 501 s"],
                        ["Fourier 执行", "通过", "returncode=0，81/81 q，约 166 s"],
                        ["Correlation 原始文件", "通过", "JLD2 存在，有限且无 NaN/Inf"],
                        ["裁剪显示谱", "通过", "min=0；仅为显示输出，不作物理验收"],
                        ["Raw spectrum 非负性", "失败", f"min={diagnostics['raw_min']:.4f}；负点 {diagnostics['raw_negative_count']}/{diagnostics['raw_total_count']}"],
                    ],
                    "widths": ["27%", "20%", "53%"],
                },
                {
                    "kind": "kv",
                    "pairs": [
                        ["最负点", f"q index={diagnostics['raw_min_q_index']}、omega index={diagnostics['raw_min_omega_index']}；q={diagnostics['raw_min_q']:.4f}、omega={diagnostics['raw_min_omega']:.3f}"],
                        ["时间范围", "correlation 从 t=0.025 开始，tmax=15；未包含 t=0 样本"],
                        ["当前判断", "日志没有崩溃或线程错误；优先诊断有限时间窗/零时刻采样，再决定是否重跑"],
                        ["范围", "0 <= alpha,beta <= 1；负 alpha 与 Fig. 9 排除"],
                    ],
                },
                {
                    "kind": "list",
                    "title": "下一步",
                    "items": [
                        "保留本轮 correlation、raw spectrum 和 manifest，不把裁剪谱写成最终 DSF。",
                        "在本地/服务器用相同 correlation 做时间窗与 t=0 采样诊断；确认修复后再运行 dt/2。",
                        "只有 raw 非负、dt/dt2、时间窗和 CV/TEBD 主峰门全部通过，才提升动态结论等级。",
                    ],
                },
                {
                    "kind": "code",
                    "title": "失败证据",
                    "text": "results/research_progress/tebd_crosscheck_20260803.json\nresults/autoresearch_v5_20260802/round23_tebd_crosscheck/cell-alpha023-dt025-t15-auto/\nscripts/autoresearch_v5/audit_tebd_terminal_20260803.py",
                },
            ],
        },
    )
    report["sections"] = sections
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"section": TITLE, "status": audit["status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
