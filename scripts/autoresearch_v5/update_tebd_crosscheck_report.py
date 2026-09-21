#!/usr/bin/env python3
"""把 TEBD pilot 审计和生产交叉检查计划写入长期 HTML 报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results" / "research_progress" / "report.json"
TITLE = "TEBD pilot 审计与交叉检查准备"


def build_section() -> dict[str, object]:
    return {
        "title": TITLE,
        "note": "2026-08-03 · 只含 alpha>=0、beta=0.5；pilot 不作为生产结论",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "现有 TEBD 只能作 pilot，尚未达到正文准入",
                "why": "旧数据仅有 dt=0.05；dt/2、原始反演、非负性和时间窗门槛未全部通过，因此不把 pilot 谱线写成生产 DSF。",
            },
            {
                "kind": "text",
                "text": "L=40、beta=0.5 的旧 pilot 覆盖 alpha=0.14、0.23、0.33 和 tmax=7.5/10/15，但只保存了 dt=0.05。alpha=0.14 的时间窗峰位漂移约 0.9833；其余点也未完成 dt/2 比较。q=0 非弹性守恒量约 1e-17 是通过项，但不足以抵消反演和非负性失败。",
            },
            {
                "kind": "table",
                "columns": ["检查", "pilot 结果", "正文状态"],
                "rows": [
                    ["dt/2", "没有 dt=0.025 原始谱", "待计算"],
                    ["时间窗", "alpha=0.14 峰位漂移 0.9833", "未通过"],
                    ["raw inversion", "相对 RMS 0.54–1.17", "未通过"],
                    ["raw nonnegative", "negative/positive 比 0.64–3.19", "未通过"],
                    ["q=0 守恒", "约 1e-17", "通过单项检查"],
                ],
                "widths": ["24%", "42%", "34%"],
            },
            {
                "kind": "figures",
                "items": [
                    {
                        "src": "positive_tebd_pilot_audit_20260803.png",
                        "caption": "补充审计图，不是生产 DSF。仅含 alpha=0.14、0.23、0.33、beta=0.5、L=40 的 dt=0.05 pilot：a 为 q=pi 峰位随时间窗变化，b 为 raw inversion relative RMS，c 为 raw 负/正权重比，d 为 q=0 非弹性守恒比。q=0 守恒通过，但时间窗、raw inversion 和非负性均未达到生产门槛；派生数据与 SHA-256 见 positive_tebd_pilot_audit_20260803.json。",
                    }
                ],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["推荐生产点", "alpha=0.23, beta=0.5, L=40, dt=0.025, tmax=15, q=81, omega=181"],
                    ["固定设置", "N_units=8、dmrg/TEBD maxdim=320、24 sweeps、8 threads、omega_max=3"],
                    ["远端状态", "round22 L=80 CV anchor 释放后才能启动；当前只完成 run_config/status scaffold；三份脚本已同步且远端语法检查通过"],
                    ["本地进度", "progress.json=waiting_for_anchor；当前没有 TEBD/Fourier 输出"],
                    ["准入门槛", "dt/2 通过；至少 tmax=15/20；峰位漂移<=0.05；主要低频权重差<=15%；谱非负"],
                ],
            },
            {
                "kind": "code",
                "title": "证据与入口",
                "text": "results/autoresearch_v2_20260729/round5_dsf_window_audit_fix1/acceptance.txt\nresults/autoresearch_v2_20260729/round5_dsf_window_audit_fix1/window_summary.csv\nresults/research_progress/positive_tebd_pilot_audit_20260803.json\nresults/research_progress/positive_tebd_pilot_audit_20260803.csv\nfigures/positive_tebd_pilot_audit_20260803.png\nresults/autoresearch_v5_20260802/round23_tebd_crosscheck/cell-alpha023-dt025-t15/run_config.json\nscripts/autoresearch_v5/run_tebd_production.py\nscripts/autoresearch_v5/analyze_tebd_crosscheck.py",
            },
            {
                "kind": "note",
                "label": "范围边界",
                "style": "pending",
                "text": "不计算负 alpha，不扩大二维相图；TEBD 生产 run 只有在服务器重任务释放后启动，旧 pilot 在交叉检查完成前只进入补充审计。",
            },
        ],
    }


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    sections = [section for section in report["sections"] if section["title"] != TITLE]
    insert_at = next(
        (index + 1 for index, section in enumerate(sections) if section["title"].startswith("round22 L=80 CV anchor")),
        len(sections),
    )
    sections.insert(insert_at, build_section())
    report["sections"] = sections
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(REPORT), "section": TITLE}, ensure_ascii=False))


if __name__ == "__main__":
    main()
