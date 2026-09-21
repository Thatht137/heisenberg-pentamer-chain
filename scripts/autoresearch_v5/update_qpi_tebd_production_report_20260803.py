"""把严格 q=pi 生产数据的回传、验收和真实图写入报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
SUMMARY = ROOT / "results/autoresearch_v5_20260803/round29_qpi_local_handoff/production_crosscheck/summary.json"
RECEIPT = ROOT / "results/research_progress/qpi_tebd_fetch_receipt_20260803_2055.json"
TITLE = "2026-08-03 21:12 严格 q=pi L=40 生产回传与真实谱"


def fmt(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}g}"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    diagnostics = summary["diagnostics"]
    cv = diagnostics["cv"]
    sections = [section for section in report["sections"] if section["title"] != TITLE]
    sections.insert(
        0,
        {
            "title": TITLE,
            "note": "用户确认下载后完成非覆盖式回传、独立哈希验收和 Python-only 真实生产图",
            "blocks": [
                {
                    "kind": "verdict",
                    "status": "warn",
                    "label": "TEBD 单 run 与 dt/tmax 门通过；完整动态结论仍 incomplete",
                    "why": "两个生产 cell 均 accepted，dt/dt2、tmax=25/30、非负性和 Fourier 复算通过；尚无实际触顶的第二档 maxdim，CV 仅覆盖 0.20–0.35。",
                },
                {
                    "kind": "table",
                    "columns": ["项目", "结果", "解释"],
                    "rows": [
                        ["回传完整性", f"{receipt['file_count']} files；{receipt['total_bytes']} bytes；receipt=pass", "非覆盖式原子落位；两个 cell 与 overall hash 一致"],
                        ["参数实例", "alpha=0.23，beta=0.5，L=40，q=pi，eta=0.1，OBC，Sz=0", "负 alpha 与 Fig. 9 排除"],
                        ["dt/dt2", f"峰位差={fmt(diagnostics['dt_peak_delta'])}；权重相对差={diagnostics['dt_weight_relative_delta']:.3e}", "均在预注册 0.05 / 5% 门槛内"],
                        ["tmax=25/30", f"峰位差={fmt(diagnostics['time_window_peak_delta'])}；短窗最小谱={diagnostics['short_spectrum_min']:.3e}", "短窗非负，时间窗门通过"],
                        ["峰位", f"coarse/refined/short 均为 omega={diagnostics['refined_peak_omega']:.2f}", "当前 0.05 频率网格上的离散峰位"],
                    ],
                    "widths": ["20%", "38%", "42%"],
                },
                {
                    "kind": "figures",
                    "items": [
                        {
                            "src": "../../figures/qpi_tebd_production_20260803.png",
                            "caption": "真实 L=40 严格 q=pi 生产谱。a：refined、coarse、tmax=25 的 TEBD 谱与四个 CV anchor；b：频率分辨差值；c：已通过的 dt、积分权重和时间窗门槛占用率。图中 CV 明确标为 sparse anchors，不把未覆盖主峰和主要积分窗的四点升级为方法 Agreement。",
                        }
                    ]
                },
                {
                    "kind": "table",
                    "columns": ["CV/TEBD 状态", "当前证据", "允许的结论"],
                    "rows": [
                        ["cross_method_tag", "NotEvaluable", "不关闭 CV–TEBD 独立方法门"],
                        ["CV omega", ", ".join(f"{omega:g}" for omega in cv["omegas"]), "四点均在低频段，未包围主峰 omega≈0.05"],
                        ["主要积分窗 [0,1.5]", "未覆盖", "不能报告 15% 权重比较"],
                        ["qpi_production_status", "incomplete", "可报告 TEBD 时间步/时间窗稳定性，不能宣称完整动态复现"],
                    ],
                    "widths": ["24%", "34%", "42%"],
                },
                {
                    "kind": "kv",
                    "pairs": [
                        ["独立交接审计", "results/autoresearch_v5_20260803/round29_qpi_local_handoff/local_handoff_audit.json"],
                        ["分析摘要", "results/autoresearch_v5_20260803/round29_qpi_local_handoff/production_crosscheck/summary.json"],
                        ["真实图与 provenance", "figures/qpi_tebd_production_20260803.{svg,pdf,tiff,png,sources.json}"],
                        ["本地权限修复", "仅对回传目录授予当前用户访问权；未改数据内容，checksum 仍为 pass"],
                    ],
                },
                {
                    "kind": "note",
                    "label": "下一步",
                    "style": "pending",
                    "text": "基于真实谱，下一计算为独立的 TEBD maxdim=96、dt=0.0125、tmax=30 单 cell；它尚未上传或启动，需单独 preview 与确认。CV 扩展应覆盖主峰附近并延伸至主要积分窗后再运行。",
                },
            ],
        },
    )
    report["sections"] = sections
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03 21:12 CST"
    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"section": TITLE, "status": summary["status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
