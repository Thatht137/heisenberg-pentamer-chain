#!/usr/bin/env python3
"""把服务器终态和 ETA 追加到研究报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
ROUND38 = ROOT / "results/research_progress/round38_mesh0051_acceptance_20260804.json"
ROUND31 = ROOT / "results/research_progress/round31_high150_status_20260804.json"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    r38 = json.loads(ROUND38.read_text(encoding="utf-8"))
    r31 = json.loads(ROUND31.read_text(encoding="utf-8"))
    sections = [s for s in report["sections"] if s.get("title") not in {
        "2026-08-04 round38 mesh-cell-0051 高预算复核验收",
        "2026-08-04 round31 high-150 运行状态与 ETA",
    }]
    section38 = {
        "title": "2026-08-04 round38 mesh-cell-0051 高预算复核验收",
        "note": "正区有限尺寸控制点；不含负 alpha，不涉及 Fig.9。",
        "blocks": [
            {"kind": "verdict", "status": "warn", "label": "运行质量通过，双初态稳定性目标未通过", "why": "两子运行均 success/accepted，方差和截断误差通过；半差 1.791e-3 > 1e-3。"},
            {"kind": "table", "columns": ["量", "值", "门槛", "结果"], "rows": [
                ["variance/site 最大", "6.8398e-10", "<=1e-8", "通过"],
                ["final truncation 最大", "9.9995e-13", "<=1e-9", "通过"],
                ["双初态半差", "1.79096e-3", "<=1e-3", "未通过"],
                ["相界结论", "不命名", "必须有尺寸序列 crossing", "保持约束性"],
            ], "numeric": [False, True, True, False]},
            {"kind": "kv", "pairs": [["参数", "alpha=0.125, beta=1.0, L=80, maxdim=1600, nsweeps=80"], ["结构因子比", "0.27759795 ± 0.00179096"], ["证据", "results/research_progress/round38_mesh0051_acceptance_20260804.json"], ["远端校验", "顶层及两个子目录 checksum failures=0"]]},
            {"kind": "note", "label": "解释边界", "style": "pending", "text": "本复核只降低该点的数值不确定性，不扩大相图网格，也不把未见 crossing 升级为热力学单相证明。"},
        ],
    }
    section31 = {
        "title": "2026-08-04 round31 high-150 运行状态与 ETA",
        "note": "一次只读快照；不抓取运行中的目录。",
        "blocks": [
            {"kind": "verdict", "status": "warn", "label": "round31 3/4，high-150 仍在运行", "why": "high-100 已通过独立 validator；high-150 的 Julia linsolve 仍有持续 CPU，预计还需 8–12 小时，置信度低。"},
            {"kind": "table", "columns": ["cell", "状态", "证据", "动作"], "rows": [
                ["low 0.00–0.20", "success / rejected", "residual 超 1e-5", "排除，不降门槛"],
                ["high 0.55", "success / accepted", "已回传", "accepted-only"],
                ["high 1.00", "success / accepted", "residual 1.959e-6", "已回传并验证"],
                ["high 1.50", "running", "PID 324653；无 manifest", "等待，不并行"],
            ], "widths": ["22%", "24%", "30%", "24%"]},
            {"kind": "kv", "pairs": [["资源", "80 cores；available memory 225 GiB；load 21.32"], ["ETA", "8–12 小时（低置信）"], ["状态证据", "results/research_progress/round31_high150_status_20260804.json"], ["下一交接", "终态 manifest -> remote checksum -> non-clobber fetch -> validator"]]},
            {"kind": "note", "label": "并行策略", "style": "info", "text": "high-150 运行期间继续做本机 accepted-only 汇总、图件和报告审计；不启动第二个 Julia。"},
        ],
    }
    report["sections"] = [section38, section31] + sections
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · ROUND31 3/4 · ROUND38 ACCEPTED WITH WARN"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "updated", "sections": 2}, ensure_ascii=False))


if __name__ == "__main__":
    main()
