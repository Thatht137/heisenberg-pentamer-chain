#!/usr/bin/env python3
"""把 L=80 尺寸晋级结果写入长期 HTML 报告源。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "results" / "research_progress"
REPORT = REPORT_DIR / "report.json"
RUN = ROOT / "results" / "autoresearch_v5_20260731" / "round18_final_phase_diagram_positive_L80"
OBS = RUN / "phase-diagram" / "observations_merged.json"
GUARD = RUN / "phase-diagram" / "positive_phase_guard.json"
CONTROLLER = RUN / "phase-diagram" / "report.json"


def load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def fmt(value: float) -> str:
    return f"{value:.6f}"


def build_section(observations: dict[str, object], guard: dict[str, object], controller: dict[str, object]) -> dict[str, object]:
    records = observations["records"]
    index = {(r["params"]["beta"], r["params"]["alpha"], r["params"]["L"]): r for r in records}
    rows = []
    for beta in sorted({key[0] for key in index}):
        for alpha in sorted({key[1] for key in index if key[0] == beta}):
            values = [index[(beta, alpha, size)]["value"] for size in (40, 60, 80)]
            rows.append([
                f"{beta:g}", f"{alpha:g}", *(fmt(float(value)) for value in values),
                fmt(float(values[2]) - float(values[1])),
            ])
    guard_status = guard["status"]
    return {
        "title": "L=80 尺寸晋级与相图最终验收",
        "note": "2026-08-02 · 正 alpha、正 beta；负 alpha 未执行",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "L=80 晋级完成，但未形成可验收相界",
                "why": "15/15 个 L=80 cell 通过；L=60/80 在 beta=0.1、0.5 全部同号，beta=0.9 的 alpha=0 仍因双初态误差 INCONCLUSIVE。",
            },
            {
                "kind": "text",
                "text": "在首段 L=40/60 粗扫基础上补齐 L=80，固定尺寸对升级为 L=60/80。所有参数仍位于 alpha>=0、beta>=0，L=80 采用 16 个五聚体、OBC、Sz=0/1、maxdim=1200、cutoff=1e-11。guard 的结果是 beta=0.1 与 0.5 无显著 crossing；beta=0.9 只有 alpha=0 落入误差门槛，因此 controller 保持 HUMAN_REQUIRED，不报告相界数值或相名。",
            },
            {
                "kind": "table",
                "columns": ["beta", "alpha", "R(40)", "R(60)", "R(80)", "Delta R(60->80)"],
                "rows": rows,
                "numeric": [True, True, True, True, True, True],
                "widths": ["10%", "12%", "19%", "19%", "19%", "21%"],
            },
            {
                "kind": "figures",
                "items": [
                    {
                        "src": "positive_phase_size_promotion_20260802.png",
                        "caption": "L=40/60 与 L=60/80 的结构因子比差值 Delta R。误差棒由两尺寸 manifest 误差合成；零线表示 crossing 判据，beta=0.1 和 0.5 的所有点均在零线同侧，beta=0.9 的 alpha=0 误差棒覆盖零线。",
                    }
                ],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["最终运行", "results/autoresearch_v5_20260731/round18_final_phase_diagram_positive_L80"],
                    ["L=80 完成度", "15/15 accepted；所有最终 manifest、checksums 和 provenance 通过"],
                    ["预算例外", "l80-cell-0012 与 l80-cell-0015 使用 64 sweeps；原 32-sweep 失败目录保留"],
                    ["controller", f"{controller['status']}；问题：{controller.get('question', '无')}"],
                    ["positive guard", f"{guard_status}；beta=0.1/0.5 无 crossing，beta=0.9 alpha=0 不确定"],
                    ["负 alpha", "未生成、未上传、未进入 observations 或图表"],
                ],
            },
            {
                "kind": "note",
                "label": "验收与 Skill 改进记录",
                "style": "pending",
                "text": "发现 phase cell 验收器把第 1 个预热 sweep 的 discarded weight 当成最终门槛，导致 l80-cell-0015 在 32/64 sweeps 都被误拒绝；现已保留全 sweep 最大值并改用最终三个零噪声 sweep。另发现一次 scp 远端路径拼写错误、两次只读 SSH 审核超时，以及 Windows 默认 GBK 读取 UTF-8 report.json 的渲染问题；这些问题均未污染结果。",
            },
        ],
    }


def main() -> None:
    report = load(REPORT)
    observations = load(OBS)
    guard = load(GUARD)
    controller = load(CONTROLLER)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-02"
    report["sections"] = [section for section in report["sections"] if section["title"] != "L=80 尺寸晋级与相图最终验收"]
    section = build_section(observations, guard, controller)
    insert_at = next((i for i, item in enumerate(report["sections"]) if item["title"] == "数值验收"), len(report["sections"]))
    report["sections"].insert(insert_at, section)
    for item in report["sections"]:
        if item["title"] != "进展日志":
            continue
        for block in item["blocks"]:
            if block.get("kind") != "table":
                continue
            if not any(row and row[1] == "L=80 尺寸晋级" for row in block.get("rows", [])):
                block["rows"].extend([
                    ["2026-08-02", "L=80 尺寸晋级", "正区 15 个 L=80 cell，补齐 40/60/80 尺寸序列", "15/15 accepted；L=60/80 guard=INCONCLUSIVE；不命名相界", "完成（待决策）"],
                    ["2026-08-02", "截断验收 Skill 修正", "区分预热 sweep 与最终零噪声 sweep 的 discarded weight", "l80-cell-0015 由误拒绝变为通过；全 sweep 最大值继续留档", "完成"],
                ])
            break
        break
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(REPORT), "section": section["title"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
