#!/usr/bin/env python3
"""由已审计的 R14 生成器派生 R17 续跑包。"""

from __future__ import annotations

from pathlib import Path


SOURCE = Path(__file__).with_name("make_negative_phase_stage_b_practical_v2_after_bounded_r14.py")


def transform(source: str) -> str:
    replacements = [
        ("R14终态后生成跳过不可评估点的 Stage B 续跑包。", "R16终态后生成跳过不可评估点的 Stage B 续跑包。"),
        ('STAGE_NAME = "stage-b-negative-coarse-r15-remaining50"', 'STAGE_NAME = "stage-b-negative-coarse-r17-remaining35"'),
        ('default="stage-b-negative-coarse-r14-remaining65"', 'default="stage-b-negative-coarse-r16-remaining36"'),
        ("if len(paths) != 15 or len(receipts) != 15:", "if len(paths) != 1 or len(receipts) != 1:"),
        ("R14 必须提供15组 validator 与回传证据", "R16 必须提供1组 validator 与回传证据"),
        ("if len(passed) != 14 or len(failed) != 1:", "if len(passed) != 0 or len(failed) != 1:"),
        ("R14 终态必须是14 pass/1 fail", "R16 终态必须是0 pass/1 fail"),
        (
            '''        or any(float(child["variance_per_site_sz0"]) > VARIANCE_MAX for child in children)
        or any(float(child["variance_per_site_sz1"]) > VARIANCE_MAX for child in children)
        or not any(float(child["spin_gap"]) < -1e-8 for child in children)''',
            '''        or not any(
            float(child["variance_per_site_sz0"]) > VARIANCE_MAX
            or float(child["variance_per_site_sz1"]) > VARIANCE_MAX
            for child in children
        )
        or any(float(child["spin_gap"]) < -1e-8 for child in children)
        or any("variance" not in item for item in failure.get("failures", []))''',
        ),
        ("R14 失败不是64-sweep非方差终态", "R16 失败不是64-sweep终态"),
        ("R14 证据包含计划外 cell", "R16 证据包含计划外 cell"),
        ('!= 44:', '!= 57:'),
        ("accepted index 未形成44个唯一物理点", "accepted index 未形成57个唯一物理点"),
        ('index["count"] = 44', 'index["count"] = 57'),
        ('bounded.get("count") != 1 or len(bounded.get("records", [])) != 1', 'bounded.get("count") != 3 or len(bounded.get("records", [])) != 3'),
        ("R14 既有 bounded 索引异常", "R16 既有 bounded 索引异常"),
        ('bounded["count"] = 2', 'bounded["count"] = 4'),
        ('evidence_out = STAGE / "r14-terminal-evidence-index.json"', 'evidence_out = STAGE / "r16-terminal-evidence-index.json"'),
        ('"summary": "14 pass/1 bounded"', '"summary": "0 pass/1 bounded"'),
        ('old_id.replace("negb14-", "negb15-", 1)', 'old_id.replace("negb16-", "negb17-", 1)'),
        ('cell["stage"] = "B-R15-practical-v2-remaining50"', 'cell["stage"] = "B-R17-practical-v2-remaining35"'),
        ('cell["r14_cell_id"] = old_id', 'cell["r16_cell_id"] = old_id'),
        ("R14终态验收后续跑；保留原预算且上限64", "R16终态验收后续跑；保留原预算且上限64"),
        ("if len(cells) != 50 or len({key(cell[\"params\"]) for cell in cells}) != 50:", "if len(cells) != 35 or len({key(cell[\"params\"]) for cell in cells}) != 35:"),
        ("R15剩余点数量或唯一性错误", "R17剩余点数量或唯一性错误"),
        ('"run_id": "pentamer-negative-phase-stage-b-r15-practical-v2-remaining50-20260901"', '"run_id": "pentamer-negative-phase-stage-b-r17-practical-v2-remaining35-20260904"'),
        ('"scope": "Stage B Practical V2 remaining50 after R14 terminal evidence"', '"scope": "Stage B Practical V2 remaining35 after R16 terminal evidence"'),
        ('"r14_terminal_evidence": relative(evidence_out)', '"r16_terminal_evidence": relative(evidence_out)'),
        ('"r14_terminal_evidence_sha256": sha256(evidence_out)', '"r16_terminal_evidence_sha256": sha256(evidence_out)'),
        ('"prior_accepted_physical_points": 44', '"prior_accepted_physical_points": 57'),
        ('"bounded_physical_points": 2', '"bounded_physical_points": 4'),
        ('"stage": "B-R15-practical-v2-remaining50"', '"stage": "B-R17-practical-v2-remaining35"'),
        ('"bounded_actions_excluded": 2', '"bounded_actions_excluded": 4'),
        ('"cell_count": 50', '"cell_count": 35'),
        ('"eta_hours": {"low": 10, "high": 18}', '"eta_hours": {"low": 7, "high": 13}'),
        ('f"{STAGE_REL}/r14-terminal-evidence-index.json"', 'f"{STAGE_REL}/r16-terminal-evidence-index.json"'),
        ('"accepted": 44', '"accepted": 57'),
        ('"bounded": 2', '"bounded": 4'),
        ('"remaining": 50', '"remaining": 35'),
    ]
    for old, new in replacements:
        if old not in source:
            raise RuntimeError(f"派生锚点缺失: {old}")
        source = source.replace(old, new)
    return source


def main() -> int:
    namespace = {"__name__": "_r17_generator", "__file__": str(SOURCE)}
    exec(compile(transform(SOURCE.read_text(encoding="utf-8")), str(SOURCE), "exec"), namespace)
    return int(namespace["main"]())


if __name__ == "__main__":
    raise SystemExit(main())
