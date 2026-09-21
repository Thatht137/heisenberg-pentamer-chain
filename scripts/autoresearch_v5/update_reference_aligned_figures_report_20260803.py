"""把参考图一一对应的五聚体图版写入 HTML 报告。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "results/research_progress"
REPORT = REPORT_DIR / "report.json"
FIGURES = ROOT / "figures"
TITLE = "2026-08-03 参考图一一对应版 Fig. 1--3"
FIG1 = "reference_aligned_fig1_pentamer_20260803.png"
FIG2 = "reference_aligned_fig2_pentamer_positive_20260803.png"
FIG3 = "reference_aligned_fig3_pentamer_positive_20260803.png"


def main() -> None:
    for name in (FIG1, FIG2, FIG3):
        shutil.copy2(FIGURES / name, REPORT_DIR / name)
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "Python/matplotlib；复用已有 ED 多重态数据；只含 0<=alpha<=1。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good",
                "label": "Fig. 1--2 的五聚体版式已对齐",
                "why": "保留参考文献的链模型、局域能级、能级流和动量过滤证据角色；不移植四聚体相名、负 alpha 或 Fig. 9。",
            },
            {
                "kind": "figures",
                "items": [
                    {
                        "src": FIG1,
                        "caption": "对应参考 Fig. 1。a：1×5 链、J1/J2/J3 和低能投影；b：alpha=0.23 的五聚体局域多重态能级，颜色表示总自旋，圆点大小表示 q=pi 局域谱权。",
                    },
                    {
                        "src": FIG2,
                        "caption": "对应参考 Fig. 2。a：正 alpha 区五个双重态、四个四重态和一个六重态的局域能隙流；b：q=pi 谱权按总自旋分组，标出生产主点 alpha=0.23。",
                    },
                    {
                        "src": FIG3,
                        "caption": "对应参考 Fig. 3 的正区诊断版。a：L=80 的 R 热图；b/c：beta 与 alpha 切片；d：L=60-L=40 尺寸差。该图只检查有限尺寸趋势，不绘制未经验收的相界。",
                    },
                ],
            },
            {
                "kind": "table",
                "columns": ["参考图角色", "五聚体对应实现", "数据状态"],
                "rows": [
                    ["Fig. 1a 链模型", "1×5 单胞 + J1/J2/J3 + 有效 S=1/2 链", "已有投影 ED；无新增计算"],
                    ["Fig. 1b 单胞能级", "alpha=0.23 局域多重态能级", "multiplet_scan 已验收"],
                    ["Fig. 2a 能级流", "0<=alpha<=1 正区局域能隙", "五双重态、四四重态、一六重态"],
                    ["Fig. 2b 解耦/通道", "q=pi 谱权按 S 分组", "最低奇宇称双重态和 S=5/2 接近暗通道"],
                    ["Fig. 3 热图/切片", "R(L=80) 与尺寸差诊断", "正区 5×7×3 网格；不宣称相界"],
                ],
                "widths": ["24%", "42%", "34%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["绘图脚本", "scripts/autoresearch_v5/plot_reference_aligned_figures_20260803.py"],
                    ["源数据", "results/autoresearch_v4_20260730/round2_local_spectral_channels_v4/multiplet_scan.csv"],
                    ["相图源数据", "results/autoresearch_v5_20260802/round19_phase_diagram_positive_mesh/phase-diagram/observations_merged.json"],
                    ["导出", "SVG、PDF、450 dpi PNG、600 dpi TIFF"],
                    ["图像 QA", "已检查面板标签、坐标、无文字遮挡；SVG/PDF 使用可编辑文字"],
                ],
            },
            {
                "kind": "note",
                "label": "边界",
                "style": "pending",
                "text": "Fig. 3 已有有限尺寸诊断版；Fig. 6--8 的 DSF 多面板将继续沿用参考图的面板角色，但只有具备原始数据和收敛证据的正区结果才进入正式版；当前不把侦察热图冒充生产谱。",
            },
        ],
    }
    report["sections"] = [item for item in report["sections"] if item["title"] != TITLE]
    report["sections"].insert(1, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03 · REFERENCE-ALIGNED FIGURES"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"section": TITLE, "figures": [FIG1, FIG2, FIG3]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
