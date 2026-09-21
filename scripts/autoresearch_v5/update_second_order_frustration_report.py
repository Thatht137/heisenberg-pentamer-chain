#!/usr/bin/env python3
"""把二阶诱导挫折及十五自旋验证写入长期 HTML 报告源。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "results" / "research_progress"
REPORT = REPORT_DIR / "report.json"
ROUND14 = ROOT / "results" / "autoresearch_v5_20260731" / "round14_schrieffer_wolff"
ROUND15 = ROOT / "results" / "autoresearch_v5_20260731" / "round15_three_cell_sw_validation"
ROUND16 = ROOT / "results" / "autoresearch_v5_20260731" / "round16_second_paper_novelty_audit"
SECTION_TITLE = "二阶虚激发诱导有效挫折"
FIGURE_NAME = "schrieffer_wolff_second_order_20260731.png"


def percent_range(values: list[float]) -> str:
    return f"{100 * values[0]:.2f}%–{100 * values[1]:.2f}%"


def build_section(sw: dict[str, object], validation: dict[str, object], audit: dict[str, object]) -> dict[str, object]:
    with_j2 = validation["with_J2_error_power"]
    without_j2 = validation["without_J2_error_power"]
    literature_rows = [
        [item["title"], str(item["year"]), item["doi"], item["relation"]]
        for item in audit["closest_related_works"]
    ]
    return {
        "title": SECTION_TITLE,
        "note": "2026-07-31 · 100 个正 alpha 点 SW 展开；12 个完整十五自旋谱验证 cell",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good",
                "label": "完整十五自旋谱确认二阶诱导 AFM J2",
                "why": "加入 J2 后 12/12 个谱误差均降低并恢复 O(beta^3)；删除 J2 后残留 O(beta^2)。",
            },
            {
                "kind": "text",
                "text": "一阶投影只给出最近邻反铁磁有效链。二阶 Schrieffer–Wolff 展开显示，虚激发还会跨过中间五聚体产生次近邻交换。全部 100 个 $\\alpha\\geq0$ 扫描点均得到 $J_2^{(2)}>0$，因此微观 Hamiltonian 即使没有显式次近邻耦合，低能理论也会出现反铁磁有效挫折。这个效应在受控弱耦合区较弱，但不是算符拟合伪影。",
            },
            {
                "kind": "equation",
                "tex": "H_{\\mathrm{eff}}=\\sum_n\\left[\\beta J_1^{(1)}\\mathbf T_n\\cdot\\mathbf T_{n+1}+\\beta^2 C^{(2)}+\\beta^2\\delta J_1^{(2)}\\mathbf T_n\\cdot\\mathbf T_{n+1}\\right]+\\beta^2J_2^{(2)}\\sum_n\\mathbf T_n\\cdot\\mathbf T_{n+2}+O(\\beta^3)",
            },
            {
                "kind": "figures",
                "items": [
                    {
                        "src": FIGURE_NAME,
                        "caption": "通过。a：100 个正 alpha 点的二阶最近邻修正与诱导次近邻交换；J2^(2) 全部为正。b：J2^(2)/deltaJ1^(2)=0.2188–0.3196，说明两类二阶项具有稳定但非普适的比例。c：固定 beta/Delta_local 后的 J2/J1；在受控边缘 0.65 处仅为 3.95%–5.19%，对应弱而系统的有效挫折。",
                    }
                ],
            },
            {
                "kind": "table",
                "columns": ["检验", "结果", "含义"],
                "rows": [
                    ["正区符号", f"{sw['alpha_points']}/{sw['alpha_points']} 点 J2^(2)>0", "全正 alpha 扫描均为反铁磁"],
                    ["J2^(2) 范围", f"{sw['J2_second_range'][0]:.6f}–{sw['J2_second_range'][1]:.6f}", "系数随局域能隙显著变化"],
                    ["J2^(2)/deltaJ1^(2)", f"{sw['J2_over_second_J1_range'][0]:.5f}–{sw['J2_over_second_J1_range'][1]:.5f}", "比例稳定但不是严格常数"],
                    ["受控边缘 J2/J1", percent_range(sw["controlled_edge_J2_over_J1_range"]), "beta/Delta_local=0.65 时仍为几个百分点"],
                    ["两胞算符拟合残差", f"{sw['max_two_fit_relative_residual']:.2e}", "算符基展开达到机器精度"],
                    ["三胞算符拟合残差", f"{sw['max_three_fit_relative_residual']:.2e}", "连通 J2 项可稳定分离"],
                    ["有限 beta 二阶系数差", f"{100 * sw['max_finite_beta_C2_relative_error']:.2f}%", "独立有限 beta ED 与 SW 一致"],
                ],
                "numeric": [False, True, False],
                "widths": ["29%", "27%", "44%"],
            },
            {
                "kind": "heading",
                "level": 3,
                "text": "完整十五自旋谱交叉验证",
            },
            {
                "kind": "text",
                "text": "三胞完整 Hamiltonian 在 $2S^z=1$ 的 6435 维块中直接对角化，再与有、无 $J_2$ 的二阶有效 Hamiltonian 比较。三个代表 $\\alpha$、四个 $\\beta$ 共 12 个 cell 均显示同一结论：$J_2$ 把遗漏误差从二阶推迟到三阶。",
            },
            {
                "kind": "table",
                "columns": ["alpha", "含 J2 的误差幂", "不含 J2 的误差幂", "判断"],
                "rows": [
                    [alpha, f"{with_j2[alpha]:.4f}", f"{without_j2[alpha]:.4f}", "O(beta^3) 对 O(beta^2)"]
                    for alpha in ("0.14", "0.23", "0.33")
                ],
                "numeric": [True, True, True, False],
                "widths": ["15%", "25%", "25%", "35%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["验证规模", f"{validation['cells']} cells；完整 15 自旋；2Sz=1 块维数 {validation['block_dimension']}"],
                    ["误差改善", f"{validation['improvement_factor_range'][0]:.2f}–{validation['improvement_factor_range'][1]:.2f} 倍；12/12 cell 改善"],
                    ["最大本征残差", f"{validation['max_eigensolver_residual']:.2e}"],
                    ["验收门", "本征残差、三阶恢复、二阶遗漏、逐 cell 改善全部通过"],
                ],
            },
            {
                "kind": "verdict",
                "status": "warn",
                "label": "值得发展为第二篇文章候选，但尚不可投稿",
                "why": "初筛未发现直接匹配工作；仍缺一般奇数团簇推广、全文级文献审计和更大系统验证。",
            },
            {
                "kind": "table",
                "columns": ["相关工作", "年份", "DOI", "与本结果的边界"],
                "rows": literature_rows,
                "numeric": [False, True, False, False],
                "muted": [False, False, True, False],
                "widths": ["27%", "8%", "22%", "43%"],
            },
            {
                "kind": "note",
                "label": "新颖性边界",
                "style": "pending",
                "text": "本轮使用 OpenAlex 元数据与摘要片段初筛，未接入 Scopus、Web of Science 和中文数据库，也没有完成逐篇全文比对。因此“未发现直接同类”不是新颖性证明，当前只能登记为独立文章候选。",
            },
            {
                "kind": "code",
                "title": "复现入口",
                "text": "scripts/autoresearch_v5/analyze_second_order_schrieffer_wolff.py\nscripts/autoresearch_v5/validate_three_cell_schrieffer_wolff.py\nresults/autoresearch_v5_20260731/round14_schrieffer_wolff/summary.json\nresults/autoresearch_v5_20260731/round14_schrieffer_wolff/checksums.sha256\nresults/autoresearch_v5_20260731/round15_three_cell_sw_validation/summary.json\nresults/autoresearch_v5_20260731/round15_three_cell_sw_validation/checksums.sha256\nresults/autoresearch_v5_20260731/round16_second_paper_novelty_audit/literature_novelty_audit.json",
            },
        ],
    }


def upsert_row(table: dict[str, object], key_index: int, row: list[str]) -> None:
    for index, old in enumerate(table["rows"]):
        if len(old) > key_index and old[key_index] == row[key_index]:
            table["rows"][index] = row
            return
    table["rows"].append(row)


def update_latest(report: dict[str, object]) -> None:
    section = next(item for item in report["sections"] if item["title"] == "最新成果")
    table = next(block for block in section["blocks"] if block.get("kind") == "table")
    upsert_row(
        table,
        0,
        [
            "二阶诱导有效挫折",
            "100/100 点 J2^(2)>0；15 自旋谱误差改善 2.23–31.15 倍",
            "含 J2 后遗漏从 O(beta²) 推迟到 O(beta³)",
        ],
    )
    if not any(block.get("label") == "发现第二篇文章候选方向" for block in section["blocks"]):
        section["blocks"].insert(
            1,
            {
                "kind": "verdict",
                "status": "warn",
                "label": "发现第二篇文章候选方向",
                "why": "二阶虚激发诱导 AFM J2 已通过完整十五自旋谱验证；一般奇数团簇推广与全文文献审计尚未完成。",
            },
        )


def update_completion(report: dict[str, object]) -> None:
    section = next(item for item in report["sections"] if item["title"] == "论文复现完成度")
    verdict = next(block for block in section["blocks"] if block.get("kind") == "verdict")
    verdict.update(
        {
            "label": "核心科学内容约完成 50%",
            "why": "低能机制、局域多重态和二阶有效 Hamiltonian 已由完整谱闭环；正区系统相图与生产级长链 DSF 仍是决定性缺口。",
        }
    )
    text = next(block for block in section["blocks"] if block.get("kind") == "text")
    text["text"] = "这个比例按可进入论文并通过当前验收标准的证据计算，不按脚本数量或图片数量计算。核心科学内容约完成 50%；参考论文逐图替换约完成 50%；投稿级完整度约完成 35%。二阶诱导 J2 显著加强 Fig. 8 的解析归属和低能理论，但不替代待完成的正区生产静态矩阵与长链 DSF。"
    table = next(block for block in section["blocks"] if block.get("kind") == "table")
    for row in table["rows"]:
        if row[0] == "Fig. 8 色散归属":
            row[2] = "55%"
            row[3] = "受控区边界与二阶 J2 已由 15 自旋谱验证；仍缺有限 beta 生产谱和独立方法交叉检查"
            break
    kv = next(block for block in section["blocks"] if block.get("kind") == "kv")
    for pair in kv["pairs"]:
        if pair[0] == "已形成的主线":
            pair[1] = "有效 S=1/2 反铁磁链；二阶虚激发诱导弱 AFM J2；校准后 c=1；q=pi 局域四重态可见"
        elif pair[0] == "已完成的严格结果":
            pair[1] = "单胞能级、二阶 SW 有效理论、15 自旋谱验证、ED oracle、36-cell DMRG、纠缠校准、局域选择定则"


def update_log(report: dict[str, object]) -> None:
    section = next(item for item in report["sections"] if item["title"] == "进展日志")
    table = next(block for block in section["blocks"] if block.get("kind") == "table")
    rows = [
        ["2026-07-31", "二阶 SW 有效理论", "100 点正 alpha 两胞/三胞连通展开", "J2^(2)>0；受控边缘 J2/J1=3.95%–5.19%", "完成"],
        ["2026-07-31", "十五自旋谱验证", "12 个完整 15 自旋低能谱与有效模型比较", "含 J2 为 O(beta^3)；无 J2 残留 O(beta^2)", "完成"],
        ["2026-07-31", "第二篇文章候选审计", "针对虚激发诱导挫折做文献初筛", "未发现直接匹配；仍需全文审计与一般化", "候选"],
    ]
    for row in rows:
        upsert_row(table, 1, row)


def update_outputs(report: dict[str, object]) -> None:
    section = next(item for item in report["sections"] if item["title"] == "成果文件")
    code = next(block for block in section["blocks"] if block.get("kind") == "code")
    additions = [
        "scripts/autoresearch_v5/analyze_second_order_schrieffer_wolff.py",
        "scripts/autoresearch_v5/validate_three_cell_schrieffer_wolff.py",
        "results/autoresearch_v5_20260731/round14_schrieffer_wolff/summary.json",
        "results/autoresearch_v5_20260731/round15_three_cell_sw_validation/summary.json",
        "results/autoresearch_v5_20260731/round16_second_paper_novelty_audit/literature_novelty_audit.json",
    ]
    lines = code["text"].splitlines()
    code["text"] = "\n".join(lines + [item for item in additions if item not in lines])


def main() -> None:
    sw = json.loads((ROUND14 / "summary.json").read_text(encoding="utf-8"))
    validation = json.loads((ROUND15 / "summary.json").read_text(encoding="utf-8"))
    audit = json.loads((ROUND16 / "literature_novelty_audit.json").read_text(encoding="utf-8"))
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-07-31"
    report["lede"] = "持续记录 1x5 五聚体链复现工作的计算、验收与物理结论。本页只包含 alpha >= 0、beta >= 0 的研究内容；阶段结果仅进入本 HTML，不同步修改 paper/。"
    report["sections"] = [item for item in report["sections"] if item["title"] != SECTION_TITLE]
    insert_at = next(
        (index for index, item in enumerate(report["sections"]) if item["title"] == "数值验收"),
        len(report["sections"]),
    )
    report["sections"].insert(insert_at, build_section(sw, validation, audit))
    update_latest(report)
    update_completion(report)
    update_log(report)
    update_outputs(report)
    shutil.copy2(ROUND14 / "schrieffer_wolff_second_order.png", REPORT_DIR / FIGURE_NAME)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已更新 {REPORT}")


if __name__ == "__main__":
    main()
