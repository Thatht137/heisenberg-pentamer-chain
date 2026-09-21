#!/usr/bin/env python3
"""登记 L=80 correction-vector anchor 的状态。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results" / "research_progress" / "report.json"
PREFIX = "round22 L=80 CV anchor"


def make_section(status: str, detail: str, why: str, note: str) -> dict[str, object]:
    title = f"{PREFIX}（{'已通过' if status == 'good' else '运行中'}）"
    return {
        "title": title,
        "note": f"{note} · alpha=0.23、beta=0.5、L=80、q=pi、omega=0.25",
        "blocks": [
            {"kind": "verdict", "status": status, "label": f"{PREFIX}：{'已通过' if status == 'good' else '运行中'}", "why": why},
            {
                "kind": "table",
                "columns": ["项目", "设置", "状态"],
                "rows": [
                    ["系统", "N_units=16、L=80、OBC、Sz=0", "单频率 anchor"],
                    ["CV", "q=pi、eta=0.1、omega=0.25", "可恢复 correction-vector DMRG"],
                    ["数值门槛", "variance/L<=1e-8、CV residual<=1e-5", "通过后才扩展频率"],
                    ["资源", "8 threads、nice=10、dmrg_maxdim=400、cv_maxdim=800", detail],
                ],
                "widths": ["20%", "38%", "42%"],
            },
            {
                "kind": "table",
                "columns": ["运行时诊断", "观测", "判断"],
                "rows": [
                    ["Julia 进程", "State=RNl、wchan=0、主线程约96.9% CPU、57 threads", "正在计算，不是锁等待"],
                    ["资源与 IO", "总 CPU 约1626%、RSS约5.2 GiB、stderr=0", "内存计算，无错误阻塞"],
                    ["代码 provenance", "远端 Julia/Python SHA-256 与 run_config 一致", "不是脚本版本错配"],
                    ["文件进度", "单个 linsolve 完成前不写 checkpoint；points/仍为空", "没有中间进度是程序设计，不等于卡死"],
                    ["时间估计", "截至09:53已运行约13.0 h；先验 L=80 单点估计11.84 h", "可能还需0–8 h；保守上界12 h，置信度低到中"],
                ],
                "widths": ["20%", "47%", "33%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["远端 run", "results/autoresearch_v5_20260802/round22_cv_l80_anchor/cell-0003-L80-qpi-w025"],
                    ["PID", "Python 3745209；Julia 3745217"],
                    ["下一步", "完成后回传、校验 checksum、检查方差/截断/残差；通过才决定 L=80 频率窗口"],
                ],
            },
            {
                "kind": "code",
                "title": "回传后验收入口",
                "text": "results/research_progress/l80_anchor_diagnostic_20260803_0953.json\nscripts/autoresearch_v5/validate_cv_run.py\n通过后才调用 scripts/autoresearch_v5/seed_cv_dsf_extension.py",
            },
            {"kind": "note", "label": "范围边界", "style": "pending", "text": "只含 alpha>=0、beta>=0；不做负 alpha，不扩大二维相图；本点不是完整 L=80 频率谱。"},
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", choices=["running", "good"], required=True)
    parser.add_argument("--detail", required=True)
    parser.add_argument("--why", required=True)
    parser.add_argument("--note", default="2026-08-03")
    args = parser.parse_args()
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    sections = [item for item in report["sections"] if not item["title"].startswith(PREFIX)]
    index = next((i for i, item in enumerate(sections) if item["title"].startswith("round21 CV")), len(sections)) + 1
    sections.insert(index, make_section(args.status, args.detail, args.why, args.note))
    report["sections"] = sections
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(REPORT), "status": args.status}, ensure_ascii=False))


if __name__ == "__main__":
    main()
