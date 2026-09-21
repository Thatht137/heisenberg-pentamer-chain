#!/usr/bin/env python3
"""把 PR #244 相图扫描 Skill 的安装和本地验证写入长期 HTML 报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results" / "research_progress" / "report.json"
SECTION_TITLE = "PR #244 相图扫描 Skill"


def build_section() -> dict[str, object]:
    return {
        "title": SECTION_TITLE,
        "note": "2026-07-31 · 已合并提交 a0562a5；首段服务器 batch 已启动",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good",
                "label": "phase-diagram Skill 已下载并用于首段扫描",
                "why": "PR #244 已合并；本地控制器流程通过，首段 30-cell 计算已在服务器启动。",
            },
            {
                "kind": "text",
                "text": "这个 Skill 是一个有限尺寸 crossing 控制器：它在本地根据 dimensionless observable 的带误差符号差决定 coarse grid、统计量升级、二分细化和尺寸 promotion；真正的计算单元仍由 parameter-scan 生成，服务器只接收 compute entrypoint 与 run spec，manifest 回传后才在本地 collect 和验收。它不直接给 crossing 命名相，也不替代 Heisenberg 模型卡。",
            },
            {
                "kind": "table",
                "columns": ["项目", "结果", "状态"],
                "rows": [
                    ["PR", "Feature: add adaptive phase-diagram skill · #244 · merged", "确认"],
                    ["来源提交", "a0562a508d65db62fbc9aebbc196b794762da6c0", "锁定"],
                    ["Skill 路径", "skills/phase-diagram → ~/.codex/skills/phase-diagram", "已安装"],
                    ["内容", "SKILL.md、references/contracts.md、scripts/phase_diagram.py", "完整"],
                    ["本地 smoke", "scaffold → init → check → ingest → inspect；首批 6 个 ACTION_REQUIRED cells", "通过"],
                    ["物理计算", "统一重跑后 cell-0001–0016 已通过；当前 cell-0017 由服务器 PID=3436382 顺序运行", "进行中"],
                ],
                "numeric": [False, False, False],
                "widths": ["23%", "53%", "24%"],
            },
            {
                "kind": "verdict",
                "status": "warn",
                "label": "上游控制器当前不能原生运行于 Windows",
                "why": "phase_diagram.py 直接 import POSIX-only fcntl；本机使用临时兼容层完成流程 smoke test，未修改上游 Skill。",
            },
            {
                "kind": "heading",
                "level": 3,
                "text": "本项目的正区使用协议（已固化）",
            },
            {
                "kind": "list",
                "title": "建议先确认的科学输入",
                "items": [
                    "控制轴只取 alpha=[0,0.125,0.25,0.50,1.00]，边界为 [0,1]，不涉及负 alpha。",
                    "beta 切片固定为 [0.10,0.50,0.90]；尺寸序列为 L=[40,60,80]，先完成 40/60 粗扫。",
                    "dimensionless observable 固定为中心窗口 R(L)=1-S(pi-2pi/M)/S(pi)，误差来自 center/domain 双初态半差和截断下限。",
                    "候选 cell 由 parameter-scan 生成；phase policy、state、report 和 observations 永远留在本地。",
                    "只有最终相邻尺寸对达到声明的 sigma 和 bracket width，才能汇报有限尺寸边界；不能仅凭热图颜色命名相。",
                ],
            },
            {
                "kind": "note",
                "label": "首段服务器计算进行中",
                "style": "info",
                "text": "首段已按确认上传；cell-0001 双初态验收通过。完整 batch 完成后再回传 manifests 并由本地 controller 计算 crossing。",
            },
            {
                "kind": "code",
                "title": "已安装文件",
                "text": "~/.codex/skills/phase-diagram/SKILL.md\n~/.codex/skills/phase-diagram/references/contracts.md\n~/.codex/skills/phase-diagram/scripts/phase_diagram.py\ndocs/phase_diagram_execution_plan.md",
            },
            {
                "kind": "note",
                "label": "执行边界",
                "style": "info",
                "text": "服务器只运行上传的 compute entrypoint 和 run spec；phase controller、state、认证信息仍留在本地。当前不做负 alpha，也不复现 Fig. 9。",
            },
        ],
    }


def find_block(section: dict[str, object], kind: str) -> dict[str, object]:
    return next(block for block in section["blocks"] if block.get("kind") == kind)


def upsert_row(table: dict[str, object], row: list[str]) -> None:
    for index, old in enumerate(table["rows"]):
        if old and old[0] == row[0]:
            table["rows"][index] = row
            return
    table["rows"].append(row)


def update_latest(report: dict[str, object]) -> None:
    section = next(item for item in report["sections"] if item["title"] == "最新成果")
    table = find_block(section, "table")
    upsert_row(table, ["PR #244 相图扫描 Skill", "已安装；cell-0001–0016 通过，当前 cell-0017", "controller 可用，服务器 batch 已启动"])


def update_log(report: dict[str, object]) -> None:
    section = next(item for item in report["sections"] if item["title"] == "进展日志")
    table = find_block(section, "table")
    upsert_row(table, ["2026-07-31", "PR #244 相图扫描 Skill", "下载、验证并用于正区首段扫描", "本地 durable workflow 通过；cell-0001–0016 通过；远端 batch 已启动", "运行中"])


def update_outputs(report: dict[str, object]) -> None:
    section = next(item for item in report["sections"] if item["title"] == "成果文件")
    code = find_block(section, "code")
    additions = [
        "~/.codex/skills/phase-diagram/SKILL.md",
        "~/.codex/skills/phase-diagram/references/contracts.md",
        "~/.codex/skills/phase-diagram/scripts/phase_diagram.py",
        "scripts/autoresearch_v5/update_phase_diagram_skill_report.py",
    ]
    lines = code["text"].splitlines()
    code["text"] = "\n".join(lines + [item for item in additions if item not in lines])


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    report["sections"] = [item for item in report["sections"] if item["title"] != SECTION_TITLE]
    insert_at = next(
        (index for index, item in enumerate(report["sections"]) if item["title"] == "数值验收"),
        len(report["sections"]),
    )
    report["sections"].insert(insert_at, build_section())
    update_latest(report)
    update_log(report)
    update_outputs(report)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已更新 {REPORT}")


if __name__ == "__main__":
    main()
