#!/usr/bin/env python3
"""记录低频主峰包围所需的条件计算。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
RECORD = ROOT / "results/research_progress/round42_qpi_cv_low000_conditional_plan_20260805.json"
TITLE = "2026-08-05 round42 q=pi omega=0.00 条件计算计划"


def main() -> None:
    record = {
        "schema_version": 1,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "conditional_not_started",
        "trigger": {
            "low005_validator_pass": True,
            "server_has_no_heavy_julia": True,
            "high150_validator_pass": True,
        },
        "reason": (
            "omega=0.05 与 1.50 只能补齐端点；严格 analyzer 要求主峰不是 CV 网格端点。"
            "新增 omega=0.00 后，0.05 主峰才可由 0.00 和 0.20 两侧包围。"
        ),
        "parameters": {
            "alpha": 0.23,
            "beta": 0.5,
            "L": 40,
            "q_over_pi": 1.0,
            "eta": 0.1,
            "omega": 0.0,
            "dmrg_maxdim": 320,
            "cv_maxdim": 800,
            "nsweeps": 20,
            "max_cv_residual": 1e-5,
            "threads": 4,
        },
        "expected_wall_minutes": [60, 180],
        "acceptance": [
            "自然终态且 returncode=0",
            "远端和本地 SHA-256 全部通过",
            "validate_cv_run.py 全部通过",
            "relative residual<=1e-5",
            "非负性、DMRG 方差和截断误差通过",
        ],
        "decision": {
            "on_pass": "组装 0.00,0.05,...,1.50 accepted-only，并重跑 CV--TEBD analyzer。",
            "on_fail": "隔离结果，停止低频追加计算，Fig.6--8 保持 bounded。",
        },
        "planning_proxy": {
            "evidence_grade": "planning_only_failed_residual_points",
            "cv_peak_omega": 0.05,
            "tebd_peak_omega": 0.05,
            "peak_delta": 0.0,
            "projected_window_weight_relative_delta": 0.018384749790664894,
            "warning": "0.00/0.05 代理点 residual 超门，不可用于正式结论或 accepted-only。",
        },
        "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True},
    }
    RECORD.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "这是严格验收推导出的最小后续点；当前未启动，不与 low-005 retry 并发。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "low-005 通过后仍需一个 omega=0.00 侧翼点",
                "why": "0.05 若为 CV 最大值但处于网格左端，不能满足‘主峰被两侧频点包围’；0.00 是关闭该门的最小新增计算。",
            },
            {
                "kind": "table",
                "columns": ["阶段", "条件", "动作"],
                "rows": [
                    ["现在", "low-005 正在运行", "只准备计划，不启动第二个 Julia"],
                    ["low-005 通过", "服务器无重型 Julia", "启动独立 omega=0.00 高预算点"],
                    ["low-005 失败", "residual>1e-5 或 validator 失败", "停止追加，保持 bounded"],
                    ["low-000 通过", "checksum 与 validator 全通过", "重组 accepted-only 并运行 CV--TEBD"],
                ],
                "widths": ["18%", "36%", "46%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["参数", "alpha=0.23, beta=0.5, L=40, q=pi, eta=0.1, omega=0.00"],
                    ["预算", "Ddmrg=320, Dcv=800, nsweeps=20, threads=4"],
                    ["预计时间", "1--3 小时；启动后按实际进度设置一次性读取"],
                    ["门槛", "residual<=1e-5，不降低"],
                    ["范围", "0<=alpha,beta<=1；排除负 alpha 与 Fig.9"],
                ],
            },
            {
                "kind": "note",
                "label": "仅用于排程的成功概率信号",
                "style": "info",
                "text": "用旧失败 residual 点作代理时，九点网格的 CV/TEBD 峰位均为 0.05，峰位差 0，完整窗积分差约 1.84%（门槛 15%）。这些代理点不进入正式证据，只说明补 omega=0.00 值得执行。",
            },
        ],
    }
    report["sections"] = [item for item in report["sections"] if item.get("title") != TITLE]
    report["sections"].insert(1, section)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "recorded", "record": str(RECORD)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
