#!/usr/bin/env python3
"""记录 low-005 失败终态并冻结动态交付。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results/research_progress"
REPORT = RUN / "report.json"
RETRY = RUN / "round41_qpi_cv_low005_retry_submission_20260805.json"
PLAN = RUN / "round42_qpi_cv_low000_conditional_plan_20260805.json"
VALIDATOR = RUN / "round41_low005_retry_validator_20260805.json"
FREEZE = RUN / "dynamic_gate_freeze_20260805.json"
TITLE = "2026-08-05 low-005 终态失败与 bounded 动态交付冻结"


def main() -> None:
    validator = json.loads(VALIDATOR.read_text(encoding="utf-8"))
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    if validator.get("status") != "fail" or validator.get("checks", {}).get("cv_residual") is not False:
        raise SystemExit("validator 不是预期 residual 失败")

    retry = json.loads(RETRY.read_text(encoding="utf-8"))
    retry["status"] = "failed_acceptance"
    retry["terminal"] = {
        "finished_at": "2026-08-05T21:28:11+08:00",
        "returncode": 0,
        "accepted": False,
        "elapsed_seconds": 4715.091,
        "max_cv_residual": 1.1767005759300015e-5,
        "threshold": 1e-5,
        "remote_checksums": "pass",
        "local_checksums": "pass",
        "validator": "fail",
    }
    RETRY.write_text(json.dumps(retry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    plan["status"] = "cancelled_trigger_not_met"
    plan["cancellation"] = {
        "reason": "low-005 residual 1.1767005759300015e-5 > 1e-5",
        "round42_started": False,
        "server_write_performed": False,
    }
    PLAN.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "程序正常退出不等于数值验收通过；本节只使用 validator、checksum 和 accepted-only 分析。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "bad",
                "label": "low-005 residual 再次超过严格门槛",
                "why": "最终 residual=1.17670e-5，高于 1e-5；returncode=0、stderr=0，但 accepted=false。",
            },
            {
                "kind": "verdict",
                "status": "warn",
                "label": "动态结果冻结为 bounded，而不是继续消耗计算",
                "why": "七点 accepted CV 与 TEBD 最大差 6.40%、共享窗积分差 1.53%，但主峰和左端覆盖未通过。",
            },
            {
                "kind": "table",
                "columns": ["项目", "结果", "处理"],
                "rows": [
                    ["程序终态", "success / returncode=0", "程序无崩溃"],
                    ["远端与本地 checksum", "pass", "失败证据完整"],
                    ["DMRG 方差/截断误差", "pass", "不是基态质量问题"],
                    ["CV residual", "1.17670e-5 > 1e-5", "拒绝进入 accepted-only"],
                    ["round42 omega=0.00", "未启动", "触发条件未满足，按止损规则取消"],
                    ["Fig.6/7/8", "exploratory / pilot / bounded", "不升级 production"],
                ],
                "widths": ["27%", "31%", "42%"],
            },
            {
                "kind": "figures",
                "items": [
                    {
                        "src": "paper_fig8_bounded_cv_tebd_20260805.png",
                        "caption": "Bounded Fig.8。a：L=40、alpha=0.23、beta=0.5、q=pi、eta=0.1 的 TEBD 谱与七个 accepted CV 点；空心叉号为 residual 超门的 omega=0.05 点，只作失败审计。绿色区域为 leading-order 有效链参考窗。b：七个共享频点的相对差，最大 6.40%，均低于 15% 预算；低频覆盖缺失使总体仍为 NotEvaluable。",
                    }
                ],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["冻结决定", "results/research_progress/dynamic_gate_freeze_20260805.json"],
                    ["validator", "results/research_progress/round41_low005_retry_validator_20260805.json"],
                    ["图件 sidecar", "figures/paper_fig8_bounded_cv_tebd_20260805.sources.json"],
                    ["下一步", "停止重型动态计算，完成 bounded 图注、交付审计和 HTML 审阅稿"],
                ],
            },
        ],
    }
    report["sections"] = [item for item in report["sections"] if item.get("title") != TITLE]
    report["sections"].insert(0, section)
    report["eyebrow"] = "RESEARCH LOG · DYNAMIC GATE FROZEN BOUNDED · LOW005 REJECTED"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": freeze["status"], "round42": "cancelled"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
