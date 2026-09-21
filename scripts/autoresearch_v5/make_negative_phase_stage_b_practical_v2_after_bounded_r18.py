#!/usr/bin/env python3
"""由已审计的 R14 生成器派生 R19 续跑包。"""

from __future__ import annotations

from pathlib import Path


SOURCE = Path(__file__).with_name("make_negative_phase_stage_b_practical_v2_after_bounded_r14.py")


def transform(source: str) -> str:
    replacements = [
        ("R14终态后生成跳过不可评估点的 Stage B 续跑包。", "R18终态后生成跳过不可评估点的 Stage B 续跑包。"),
        ('STAGE_NAME = "stage-b-negative-coarse-r15-remaining50"', 'STAGE_NAME = "stage-b-negative-coarse-r19-remaining19"'),
        ('default="stage-b-negative-coarse-r14-remaining65"', 'default="stage-b-negative-coarse-r18-remaining20"'),
        ("if len(paths) != 15 or len(receipts) != 15:", "if len(paths) != 1 or len(receipts) != 1:"),
        ("R14 必须提供15组 validator 与回传证据", "R18 必须提供1组 validator 与回传证据"),
        ("if len(passed) != 14 or len(failed) != 1:", "if len(passed) != 0 or len(failed) != 1:"),
        ("R14 终态必须是14 pass/1 fail", "R18 终态必须是0 pass/1 fail"),
        ("or any(float(child[\"variance_per_site_sz0\"]) > VARIANCE_MAX for child in children)\n        or any(float(child[\"variance_per_site_sz1\"]) > VARIANCE_MAX for child in children)\n        or not any(float(child[\"spin_gap\"]) < -1e-8 for child in children)", "or not any(float(child[\"variance_per_site_sz0\"]) > VARIANCE_MAX or float(child[\"variance_per_site_sz1\"]) > VARIANCE_MAX for child in children)\n        or any(float(child[\"spin_gap\"]) < -1e-8 for child in children)"),
        ("R14 失败不是64-sweep非方差终态", "R18 失败不是64-sweep纯方差终态"),
        ("R14 证据包含计划外 cell", "R18 证据包含计划外 cell"),
        ('!= 44:', '!= 71:'),
        ("accepted index 未形成44个唯一物理点", "accepted index 未保持71个唯一物理点"),
        ('index["count"] = 44', 'index["count"] = 71'),
        ('bounded.get("count") != 1 or len(bounded.get("records", [])) != 1', 'bounded.get("count") != 5 or len(bounded.get("records", [])) != 5'),
        ("R14 既有 bounded 索引异常", "R18 既有 bounded 索引异常"),
        ('"failed_gate": "nonnegative_gap"', '"failed_gate": "variance_per_site_sz1"'),
        ('bounded["count"] = 2', 'bounded["count"] = 6'),
        ('evidence_out = STAGE / "r14-terminal-evidence-index.json"', 'evidence_out = STAGE / "r18-terminal-evidence-index.json"'),
        ('old_id.replace("negb14-", "negb15-", 1)', 'old_id.replace("negb18-", "negb19-", 1)'),
        ('cell["stage"] = "B-R15-practical-v2-remaining50"', 'cell["stage"] = "B-R19-practical-v2-remaining19"'),
        ('cell["r14_cell_id"] = old_id', 'cell["r18_cell_id"] = old_id'),
        ("R14终态验收后续跑；保留原预算且上限64", "R18终态验收后续跑；保留原预算且上限64"),
        ('if len(cells) != 50 or len({key(cell["params"]) for cell in cells}) != 50:', 'if len(cells) != 19 or len({key(cell["params"]) for cell in cells}) != 19:'),
        ("R15剩余点数量或唯一性错误", "R19剩余点数量或唯一性错误"),
        ('"run_id": "pentamer-negative-phase-stage-b-r15-practical-v2-remaining50-20260901"', '"run_id": "pentamer-negative-phase-stage-b-r19-practical-v2-remaining19-20260906"'),
        ('"scope": "Stage B Practical V2 remaining50 after R14 terminal evidence"', '"scope": "Stage B Practical V2 remaining19 after R18 terminal evidence"'),
        ('"r14_terminal_evidence": relative(evidence_out)', '"r18_terminal_evidence": relative(evidence_out)'),
        ('"r14_terminal_evidence_sha256": sha256(evidence_out)', '"r18_terminal_evidence_sha256": sha256(evidence_out)'),
        ('"prior_accepted_physical_points": 44', '"prior_accepted_physical_points": 71'),
        ('"bounded_physical_points": 2', '"bounded_physical_points": 6'),
        ('"stage": "B-R15-practical-v2-remaining50"', '"stage": "B-R19-practical-v2-remaining19"'),
        ('"bounded_actions_excluded": 2', '"bounded_actions_excluded": 6'),
        ('"cell_count": 50', '"cell_count": 19'),
        ('"eta_hours": {"low": 10, "high": 18}', '"eta_hours": {"low": 4, "high": 8}'),
        ('f"{STAGE_REL}/r14-terminal-evidence-index.json"', 'f"{STAGE_REL}/r18-terminal-evidence-index.json"'),
        ('"accepted": 44', '"accepted": 71'),
        ('"bounded": 2', '"bounded": 6'),
        ('"remaining": 50', '"remaining": 19'),
    ]
    for old, new in replacements:
        if old not in source:
            raise RuntimeError(f"派生锚点缺失: {old}")
        source = source.replace(old, new)
    return source


def main() -> int:
    namespace = {"__name__": "_r19_generator", "__file__": str(SOURCE)}
    exec(compile(transform(SOURCE.read_text(encoding="utf-8")), str(SOURCE), "exec"), namespace)
    return int(namespace["main"]())


if __name__ == "__main__":
    raise SystemExit(main())
