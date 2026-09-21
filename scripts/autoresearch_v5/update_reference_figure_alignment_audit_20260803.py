"""追加参考图一一对应核对和当前服务器状态。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
REPORT_DIR = REPORT.parent
TITLE = "2026-08-03 23:14 参考图一一对应核对（Fig. 1--8）"


def main() -> None:
    snapshot = {
        "checked_at": "2026-08-03T23:14:10+08:00",
        "remote_run": "round31_qpi_cv_extension/cell-l40-qpi-low-000-020",
        "status": "running",
        "phase": "julia_linsolve",
        "completed_points": 1,
        "total_points": 5,
        "omega_range": [0.0, 0.20, 0.05],
        "julia_processes": 1,
        "threads": 8,
        "cores": 80,
        "available_memory_gib": 227,
        "first_point": {"omega": 0.0, "residual": 1.324e-5, "D": 200},
        "acceptance_gate": "CV residual <= 1e-5；当前首点仍未通过，整体不验收",
        "scope": {"alpha_min": 0.0, "alpha_max": 1.0, "beta_min": 0.0, "beta_max": 1.0, "negative_alpha_excluded": True, "fig9_excluded": True},
    }
    (REPORT_DIR / "qpi_cv_extension_status_20260803_2314.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "按参考文献的面板角色逐一对齐；图形由 Python/matplotlib 统一生成。只展示 0<=alpha,beta<=1，不包含负 alpha 和 Fig. 9。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "Fig. 1--5 已有可复核对应图，Fig. 6--8 保持部分完成",
                "why": "静态 ED、有限尺寸和机制图已按参考角色绘制；动态图目前只有严格 q=pi 的代表点，完整 beta/alpha 生产扫描仍由 CV 任务提供。",
            },
            {
                "kind": "table",
                "columns": ["参考图", "五聚体对应图/数据", "当前证据等级", "验收边界"],
                "rows": [
                    ["Fig. 1", "链模型、局域多重态；reference_aligned_fig1", "已完成", "单胞 ED 与有效投影；不引入四聚体命名"],
                    ["Fig. 2", "正区能级流、q=pi 谱权；reference_aligned_fig2", "已完成", "alpha∈[0,1]；权重按总自旋分组"],
                    ["Fig. 3", "R 热图、切片和尺寸差；reference_aligned_fig3", "诊断完成", "只表示有限尺寸趋势，不命名相界"],
                    ["Fig. 4", "五切口纠缠谱；reference_aligned_fig4", "已完成（有限尺寸）", "L=80、beta=0.5；不以简并单独定义相"],
                    ["Fig. 5", "有效链与 q=pi 选择定则；pentamer_momentum_filter", "已完成", "单胞选择定则和谱权支持"],
                    ["Fig. 6", "严格 q=pi 动态谱；qpi_tebd_maxdim96_production", "部分完成", "代表点收敛通过；非全 beta 扫描"],
                    ["Fig. 7", "alpha=0.23、beta=0.5 CV/TEBD 交叉图", "等待 CV", "主峰、积分权重需独立交叉验收"],
                    ["Fig. 8", "有效连续谱与 CV 叠加；cv_continuum_overlay", "受限诊断", "仅在生产 CV 覆盖后讨论分支，不提前命名"],
                ],
                "widths": ["12%", "33%", "22%", "33%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["静态图脚本", "scripts/autoresearch_v5/plot_reference_aligned_figures_20260803.py；plot_reference_aligned_fig3_20260803.py；plot_reference_aligned_fig4_pentamer_positive_20260803.py"],
                    ["动态图资产", "figures/qpi_tebd_maxdim96_production_20260803.*；figures/cv_continuum_overlay_20260803.*"],
                    ["导出标准", "SVG/PDF 可编辑文字；PNG 450 dpi；TIFF 600 dpi；每张图保留 sources.json（如适用）"],
                    ["服务器状态", "低频 q=pi CV：1/5 点；julia_linsolve；Julia=1、threads=8；不启动第二个 Julia"],
                    ["当前首点", "omega=0.00，residual=1.324e-5，高于 1e-5 门槛；保留为未验收证据"],
                ],
            },
            {
                "kind": "note",
                "label": "下一步",
                "style": "pending",
                "text": "等待当前 cell 自然终止；终态后按回传、远端/本地 checksum、validate_cv_run.py、anchor 组装和 CV/TEBD 交叉顺序更新 Fig. 6--8。若 residual 仍超门槛，保留失败证据并新建独立重算目录，不降低验收标准。",
            },
        ],
    }
    report["sections"] = [item for item in report["sections"] if item.get("title") != TITLE]
    report["sections"].insert(0, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03 · FIGURE ALIGNMENT AUDIT"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"section": TITLE, "snapshot": snapshot["status"], "points": "1/5"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
