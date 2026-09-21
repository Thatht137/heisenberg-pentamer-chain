"""把严格 q=pi 终态验收准备和 CV schema 复核写入报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
SUMMARY = ROOT / (
    "results/autoresearch_v5_20260803/round25_qpi_tebd_smoke/"
    "production_analysis_smoke_t25_v2/summary.json"
)
VALIDATIONS = [
    ROOT / "results/research_progress/cv_l40_w020_revalidation_v2_20260803.json",
    ROOT / "results/research_progress/cv_round20_validator_schema_compat_20260803.json",
    ROOT / "results/research_progress/cv_round21_validator_schema_compat_20260803.json",
]
TITLE = "2026-08-03 20:00 严格 q=pi 终态验收链就绪"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    validations = [json.loads(path.read_text(encoding="utf-8")) for path in VALIDATIONS]
    diagnostics = summary["diagnostics"]
    sections = [section for section in report["sections"] if section["title"] != TITLE]
    sections.insert(
        0,
        {
            "title": TITLE,
            "note": "等待 L=40 生产结果期间完成；只验证分析链，不提前提升远端运行结论",
            "blocks": [
                {
                    "kind": "verdict",
                    "status": "good",
                    "label": "终态数据到达后可立即做独立复算与分层验收",
                    "why": "新验收器已从 correlation.csv 独立重算频谱，区分严格 q=pi 收敛、完整动力学准入和 CV 方法覆盖；5/5 本地测试通过。",
                },
                {
                    "kind": "table",
                    "columns": ["验收层", "已实现", "仍需真实 L=40 数据"],
                    "rows": [
                        ["单 run 完整性", "status、manifest、全文件 checksum、正区范围", "coarse/refined 终态"],
                        ["时间步", "主峰差 <=0.05；积分权重差 <=5%", "dt=0.025 与 0.0125"],
                        ["时间窗", "由原始 C_pi(t) 截取 tmax=25/30；主峰漂移 <=0.05", "L=40 短窗非负性"],
                        ["Fourier", "原始相关函数独立梯形复算；相对 L2 <=1e-10", "L=40 复算值"],
                        ["maxdim", "支持独立第二档输入和差异报告", "根据 D=320 实际触顶情况选 D=256 或更高档"],
                        ["CV 方法检查", "检查同实例、同 eta、同归一化和覆盖范围", "峰值定位后决定最小低频补点"],
                    ],
                    "widths": ["20%", "43%", "37%"],
                },
                {
                    "kind": "table",
                    "columns": ["小尺寸窗口诊断", "主峰 omega/J1", "min S(pi,omega)", "判断"],
                    "rows": [
                        ["tmax=20", "0.15", "-1.3043e-3", "负尾，不能作为严格短窗档"],
                        ["tmax=25", "0.15", f"{diagnostics['short_spectrum_min']:.4e}", "非负，选为预注册短窗"],
                        ["tmax=30", "0.15", f"{diagnostics['refined_spectrum_min']:.4e}", "生产全窗"],
                        ["25 对 30", f"漂移={diagnostics['time_window_peak_delta']:.3g}", f"relative L2={diagnostics['short_spectrum_relative_l2_vs_full']:.3%}", "峰位门通过；完整谱差保留为诊断"],
                    ],
                    "widths": ["24%", "24%", "25%", "27%"],
                },
                {
                    "kind": "kv",
                    "pairs": [
                        ["频谱复算", f"coarse relative L2={diagnostics['coarse_fourier_recompute_relative_l2']:.3e}；refined={diagnostics['refined_fourier_recompute_relative_l2']:.3e}"],
                        ["dt/dt2 smoke", f"峰位差={diagnostics['dt_peak_delta']:.3g}；积分权重相对差={diagnostics['dt_weight_relative_delta']:.4%}"],
                        ["状态边界", "小尺寸 q=pi 时间步与窗口为 Agreement；完整动力学仍因第二档 maxdim、q=0、反演和 CV 覆盖不足而 incomplete"],
                        ["范围", "0 <= alpha,beta <= 1；负 alpha 与 Fig. 9 排除"],
                    ],
                },
                {
                    "kind": "verdict",
                    "status": "good" if all(item["status"] == "pass" for item in validations) else "bad",
                    "label": "CV 独立验证器兼容旧、新两类输出",
                    "why": "旧 schema v1 的 omega=0.20、round20 单点和 round21 三点均通过；数值门槛不变，只修正了把 v2 points/ 结构错误强加给 v1 的程序兼容问题。",
                },
                {
                    "kind": "table",
                    "columns": ["L=40 CV omega/J1", "S(pi,omega)", "relative residual", "验收"],
                    "rows": [
                        ["0.20", "0.8094698096", "7.484e-6", "schema v1 复核通过"],
                        ["0.25", "0.5681807187", "6.021e-6", "schema v2 复核通过"],
                        ["0.30", "0.4268870683", "5.578e-6", "schema v2 复核通过"],
                        ["0.35", "0.3680495734", "5.292e-6", "schema v2 复核通过"],
                    ],
                    "widths": ["25%", "25%", "25%", "25%"],
                },
                {
                    "kind": "note",
                    "label": "新分析结论",
                    "style": "info",
                    "text": "四个 CV 点已组装成带源哈希的稀疏 anchor 集。它们在 0.20--0.35 上单调下降，因此当前网格没有包围内部主峰，不能用它关闭峰位或主要积分权重的 CV--TEBD 门。等待 L=40 TEBD 定位主峰后，只在低频侧补最小必要 CV 点；不重复已有频率。",
                },
                {
                    "kind": "code",
                    "title": "可复核证据",
                    "text": "scripts/autoresearch_v5/analyze_qpi_tebd_production.py\nscripts/autoresearch_v5/test_qpi_tebd_production_analysis.py\nscripts/autoresearch_v5/validate_cv_run.py\nscripts/autoresearch_v5/assemble_qpi_cv_anchors.py\nresults/autoresearch_v5_20260803/round25_qpi_tebd_smoke/production_analysis_smoke_t25_v2/{summary.json,spectrum_comparison.csv,checksums.sha256}\nresults/autoresearch_v5_20260803/round27_qpi_cv_anchor_assembly/{manifest.json,spectrum.csv,checksums.sha256}\nresults/research_progress/cv_l40_w020_revalidation_v2_20260803.json\nresults/research_progress/cv_round20_validator_schema_compat_20260803.json\nresults/research_progress/cv_round21_validator_schema_compat_20260803.json",
                },
                {
                    "kind": "note",
                    "label": "远端动作纪律",
                    "style": "pending",
                    "text": "不启动第二个 Julia。round26 coarse/refined 终态后先远端 checksum；下载仍需单独 preview 与明确确认，然后在本地运行本验收器。",
                },
            ],
        },
    )
    report["sections"] = sections
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03 20:00 CST"
    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"section": TITLE, "cv_validations": len(validations)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
