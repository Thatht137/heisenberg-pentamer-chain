#!/usr/bin/env python3
"""由已审计的 R14 生成器派生 R18 续跑包。"""

from __future__ import annotations

from pathlib import Path


SOURCE = Path(__file__).with_name("make_negative_phase_stage_b_practical_v2_after_bounded_r14.py")


def transform(source: str) -> str:
    replacements = [
        ("R14终态后生成跳过不可评估点的 Stage B 续跑包。", "R17终态后生成跳过不可评估点的 Stage B 续跑包。"),
        ('STAGE_NAME = "stage-b-negative-coarse-r15-remaining50"', 'STAGE_NAME = "stage-b-negative-coarse-r18-remaining20"'),
        ('default="stage-b-negative-coarse-r14-remaining65"', 'default="stage-b-negative-coarse-r17-remaining35"'),
        ("R14 必须提供15组 validator 与回传证据", "R17 必须提供15组 validator 与回传证据"),
        ("R14 终态必须是14 pass/1 fail", "R17 终态必须是14 pass/1 fail"),
        ("R14 失败不是64-sweep非方差终态", "R17 失败不是64-sweep非方差终态"),
        ("R14 证据包含计划外 cell", "R17 证据包含计划外 cell"),
        ('!= 44:', '!= 71:'),
        ("accepted index 未形成44个唯一物理点", "accepted index 未形成71个唯一物理点"),
        ('index["count"] = 44', 'index["count"] = 71'),
        ('bounded.get("count") != 1 or len(bounded.get("records", [])) != 1', 'bounded.get("count") != 4 or len(bounded.get("records", [])) != 4'),
        ("R14 既有 bounded 索引异常", "R17 既有 bounded 索引异常"),
        ('bounded["count"] = 2', 'bounded["count"] = 5'),
        ('evidence_out = STAGE / "r14-terminal-evidence-index.json"', 'evidence_out = STAGE / "r17-terminal-evidence-index.json"'),
        ('old_id.replace("negb14-", "negb15-", 1)', 'old_id.replace("negb17-", "negb18-", 1)'),
        ('cell["stage"] = "B-R15-practical-v2-remaining50"', 'cell["stage"] = "B-R18-practical-v2-remaining20"'),
        ('cell["r14_cell_id"] = old_id', 'cell["r17_cell_id"] = old_id'),
        ("R14终态验收后续跑；保留原预算且上限64", "R17终态验收后续跑；保留原预算且上限64"),
        ("if len(cells) != 50 or len({key(cell[\"params\"]) for cell in cells}) != 50:", "if len(cells) != 20 or len({key(cell[\"params\"]) for cell in cells}) != 20:"),
        ("R15剩余点数量或唯一性错误", "R18剩余点数量或唯一性错误"),
        ('"run_id": "pentamer-negative-phase-stage-b-r15-practical-v2-remaining50-20260901"', '"run_id": "pentamer-negative-phase-stage-b-r18-practical-v2-remaining20-20260905"'),
        ('"scope": "Stage B Practical V2 remaining50 after R14 terminal evidence"', '"scope": "Stage B Practical V2 remaining20 after R17 terminal evidence"'),
        ('"r14_terminal_evidence": relative(evidence_out)', '"r17_terminal_evidence": relative(evidence_out)'),
        ('"r14_terminal_evidence_sha256": sha256(evidence_out)', '"r17_terminal_evidence_sha256": sha256(evidence_out)'),
        ('"prior_accepted_physical_points": 44', '"prior_accepted_physical_points": 71'),
        ('"bounded_physical_points": 2', '"bounded_physical_points": 5'),
        ('"stage": "B-R15-practical-v2-remaining50"', '"stage": "B-R18-practical-v2-remaining20"'),
        ('"bounded_actions_excluded": 2', '"bounded_actions_excluded": 5'),
        ('"cell_count": 50', '"cell_count": 20'),
        ('"eta_hours": {"low": 10, "high": 18}', '"eta_hours": {"low": 4, "high": 8}'),
        ('f"{STAGE_REL}/r14-terminal-evidence-index.json"', 'f"{STAGE_REL}/r17-terminal-evidence-index.json"'),
        ('"accepted": 44', '"accepted": 71'),
        ('"bounded": 2', '"bounded": 5'),
        ('"remaining": 50', '"remaining": 20'),
    ]
    for old, new in replacements:
        if old not in source:
            raise RuntimeError(f"派生锚点缺失: {old}")
        source = source.replace(old, new)
    return source


def main() -> int:
    namespace = {"__name__": "_r18_generator", "__file__": str(SOURCE)}
    exec(compile(transform(SOURCE.read_text(encoding="utf-8")), str(SOURCE), "exec"), namespace)
    return int(namespace["main"]())


if __name__ == "__main__":
    raise SystemExit(main())
