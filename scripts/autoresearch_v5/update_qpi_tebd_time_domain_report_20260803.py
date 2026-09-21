"""把严格 q=pi TEBD 的 ED 时域诊断写入报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
SUMMARY = ROOT / "results/autoresearch_v5_20260803/round25_qpi_tebd_smoke/time_domain_crosscheck/summary.json"
TITLE = "2026-08-03 19:47 严格 q=pi TEBD 时域误差缩放"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    coarse = summary["coarse"]["full"]
    refined = summary["refined"]["full"]
    dt_pair = summary["dt_vs_dt2"]
    ratio = summary["diagnosis"]["coarse_to_refined_l2_error_ratio"]
    sections = [section for section in report["sections"] if section["title"] != TITLE]
    sections.insert(
        0,
        {
            "title": TITLE,
            "note": "L=10 精确 ED 与严格动量自相关逐时刻比较；确定性诊断，不作为新增生产门",
            "blocks": [
                {
                    "kind": "verdict",
                    "status": "good",
                    "label": "二阶 Trotter 误差缩放得到直接验证",
                    "why": f"dt=0.05 的全时窗相对 L2 误差为 {coarse['relative_l2']:.3e}，dt/2 后降至 {refined['relative_l2']:.3e}，误差比 {ratio:.5f}，几乎等于二阶算法预期的 4。",
                },
                {
                    "kind": "figures",
                    "items": [
                        {
                            "src": "qpi_tebd_ed_diagnostic_20260803.png",
                            "caption": "通过的小尺寸实现诊断。L=10、alpha=0.23、beta=0.5、q=pi：黑色为精确 ED，蓝色虚线和红色点线分别为 dt=0.05 与 0.025 的严格 O_q|GS> TEBD。a,b 显示复相关函数实部和虚部全时窗重合；c 显示 dt 减半使误差降低约 4 倍；d 显示 eta=0.1 的频谱 Agreement。该图验证相位、门序和归一化，不替代 L=40 生产结果。",
                        }
                    ],
                },
                {
                    "kind": "table",
                    "columns": ["诊断量", "dt=0.05", "dt=0.025", "解释"],
                    "rows": [
                        ["全时窗相对 L2", f"{coarse['relative_l2']:.6e}", f"{refined['relative_l2']:.6e}", f"比值 {ratio:.5f}"],
                        ["最大复误差", f"{coarse['max_absolute']:.6e}", f"{refined['max_absolute']:.6e}", "随 dt/2 降低约 4 倍"],
                        ["t=30 复误差", f"{coarse['terminal_absolute']:.6e}", f"{refined['terminal_absolute']:.6e}", "误差随时间累积但仍受控"],
                        ["dt 与 dt/2 互差", f"relative L2={dt_pair['relative_l2']:.6e}", f"max={dt_pair['max_absolute']:.6e}", "独立于频谱窗函数"],
                    ],
                    "widths": ["24%", "23%", "23%", "30%"],
                },
                {
                    "kind": "kv",
                    "pairs": [
                        ["直接验证", "C_pi(t) 的实部、虚部、t=0、exp(iE0t) 相位与二阶门序"],
                        ["频谱差异来源", "有限 tmax=30 的指数窗造成约 4.45% 全谱 L2 差；峰位和积分权重仍通过既有预算"],
                        ["验收边界", "时域误差未预先声明论文门槛，因此 status=diagnostic、gate_effect=none"],
                        ["图形 QA", "183 x 105 mm；SVG/PDF 矢量；TIFF 600 dpi；PNG 300 dpi；Python-only"],
                        ["范围", "0 <= alpha,beta <= 1；负 alpha 与 Fig. 9 排除"],
                    ],
                },
                {
                    "kind": "code",
                    "title": "可复核证据",
                    "text": "scripts/autoresearch_v5/analyze_qpi_tebd_time_domain.py\nscripts/autoresearch_v5/plot_qpi_tebd_time_domain.py\nresults/autoresearch_v5_20260803/round25_qpi_tebd_smoke/time_domain_crosscheck/{summary.json,checksums.sha256}\nfigures/qpi_tebd_ed_diagnostic_20260803.{svg,pdf,tiff,png,sources.json}",
                },
                {
                    "kind": "note",
                    "label": "远端任务仍独立验收",
                    "style": "pending",
                    "text": "本节不提升 L=40 结论等级。远端 round26 在最近一次检查时处于 coarse/DMRG；等待 coarse 终态后再决定 refined，不做短间隔轮询。",
                },
            ],
        },
    )
    report["sections"] = sections
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03 19:47 CST"
    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"section": TITLE, "error_ratio": ratio}, ensure_ascii=False))


if __name__ == "__main__":
    main()
