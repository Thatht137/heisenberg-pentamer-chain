#!/usr/bin/env python3
"""登记 round41 residual 修复重跑的启动事实。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results" / "research_progress" / "report.json"
RECORD = ROOT / "results" / "research_progress" / "round41_qpi_cv_low005_retry_submission_20260805.json"
TITLE = "2026-08-05 round41 q=pi 低频 residual 修复重跑"


def main() -> None:
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    remote = record["remote"]
    params = record["parameters"]
    verification = record["post_launch_verification"]
    section = {
        "title": TITLE,
        "note": "独立新目录启动记录；不覆盖 round41 原失败结果，不降低 residual 门槛，不扩展低频网格。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "retry 正在运行，尚未进入 accepted-only",
                "why": "high-150 已自然终态通过；修复版只对 omega=0.05 单点追加 linsolve 预算，必须自然终态、checksum 和 validator 全通过后才可使用。",
            },
            {
                "kind": "table",
                "columns": ["项目", "事实", "当前处理"],
                "rows": [
                    ["参数", f"alpha={params['alpha']}, beta={params['beta']}, L={params['L']}, q=pi, eta={params['eta']}, omega={params['omega_min']}", "正区范围"],
                    ["资源", f"Python PID {remote['python_pid']}；Julia PID {remote['julia_pid']}；4 threads；nice=15", "单 Julia"],
                    ["启动核验", f"{verification['phase']}；{verification['completed_points']}/{verification['total_points']} 点；status/progress 已生成", "运行中，暂不轮询"],
                    ["预计时间", "30–60 分钟", "到 ETA 只做一次性只读检查"],
                    ["旧结果", "round41 原 residual=1.17068e-5 的目录保留", "隔离，不覆盖、不重试旧目录"],
                    ["high-150", "omega=1.50；residual=5.540316e-6；acceptance=pass", "已完成终态交接前置"],
                ],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["远端目录", f"{remote['run_root']}/{Path(remote['run_dir']).name}"],
                    ["代码备份", record["preflight"]["code_backup"]],
                    ["验收顺序", "natural termination → remote checksum → 非覆盖回传 → local checksum → validate_cv_run.py → accepted-only → CV–TEBD → HTML"],
                    ["范围", "0 <= alpha,beta <= 1；排除负 alpha 与 Fig.9"],
                ],
            },
            {
                "kind": "note",
                "label": "暂停条件",
                "style": "pending",
                "text": "若启动前发现已有 Julia/runner，launcher 会停止；若 retry residual 仍超过 1e-5，结果继续隔离，不自动扩展到 0–0.20。",
            },
        ],
    }
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    report["sections"] = [item for item in report["sections"] if item.get("title") != TITLE]
    report["sections"].insert(0, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-05 · HIGH150 PASS · LOW005 RETRY RUNNING"
    report["lede"] = "1×5 Heisenberg 五聚体链复现进度。范围固定为 0≤alpha,beta≤1，排除负 alpha 与参考 Fig.9；high-150 已通过，omega=0.05 修复重跑正在独立目录运行。"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "recorded", "title": TITLE}, ensure_ascii=False))


if __name__ == "__main__":
    main()
