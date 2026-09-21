#!/usr/bin/env python3
"""生成 C10/C11 的关闭条件验收表。"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
OUT = ROOT / "results/research_progress/remaining_claim_closure_20260804.json"
ROUND38 = ROOT / "results/research_progress/round38_mesh0051_acceptance_20260804.json"
ACCEPTED7 = ROOT / "results/autoresearch_v5_20260805/round40_cv_tebd_accepted7_analysis/cross-method-check.json"
TEBD = ROOT / "results/autoresearch_v5_20260803/round30_qpi_maxdim96_analysis/summary.json"
PHASE = ROOT / "results/research_progress/positive_phase_audit_20260803.json"
ROUND43 = ROOT / "results/research_progress/round43_phase1_submission_20260806.json"
TITLE = "2026-08-04 C10/C11 剩余主张关闭条件"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    round38 = json.loads(ROUND38.read_text(encoding="utf-8"))
    cross = json.loads(ACCEPTED7.read_text(encoding="utf-8"))
    tebd = json.loads(TEBD.read_text(encoding="utf-8"))
    phase = json.loads(PHASE.read_text(encoding="utf-8"))
    round43 = json.loads(ROUND43.read_text(encoding="utf-8"))
    c10_numeric = (
        tebd["status"] == "pass"
        and cross["diagnostics"]["shared_window_weight_relative_delta"] <= 0.15
        and max(cross["diagnostics"]["shared_point_relative_differences"]) <= 0.1
    )
    c11_bounded = (
        phase["guard"]["status"] == "NO_SIGNIFICANT_CROSSING"
        and phase["records"]["internal_difference_not_significant"] == 0
        and round38["acceptance"]["children_accepted"]
    )
    payload = {
        "schema_version": 1,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True},
        "claims": {
            "C10": {
                "strong_claim": "正区生产谱由有效链连续谱与局域多重态共同归属",
                "status": "pending_coverage",
                "supported_now": c10_numeric,
                "supported_statement": "七个 accepted CV 点与 TEBD 的逐点最大差为 6.40%，共享窗积分差为 1.53%。",
                "missing": ["通过 residual 门的 0.00--0.15 低频网格", "主峰内部包围", "完整 0--1.5 积分窗验收"],
                "closure_rule": "CV 主峰被内部包围、0--1.5 覆盖且 peak/weight 两门均通过后，才升级为 Agreement。",
            },
            "C11": {
                "strong_claim": "正 alpha,beta 区域的二维基态结构已确定",
                "status": "bounded_statement_supported_strong_claim_pending",
                "supported_now": c11_bounded,
                "supported_statement": "当前 40/60/80 有限尺寸正区数据未见可验收内部 crossing。",
                "missing": ["能支持热力学相名或完整二维结构的独立序参量/临界标度", "round38 双初态半差仍高于 1e-3"],
                "closure_rule": "若没有相反符号 bracket，只保留有限尺寸无 crossing 表述，不升级为热力学单相证明。",
            },
        },
        "next_compute": {
            "running": "round43 phase A: omega=0.20 -> 0.15 -> 0.10 -> 0.05",
            "after_terminal": "四点 residual 全部<=1e-5 后，才从 omega=0.05 checkpoint 启动 phase B 的 omega=0.00。",
            "new_parallel_job_now": False,
        },
        "source_sha256": {path.relative_to(ROOT).as_posix(): sha256(path) for path in [ROUND38, ACCEPTED7, TEBD, PHASE, ROUND43]},
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "区分可写的有界表述和仍待证明的强主张；不修改 paper。",
        "blocks": [
            {"kind": "verdict", "status": "warn", "label": "C10/C11 强主张仍待关闭，但两者已有可写的有界结论", "why": "C10 数值一致但频率覆盖不足；C11 有限尺寸无 crossing 稳健，但不能升级为热力学二维相图。"},
            {"kind": "table", "columns": ["主张", "当前可支持", "仍缺证据", "关闭规则"], "rows": [
                ["C10", "七点最大差 6.40%；共享窗积分差 1.53%", "0.00--0.15 合格网格；主峰包围；完整积分窗", "覆盖完整且 peak/weight 门通过"],
                ["C11", "40/60/80 正区内部未见可验收 crossing", "热力学序参量/标度；round38 半差仍为 1.791e-3", "无 bracket 时只保留有限尺寸表述"],
            ], "widths": ["12%", "30%", "30%", "28%"]},
            {"kind": "kv", "pairs": [["机器可读验收表", "results/research_progress/remaining_claim_closure_20260804.json"], ["终态交接计划", "docs/round43_compute_plan_20260805.md"], ["当前交付门", "8/9；仅 final_dynamic_claim_gate 未关闭"], ["服务器当前任务", "round43 phase A / 四点降频 warm-start"], ["下一计算", "阶段 A 四点全部通过后启动 phase B omega=0.00"]]},
            {"kind": "note", "label": "禁止升级", "style": "pending", "text": "共享子窗的良好一致性不能替代完整 0--1.5 积分窗；有限尺寸无 crossing 不能写成热力学极限单相或命名相界。"},
        ],
    }
    report["sections"] = [section] + [s for s in report["sections"] if s.get("title") != TITLE]
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-06 · CLAIMS 12/12 BOUNDED · DELIVERY 8/9"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"C10": payload["claims"]["C10"]["status"], "C11": payload["claims"]["C11"]["status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
