#!/usr/bin/env python3
"""把本轮静态审计追加到长期 HTML 报告源文件。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "results" / "research_progress"
REPORT = REPORT_DIR / "report.json"
SELECTION_DIR = ROOT / "results" / "autoresearch_v5_20260730" / "round6_positive_static_selection"
DISTANCE_DIR = ROOT / "results" / "autoresearch_v5_20260730" / "round7_positive_string_distance"


def build_section() -> dict[str, object]:
    return {
        "title": "正区静态候选与弦关联审计",
        "note": "2026-07-30 · 只使用既有正区数据，不新增服务器计算",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "三条候选交叉尺度稳定，但不是相界",
                "why": "旧 40×60 地图在四种平滑尺度下给出 alpha≈0.05、0.075、0.10 的三个 beta 锚点；地图缺少生产级误差和尺寸证据。",
            },
            {
                "kind": "text",
                "text": "对旧正区地图的 |dO_str/dalpha| 做多尺度平滑、逐 beta 局部极大值和相邻五行一致性分析。beta≈0.10、0.50、0.90 三个锚点的一致率分别为 90%、100%、100%，目标位置在四种平滑尺度下均不漂移。为检验局部对比而不是只补单点，每个锚点保留左侧、脊线、右侧三个 alpha 网格点，共 9 个候选静态 cell。",
            },
            {
                "kind": "table",
                "columns": ["beta 锚点", "地图对应 beta", "候选 ridge alpha", "多尺度一致率", "相对行中位梯度", "状态"],
                "rows": [
                    ["0.10", "0.0983", "0.050", "90%", "14.45×", "待生产验证"],
                    ["0.50", "0.5008", "0.075", "100%", "30.21×", "待生产验证"],
                    ["0.90", "0.9034", "0.100", "100%", "7.04×", "待生产验证"],
                ],
                "numeric": [True, True, True, True, True, False],
                "widths": ["14%", "16%", "18%", "16%", "18%", "18%"],
            },
            {
                "kind": "figures",
                "items": [
                    {
                        "src": "positive_static_selection_20260730.png",
                        "caption": "侦察选点图。a：旧 O_str 地图和四种平滑尺度下的 |dO_str/dalpha| 脊线；b：脊线随 beta 的漂移及尺度包络；c：三个 beta 截面的左/脊/右括号点；d：一致性评分。低 beta 中段仍有不稳定分叉，因此只保留三个稳定锚点。",
                    },
                    {
                        "src": "positive_string_distance_20260730.png",
                        "caption": "正区弦关联距离审计。alpha=0.05 与 0.50、beta=0.5 的奇距离包络均随单胞距离衰减，L=60、80、100 趋势一致；这说明相图 O_str 是有限距离诊断量，不能单独证明长程序或相界。",
                    },
                ],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["地图覆盖", "40×60=2400 个正区点；仅有 O_str 和 energy"],
                    ["候选验证路径", "3 个 beta 锚点 × 左/脊/右 3 个 alpha = 9 个候选 cell"],
                    ["每个候选最低记录", "L=40/60/80、variance、truncation、actual D、spin gap、bond correlation、Schmidt 谱"],
                    ["距离审计", "alpha=0.05/0.50，beta=0.5，L=60/80/100；6 个原始文件"],
                    ["审计结论", "有限距离弦关联衰减；不支持把旧 O_str 色带解释为已证明长程序"],
                ],
            },
            {
                "kind": "code",
                "title": "复现入口",
                "text": "scripts/autoresearch_v5/select_positive_static_validation_points.py\nscripts/autoresearch_v5/audit_positive_string_distance.py\nresults/autoresearch_v5_20260730/round6_positive_static_selection/selection_summary.json\nresults/autoresearch_v5_20260730/round7_positive_string_distance/distance_audit_summary.json",
            },
            {
                "kind": "note",
                "label": "结论边界",
                "style": "pending",
                "text": "这轮只完成候选定位与既有数据审计，没有把任何点称为相界，也没有增加新的服务器任务。下一步生产计算应优先覆盖 9 个候选 cell；若左/脊/右的尺寸依赖和收敛证据不形成独立闭环，应在报告中保留为 crossover/不确定区。",
            },
        ],
    }


def append_progress_row(report: dict[str, object]) -> None:
    for section in report["sections"]:
        if section["title"] != "进展日志":
            continue
        for block in section["blocks"]:
            if block.get("kind") != "table" or not block.get("rows"):
                continue
            if any(row and row[1] == "正区静态选点" for row in block["rows"]):
                return
            block["rows"].extend([
                ["2026-07-30", "正区静态选点", "对 2400 点旧地图做多尺度脊线稳定性和局部括号选点", "3 个 beta 锚点、9 个候选 cell；稳定性不是相界证据", "完成"],
                ["2026-07-30", "正区弦关联审计", "复核 alpha=0.05/0.50、beta=0.5 的 L=60/80/100 距离数据", "奇距离包络随距离衰减；旧 O_str 只能作有限距离诊断", "完成"],
            ])
            return
    raise ValueError("未找到进展日志表")


def main() -> None:
    selection_figure = SELECTION_DIR / "positive_static_selection_20260730.png"
    distance_figure = DISTANCE_DIR / "positive_string_distance_20260730.png"
    for source in (selection_figure, distance_figure):
        if not source.exists():
            raise FileNotFoundError(source)
        shutil.copy2(source, REPORT_DIR / source.name)

    report = json.loads(REPORT.read_text(encoding="utf-8"))
    report["sections"] = [
        section for section in report["sections"]
        if section["title"] != "正区静态候选与弦关联审计"
    ]
    section = build_section()
    insert_at = next(
        (index for index, item in enumerate(report["sections"]) if item["title"] == "数值验收"),
        len(report["sections"]),
    )
    report["sections"].insert(insert_at, section)
    append_progress_row(report)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已更新 {REPORT}")


if __name__ == "__main__":
    main()
