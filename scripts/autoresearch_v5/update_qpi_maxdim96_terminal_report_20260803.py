"""把 maxdim=96 终态验收和真实谱写入 HTML 报告。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "results/research_progress"
REPORT = REPORT_DIR / "report.json"
SUMMARY = ROOT / "results/autoresearch_v5_20260803/round30_qpi_maxdim96_analysis/summary.json"
RECEIPT = REPORT_DIR / "qpi_tebd_maxdim96_fetch_receipt_20260803.json"
FIGURE = ROOT / "figures/qpi_tebd_maxdim96_production_20260803.png"
FIGURE_NAME = FIGURE.name
TITLE = "2026-08-03 maxdim=96 终态验收与参考图动态谱"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    diagnostics = summary["diagnostics"]
    maxdim = diagnostics["maxdim"]
    shutil.copy2(FIGURE, REPORT_DIR / FIGURE_NAME)
    section = {
        "title": TITLE,
        "note": "maxdim=96 已完成远端计算、非覆盖式下载、独立 checksum 和 Python/matplotlib 图像 QA。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good",
                "label": "严格 q=pi 生产收敛通过",
                "why": "maxdim=96 实际触顶，和 maxdim=320 基准的峰位差为 0、积分权重相对差为 1.66e-7；dt、tmax 和非负性门也全部通过。",
            },
            {
                "kind": "table",
                "columns": ["项目", "结果", "验收解释"],
                "rows": [
                    ["终态", "success；2400/2400 步；890.2 s", "远端单 Julia 正常结束，manifest/status/checksums 全部通过"],
                    ["实例", "alpha=0.23，beta=0.5，L=40，q=pi", "OBC、Sz=0、eta=0.1；仅正区，排除负 alpha 和 Fig. 9"],
                    ["maxdim 对照", "96 vs 320：峰位差 0；权重差 1.66e-7", "预注册门槛为 0.05 和 5%，两项均通过"],
                    ["dt/tmax", "峰位差 0；dt 权重差 1.23e-4", "dt=0.025/0.0125 与 tmax=25/30 稳定"],
                    ["CV 交叉方法", "NotEvaluable", "已有 CV 频点 0.20–0.35，仍未包围 omega≈0.05 主峰和 [0,1.5] 积分窗"],
                ],
                "widths": ["22%", "34%", "44%"],
            },
            {
                "kind": "figures",
                "items": [
                    {
                        "src": FIGURE_NAME,
                        "caption": "对应参考文献 Fig. 6–8 的动态谱证据版。a：严格 q=pi 的 refined/coarse/tmax 对照、maxdim=96 曲线和 CV 稀疏锚点；b：频率分辨差值；c：各收敛门槛占用率。maxdim=96 与 320 几乎重合，CV 点仍明确标为 sparse anchors。",
                    }
                ],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["下载 receipt", "results/research_progress/qpi_tebd_maxdim96_fetch_receipt_20260803.json"],
                    ["分析摘要", "results/autoresearch_v5_20260803/round30_qpi_maxdim96_analysis/summary.json"],
                    ["图版 provenance", "figures/qpi_tebd_maxdim96_production_20260803.sources.json"],
                    ["导出", "SVG、PDF、300 dpi PNG、600 dpi TIFF"],
                ],
            },
            {
                "kind": "note",
                "label": "结论边界",
                "style": "pending",
                "text": "这一结果关闭了 L=40、alpha=0.23、beta=0.5 严格 q=pi TEBD 的 maxdim 收敛缺口，但不关闭 q=0 守恒、动量反演或 CV 主峰交叉验证。参考图 Fig. 4–5 可继续用已有纠缠/选择定则数据制作；Fig. 6–8 的正式多点谱仍需补齐 CV 主峰和主要积分窗。",
            },
        ],
    }
    report["sections"] = [item for item in report["sections"] if item["title"] != TITLE]
    report["sections"].insert(0, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03 · MAXDIM TERMINAL"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"section": TITLE, "status": summary["status"], "receipt": receipt["status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
