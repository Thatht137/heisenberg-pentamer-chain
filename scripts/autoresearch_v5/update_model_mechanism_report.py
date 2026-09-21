#!/usr/bin/env python3
"""把模型与激发机制正式图写入长期研究报告。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "results" / "research_progress"
REPORT = REPORT_DIR / "report.json"
RUN = ROOT / "results" / "autoresearch_v5_20260731" / "round9_model_mechanism_figures"
FIGURE_DIR = ROOT / "figures"
SECTION_TITLE = "模型与激发机制正式图"
MODEL_FIGURE = "pentamer_model_effective_chain_20260731.png"
FILTER_FIGURE = "pentamer_momentum_filter_20260731.png"


def build_section(summary: dict[str, object]) -> dict[str, object]:
    model = summary["model_metrics"]
    filtered = summary["filter_metrics"]
    return {
        "title": SECTION_TITLE,
        "note": "2026-07-31 · 复用已验收 ED 数据；未新增服务器计算",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good",
                "label": "Fig. 1 与 Fig. 5 的正式证据图已闭合",
                "why": "模型几何、低能投影、反铁磁有效交换和 q=pi 宇称过滤均由同一组可追溯 ED 数据支撑。",
            },
            {
                "kind": "text",
                "text": "第一张图把 1x5 Hamiltonian、五格点投影系数与全正 alpha 区域的 $J_{\\mathrm{eff}}/\\beta$ 放在同一证据链中；第二张图把能级宇称、离散动量谱权和全 alpha 区间的自旋通道占比放在同一证据链中。它们说明五聚体版本不能被理解为四聚体相界的平移：奇数单胞留下有效半整数自旋，而局域探针还会受到严格的动量与宇称过滤。",
            },
            {
                "kind": "figures",
                "items": [
                    {
                        "src": MODEL_FIGURE,
                        "caption": "通过。a：1x5 微观链及其低能投影；b：alpha=0.23 的五个投影系数，交错符号且总和为 1；c：100 个正 alpha ED 点的 J_eff/beta=c1c5 始终为正。正 beta 因而产生反铁磁有效 S=1/2 链。",
                    },
                    {
                        "src": FILTER_FIGURE,
                        "caption": "通过。a：q=pi 算符为反射偶宇称，最低奇宇称双重态为暗通道，而偶宇称四重态可见；b：alpha=0.23 的离散动量权重直接显示双重态在 q=pi 消失；c：全部正 alpha 区域中，四重态占 q=pi 局域非弹性权重的 84.1%–97.6%。",
                    },
                ],
            },
            {
                "kind": "table",
                "columns": ["验收量", "结果", "门槛", "状态"],
                "rows": [
                    ["投影和规则", f"sum(c_i)={model['coefficient_sum']:.15f}", "|sum-1|<=1e-12", "通过"],
                    ["反射对称误差", f"{model['reflection_error']:.2e}", "<=1e-12", "通过"],
                    ["全正区最小 J_eff/beta", f"{model['minimum_jeff_over_beta']:.6f}", ">0", "通过"],
                    ["最低双重态 q=pi 权重", f"{filtered['lowest_doublet_qpi_weight']:.2e}", "<=1e-24", "通过"],
                    ["四重态最小非弹性占比", f"{100*filtered['quartet_fraction_min']:.1f}%", ">=80%", "通过"],
                    ["S=5/2 最大占比", f"{filtered['sextet_fraction_max']:.2e}", "<=1e-24", "通过"],
                ],
                "numeric": [False, True, True, False],
                "widths": ["35%", "23%", "23%", "19%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["图形后端", "Python/matplotlib；183 mm 双栏宽度"],
                    ["导出", "SVG、PDF、600 dpi PNG、600 dpi LZW TIFF"],
                    ["源数据", "100 点 projection_scan；multiplet_scan；folded_transition_weights"],
                    ["图像 QA", "最终尺寸可读；无文字遮挡；SVG/PDF 文字可编辑"],
                    ["完成度影响", "Fig. 1 与 Fig. 5 从缺正式图更新为完成；不把作图计作新物理证据"],
                ],
            },
            {
                "kind": "code",
                "title": "复现入口",
                "text": "scripts/autoresearch_v5/plot_model_excitation_mechanism.py\nresults/autoresearch_v5_20260731/round9_model_mechanism_figures/model_mechanism_summary.json\nfigures/pentamer_model_effective_chain_20260731.svg\nfigures/pentamer_momentum_filter_20260731.svg",
            },
            {
                "kind": "note",
                "label": "结论边界",
                "style": "pending",
                "text": "这两张图闭合的是孤立单胞与一阶低能投影机制。有限 beta 链上的谱支是否保持尖锐、形成共振或混入连续谱，仍必须由 L=80 生产 CV 与 TEBD 交叉检查决定。",
            },
        ],
    }


def update_completion(report: dict[str, object]) -> None:
    section = next(item for item in report["sections"] if item["title"] == "论文复现完成度")
    section["note"] = "2026-07-31 · 仅统计 alpha >= 0；参考 Fig. 9 不在范围内"
    for block in section["blocks"]:
        if block.get("kind") == "text":
            block["text"] = (
                "这个比例按可进入论文并通过当前验收标准的证据计算，不按脚本数量或已生成图片数量计算。"
                "核心科学内容仍约完成 45%；参考论文逐图替换约完成 50%；投稿级完整度约完成 35%。"
                "本轮正式图提高的是证据表达完整度，不替代待完成的正区生产静态矩阵与长链 DSF。"
            )
        if block.get("kind") != "table":
            continue
        for row in block["rows"]:
            if row[0] == "Fig. 1 模型与单胞":
                row[2] = "100%"
                row[3] = "Hamiltonian、32 维 ED、投影机制与正式图全部完成"
            elif row[0] == "Fig. 5 激发通道":
                row[2] = "100%"
                row[3] = "局域选择定则和机制图完成；链上归属留给 Fig. 7–8"


def update_latest(report: dict[str, object]) -> None:
    section = next(item for item in report["sections"] if item["title"] == "最新成果")
    table = next(block for block in section["blocks"] if block.get("kind") == "table")
    name = "正式机制图"
    row = [name, "Fig. 1 与 Fig. 5；两张 183 mm 双栏图", "模型投影和 q=pi 宇称过滤形成可直接阅读的证据链"]
    existing = next((index for index, old in enumerate(table["rows"]) if old[0] == name), None)
    if existing is None:
        table["rows"].append(row)
    else:
        table["rows"][existing] = row


def update_log(report: dict[str, object]) -> None:
    section = next(item for item in report["sections"] if item["title"] == "进展日志")
    table = next(block for block in section["blocks"] if block.get("kind") == "table")
    row = [
        "2026-07-31",
        "模型与激发机制正式图",
        "复用投影与多重态 ED 数据绘制 Fig. 1 和 Fig. 5",
        "六项数值门槛与图像 QA 通过；核心科学完成度不虚增",
        "完成",
    ]
    existing = next((index for index, old in enumerate(table["rows"]) if old[1] == row[1]), None)
    if existing is None:
        table["rows"].append(row)
    else:
        table["rows"][existing] = row


def main() -> None:
    summary = json.loads((RUN / "model_mechanism_summary.json").read_text(encoding="utf-8"))
    if summary["tag"] != "pass":
        raise SystemExit("图形数值验收未通过")
    for name in (MODEL_FIGURE, FILTER_FIGURE):
        shutil.copy2(FIGURE_DIR / name, REPORT_DIR / name)

    report = json.loads(REPORT.read_text(encoding="utf-8"))
    report["sections"] = [item for item in report["sections"] if item["title"] != SECTION_TITLE]
    insert_at = next(
        (index + 1 for index, item in enumerate(report["sections"])
         if item["title"] == "论文复现完成度"),
        2,
    )
    report["sections"].insert(insert_at, build_section(summary))
    update_completion(report)
    update_latest(report)
    update_log(report)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已更新 {REPORT}")


if __name__ == "__main__":
    main()
