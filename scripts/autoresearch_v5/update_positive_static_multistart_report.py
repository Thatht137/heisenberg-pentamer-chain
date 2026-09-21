#!/usr/bin/env python3
"""把双初态静态生产规格写入长期报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results" / "research_progress" / "report.json"
RUN = ROOT / "results" / "autoresearch_v5_20260731" / "round10_positive_static_multistart_production"
SECTION_TITLE = "正区静态生产计算准备"


def build_section() -> dict[str, object]:
    comparison = json.loads(
        (RUN / "local_oracle_multistart_crosscheck" / "multistart-check.json").read_text(encoding="utf-8")
    )
    metrics = comparison["metrics"]
    budgets = comparison["budgets"]
    return {
        "title": SECTION_TITLE,
        "note": "2026-07-31 · 36-cell 双初态规格完成；尚未上传或启动服务器任务",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good",
                "label": "候选脊线双初态缺口已修复",
                "why": "旧 27-cell 规格只使用 center 初态，不满足候选边界验收标准；新规格为 12 个路径-初态变体 × 3 尺寸，共 36 cells。",
            },
            {
                "kind": "text",
                "text": "9 条左/脊/右基础路径和 L=40/60/80 保持不变。左、右路径只运行 center 初态；三个 ridge 路径在每个尺寸同时运行 center 与 domain 两种独立 Sz=0 产品态，Sz=1 始终使用 center。双初态分别完成完整 DMRG 与静态测量，再比较能量密度、能隙、弦关联距离剖面、全部最近邻键关联和中心五类 Schmidt 概率。",
            },
            {
                "kind": "table",
                "columns": ["层级", "任务数", "作用", "执行条件"],
                "rows": [
                    ["基础静态矩阵", "9 路径 × 3 尺寸 = 27", "左/脊/右与尺寸趋势", "全部单 cell gate 通过"],
                    ["ridge 初态复核", "3 ridge × 3 尺寸 = 9", "排除产品态依赖与亚稳态", "center/domain 五类诊断一致"],
                    ["pilot", "3 ridge × 2 初态，L=40 = 6", "先测最高风险点与实测成本", "通过后才允许 full"],
                    ["full", "36 cells，复用 pilot", "形成 Fig. 3–4 生产矩阵", "逐 cell 恢复，失败结果不覆盖"],
                ],
                "numeric": [False, True, False, False],
                "widths": ["18%", "22%", "30%", "30%"],
            },
            {
                "kind": "table",
                "columns": ["双初态诊断", "L=10 实测差异", "生产预算", "状态"],
                "rows": [
                    ["能量密度", f"{metrics['energy_density_abs']:.3e}", f"<={budgets['energy_density_abs_max']:.0e}", "Agreement"],
                    ["spin gap", f"{metrics['spin_gap_abs']:.3e}", f"<={budgets['spin_gap_abs_max']:.0e}", "Agreement"],
                    ["O_str(r) 最大绝对差", f"{metrics['string_profile_abs']:.3e}", f"<={budgets['string_profile_abs_max']:.0e}", "Agreement"],
                    ["键关联最大绝对差", f"{metrics['bond_correlation_abs']:.3e}", f"<={budgets['bond_correlation_abs_max']:.0e}", "Agreement"],
                    ["Schmidt 概率最大 L1", f"{metrics['schmidt_probability_l1']:.3e}", f"<={budgets['schmidt_probability_l1_max']:.0e}", "Agreement"],
                ],
                "numeric": [False, True, True, False],
                "widths": ["34%", "24%", "22%", "20%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["单 cell 方法", "OBC 有限链 DMRG；Sz=0 与 Sz=1；U(1) 守恒"],
                    ["生产设置", "maxdim=800/1000/1200；32 sweeps；cutoff=1e-11；8 threads；nice=10"],
                    ["单 cell 门槛", "两扇区 variance/L<=1e-8；discarded weight<=1e-9；Sz 正确；gap>=-1e-8"],
                    ["双初态门槛", "能量、gap、O_str(r)、bond correlation、Schmidt 概率全部通过预算"],
                    ["本地 center/domain oracle", "L=10，alpha=0.1，beta=0.5；五项均 Agreement"],
                    ["自动测试", "10 / 10 通过；旧 27-cell dry-run 仍兼容"],
                    ["服务器状态", "未上传、未启动，等待独立确认"],
                ],
            },
            {
                "kind": "list",
                "title": "执行与解释边界",
                "items": [
                    "所有 variant 的 alpha、beta 均非负；没有负 alpha 任务。",
                    "服务器强制离线，不包含下载或 Julia 包安装命令。",
                    "只有 center 的 ridge,L=80 cell 保存 MPS，避免重复大文件。",
                    "pilot 必须先完成 3 组双初态比较，不能只看 6 个单 cell 各自通过。",
                    "任一双初态诊断超预算即标记 unresolved，不得把 ridge 称为相界。",
                ],
            },
            {
                "kind": "code",
                "title": "生产与复核入口",
                "text": "results/autoresearch_v5_20260731/round10_positive_static_multistart_production/run_spec.json\nresults/autoresearch_v5_20260731/round10_positive_static_multistart_production/paths.json\nresults/autoresearch_v5_20260731/round10_positive_static_multistart_production/local_oracle_multistart_crosscheck/multistart-check.csv\nscripts/autoresearch_v5/run_positive_static_scan.py\nscripts/autoresearch_v5/analyze_positive_static_multistart.py\nscripts/autoresearch_v5/launch_positive_static_multistart_server.sh",
            },
            {
                "kind": "note",
                "label": "完成度边界",
                "style": "pending",
                "text": "本轮修复的是生产设计和验收缺口，不增加正区相图的物理完成度。只有服务器返回的 36-cell 数据通过单 cell、尺寸和双初态三层门槛后，Fig. 3–4 才能更新。",
            },
        ],
    }


def update_log(report: dict[str, object]) -> None:
    section = next(item for item in report["sections"] if item["title"] == "进展日志")
    table = next(block for block in section["blocks"] if block.get("kind") == "table")
    rows = {
        "静态生产管线": [
            "2026-07-31", "静态生产管线", "36-cell 双初态 DMRG 与完整静态测量规格",
            "旧 27-cell 规格被取代；pilot=6；10/10 测试通过；未提交", "准备完成",
        ],
        "静态双初态 oracle": [
            "2026-07-31", "静态双初态 oracle", "L=10 center/domain 五类诊断比较",
            "五项均 Agreement；最大差为 Schmidt L1=3.63e-15", "完成",
        ],
    }
    existing = {row[1]: index for index, row in enumerate(table["rows"]) if row}
    for name, row in rows.items():
        if name in existing:
            table["rows"][existing[name]] = row
        else:
            table["rows"].append(row)


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    report["sections"] = [item for item in report["sections"] if item["title"] != SECTION_TITLE]
    insert_at = next(
        (index for index, item in enumerate(report["sections"]) if item["title"] == "数值验收"),
        len(report["sections"]),
    )
    report["sections"].insert(insert_at, build_section())
    update_log(report)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已更新 {REPORT}")


if __name__ == "__main__":
    main()
