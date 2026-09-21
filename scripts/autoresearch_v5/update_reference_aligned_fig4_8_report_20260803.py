"""把正区 Fig. 4--8 对应图追加到 HTML 报告。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "results/research_progress"
REPORT = REPORT_DIR / "report.json"
TITLE = "2026-08-03 参考图一一对应版 Fig. 4--8"
FIGURES = [
    "reference_aligned_fig4_pentamer_positive_20260803.png",
    "pentamer_model_effective_chain_20260731.png",
    "pentamer_momentum_filter_20260731.png",
    "qpi_tebd_maxdim96_production_20260803.png",
]


def main() -> None:
    for name in FIGURES:
        source = ROOT / "figures" / name
        if not source.is_file():
            raise SystemExit(f"缺少图像: {source}")
        shutil.copy2(source, REPORT_DIR / name)
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "全部使用 Python/matplotlib；图 4 只保留正 alpha 的纠缠谱，图 5--8 沿用已验收机制和严格 q=pi 动力学证据。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good",
                "label": "Fig. 4--8 的正区对应版已补齐",
                "why": "保留参考文献的纠缠谱、模型机制、动量过滤和动态谱面板角色；不复用负 alpha，也不把未覆盖 CV 主峰的锚点升级为完整交叉验证。",
            },
            {
                "kind": "figures",
                "items": [
                    {
                        "src": FIGURES[0],
                        "caption": "对应参考 Fig. 4。L=80、beta=0.5 的五个不等价切口纠缠谱，展示 alpha=0.14 和 0.33 两个正区点；这里只作有限尺寸谱结构对应，不单独定义相界。",
                    },
                    {
                        "src": FIGURES[1],
                        "caption": "对应参考 Fig. 1 的机制扩展版。1×5 微观链、低能投影系数和全正区 J_eff/beta>0 证据，支持有效 S=1/2 反铁磁链。",
                    },
                    {
                        "src": FIGURES[2],
                        "caption": "对应参考 Fig. 5。严格 q=pi 的反射选择定则、alpha=0.23 离散通道权和正区四重态权重占比；最低奇宇称双重态为暗通道。",
                    },
                    {
                        "src": FIGURES[3],
                        "caption": "对应参考 Fig. 6--8 的动态谱证据版。L=40、alpha=0.23、beta=0.5、q=pi 的 TEBD 收敛曲线、差值和门槛占用率；maxdim=96 已与 320 基准通过对照。",
                    },
                ],
            },
            {
                "kind": "table",
                "columns": ["参考图", "五聚体对应内容", "证据状态"],
                "rows": [
                    ["Fig. 4", "五切口纠缠谱，alpha=0.14/0.33", "正区有限尺寸数据；不宣称相界"],
                    ["Fig. 5", "q=pi 选择定则和局域激发通道", "孤立单胞 ED 验收通过"],
                    ["Fig. 6--8", "严格 q=pi TEBD 动态谱", "dt、tmax、maxdim 和非负性通过；CV 主峰交叉仍未评估"],
                ],
                "widths": ["18%", "42%", "40%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["Fig. 4 脚本", "scripts/autoresearch_v5/plot_reference_aligned_fig4_pentamer_positive_20260803.py"],
                    ["Fig. 4 源数据", "data/entanglement_spectrum/spectrum_a0.14_b0.50_L080.csv；spectrum_a0.33_b0.50_L080.csv"],
                    ["动态谱分析", "results/autoresearch_v5_20260803/round30_qpi_maxdim96_analysis/summary.json"],
                    ["导出", "SVG、PDF、450 dpi PNG、600 dpi TIFF；SVG/PDF 文字可编辑"],
                ],
            },
        ],
    }
    report["sections"] = [item for item in report["sections"] if item["title"] != TITLE]
    report["sections"].insert(1, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03 · REFERENCE-ALIGNED FIGURES 1-8"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"section": TITLE, "figures": FIGURES}, ensure_ascii=False))


if __name__ == "__main__":
    main()
