"""记录严格 q=pi 的定量门槛与绘图合同。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
TITLE = "2026-08-03 20:41 严格 q=pi 定量门槛与第二档决策"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    sections = [section for section in report["sections"] if section["title"] != TITLE]
    sections.insert(
        0,
        {
            "title": TITLE,
            "note": "不下载、不上传、不启动 Julia；先完成可离线推进的验收和绘图工具链",
            "blocks": [
                {
                    "kind": "verdict",
                    "status": "good",
                    "label": "严格 q=pi 的误差预算现已可执行",
                    "why": "分析器不再把仅有配置差异的 maxdim 或不完整 CV 网格当作通过证据；18/18 单元与端到端测试通过。",
                },
                {
                    "kind": "table",
                    "columns": ["误差轴", "覆盖条件", "验收门槛", "未满足时"],
                    "rows": [
                        ["时间步", "dt 与 dt/2；同 tmax", "峰位差 <=0.05；积分权重差 <=5%", "fail"],
                        ["时间窗", "tmax=25 与 30", "峰位差 <=0.05；短窗 raw 谱非负", "fail"],
                        ["键维数", "配置不同、演化设置相同且较低上限实际触及", "峰位差 <=0.05；积分权重差 <=5%", "缺失为 incomplete；超门为 fail"],
                        ["CV/TEBD", "同实例；CV 包围内部主峰并覆盖 omega=[0,1.5]", "峰位差 <=0.10；积分权重差 <=15%", "覆盖不足为 NotEvaluable；超门为 Disagreement"],
                    ],
                    "widths": ["15%", "35%", "28%", "22%"],
                },
                {
                    "kind": "kv",
                    "pairs": [
                        ["基准实际维数", "coarse/refined 的 tebd_actual_maxdim 均为 117"],
                        ["D=160 判定", "不会触及截断上限，不能作为独立 maxdim 证据"],
                        ["下一候选", "D=96；低于实际 117，可真实激活截断误差轴"],
                        ["输出升级", "spectrum_comparison.csv 在提供第二档时写入 maxdim_<D> 谱列"],
                        ["跨方法标签", "完整覆盖后直接输出 Agreement 或 Disagreement，不再停在 PendingBudgetedComparison"],
                    ],
                },
                {
                    "kind": "table",
                    "columns": ["绘图 QA", "结果"],
                    "rows": [
                        ["后端", "仅 Python matplotlib；未调用 R"],
                        ["版式", "quantitative grid；183 x 105 mm；主谱为 hero panel"],
                        ["动态内容", "自动加入 maxdim 谱、频率分辨差值以及 maxdim/CV 门槛占用率"],
                        ["导出", "SVG、PDF、TIFF 600 dpi、PNG 300 dpi、sources JSON 烟雾测试通过"],
                        ["可编辑性与尺寸", "SVG 文本未轮廓化；PNG=2161 x 1240 px"],
                    ],
                    "widths": ["28%", "72%"],
                },
                {
                    "kind": "code",
                    "title": "已验证入口",
                    "text": "scripts/autoresearch_v5/analyze_qpi_tebd_production.py\nscripts/autoresearch_v5/plot_qpi_tebd_production.py\nscripts/autoresearch_v5/run_qpi_tebd_local_handoff.py\nscripts/autoresearch_v5/test_qpi_tebd_production_analysis.py\nscripts/autoresearch_v5/test_qpi_tebd_plot.py",
                },
                {
                    "kind": "note",
                    "label": "当前证据边界",
                    "style": "pending",
                    "text": "上述结论证明验收工具链可执行，不等于生产谱已在本地完成分析。远端 26 文件仍等待单独的“确认下载”；D=96 是下一计算候选，提交前还需独立 preview 与确认。",
                },
            ],
        },
    )
    report["sections"] = sections
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03 20:41 CST"
    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"section": TITLE, "tests": "18/18"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
