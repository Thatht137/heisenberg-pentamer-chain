#!/usr/bin/env python3
"""把有效能隙有限尺寸复核写入长期 HTML 报告源。"""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "results" / "research_progress"
REPORT = REPORT_DIR / "report.json"
RUN = ROOT / "results" / "autoresearch_v5_20260731" / "round12_effective_gap_scaling"
SECTION_TITLE = "有效能隙有限尺寸复核"
FIGURE_NAME = "effective_gap_scaling_20260731.png"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def fmt_percent(value: float) -> str:
    return f"{100 * value:.2f}%"


def build_section(summary: dict[str, object], series: list[dict[str, str]]) -> dict[str, object]:
    fit = summary["fit"]
    alpha_fit = fit["alpha"]
    deviation_range = summary["controlled_mean_abs_deviation_range"]
    rows = []
    for item in series:
        controlled = item["controlled"] == "True"
        rows.append(
            [
                item["alpha"],
                item["beta"],
                f"{float(item['control_ratio']):.3f}",
                fmt_percent(float(item["mean_abs_relative_deviation"])),
                fmt_percent(float(item["max_abs_relative_deviation"])),
                "受控" if controlled else "排除出拟合",
            ]
        )
    return {
        "title": SECTION_TITLE,
        "note": "2026-07-31 · 复用 L=40/60/80 数据；不增加服务器计算",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "有限尺寸趋势接近有效链，但严格共同塌缩未通过",
                "why": "五条 beta/Delta_local<1 曲线对 matched-size oracle 的平均绝对偏差为 1.10%–4.79%，共同幂律拟合 chi2/dof=5.30。",
            },
            {
                "kind": "text",
                "text": "把完整五聚体链的自旋能隙除以一阶投影交换 $J_{\\mathrm{eff}}$ 后，$N=8,12,16$ 的下降趋势与同尺寸开放 Heisenberg 链接近。受控五条曲线的偏差没有随 $\\beta/\\Delta_{\\mathrm{local}}$ 单调变化，因此当前证据支持低能有效链机制，但不能表述为已经获得参数无关的普适塌缩。唯一 $\\beta/\\Delta_{\\mathrm{local}}>1$ 的点平均偏离 27.0%，与投影失控预期一致。",
            },
            {
                "kind": "figures",
                "items": [
                    {
                        "src": FIGURE_NAME,
                        "caption": "初步通过。a：六组五聚体链的归一化自旋能隙与 matched-size 开放 Heisenberg oracle；误差条为方差残差范数和末扫能量漂移构造的保守数值代理。b：各曲线跨 N=8,12,16 的平均绝对 oracle 偏差；虚线为 beta/Delta_local=1 投影控制边界。受控曲线偏差为 1.10%–4.79%，失控点为 27.0%；严格共同塌缩未通过。",
                    }
                ],
            },
            {
                "kind": "table",
                "columns": ["alpha", "beta", "beta/Delta_local", "平均绝对偏差", "最大绝对偏差", "拟合状态"],
                "rows": rows,
                "numeric": [True, True, True, True, True, False],
                "widths": ["10%", "10%", "19%", "20%", "20%", "21%"],
            },
            {
                "kind": "table",
                "columns": ["检验量", "结果", "解释"],
                "rows": [
                    ["共同幂律指数标签", f"{alpha_fit['value']:.4f} [{alpha_fit['ci_lo']:.4f}, {alpha_fit['ci_hi']:.4f}]", "1000 次参数 bootstrap；0 次失败"],
                    ["oracle 端点有效斜率", f"{summary['oracle_endpoint_effective_slope_N8_to_N16']:.4f}", "由 N=8 与 16 精确能隙直接计算，不是拟合"],
                    ["chi2/dof", f"{fit['chi2_per_dof']['value']:.2f}", "大于 1；拒绝在当前误差模型下的严格共同曲线"],
                    ["受控平均偏差范围", f"{fmt_percent(deviation_range[0])}–{fmt_percent(deviation_range[1])}", "趋势一致，但偏差不单调"],
                    ["失控点平均偏差", fmt_percent(summary["largest_control_ratio"]["mean_abs_relative_deviation"]), "beta/Delta_local=1.290；不进入拟合"],
                ],
                "numeric": [False, True, False],
                "widths": ["30%", "28%", "42%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["误差代理", "每个扇区取 max(sqrt(L × variance_per_site), |末扫能量变化|)，能隙误差取两扇区之和"],
                    ["拟合形式", "唯一预注册形式：Delta_s/J_eff = A N^(-p)；未轮换其他形式"],
                    ["拟合范围", "仅 beta/Delta_local<1，共 5 条曲线、15 个点"],
                    ["数据来源", "round2 effective scan 的已选择 Sz=0/1 扇区；matched-size oracle 为精确对角化"],
                    ["完成度影响", "强化有效链机制的有限尺寸复核；核心科学完成度仍约 45%"],
                ],
            },
            {
                "kind": "code",
                "title": "复现入口",
                "text": "scripts/autoresearch_v5/analyze_effective_gap_scaling.py\nresults/autoresearch_v5_20260731/round12_effective_gap_scaling/effective_gap_scaling.csv\nresults/autoresearch_v5_20260731/round12_effective_gap_scaling/series_summary.csv\nresults/autoresearch_v5_20260731/round12_effective_gap_scaling/scaling-fit.csv\nresults/autoresearch_v5_20260731/round12_effective_gap_scaling/summary.json\nresults/autoresearch_v5_20260731/round12_effective_gap_scaling/checksums.sha256",
            },
            {
                "kind": "note",
                "label": "证据边界",
                "style": "pending",
                "text": "误差代理不是统计抽样误差，bootstrap 区间只是对该数值误差模型的敏感性区间。源数据不是 round10 的全矩阵双初态生产结果，因此本节仅作机制复核，不替代正区生产计算，也不用于声明新相界。",
            },
        ],
    }


def update_latest(report: dict[str, object]) -> None:
    section = next(item for item in report["sections"] if item["title"] == "最新成果")
    table = next(block for block in section["blocks"] if block.get("kind") == "table")
    row = [
        "有效能隙有限尺寸复核",
        "受控曲线平均 oracle 偏差 1.10%–4.79%；共同拟合 chi2/dof=5.30",
        "支持有效链趋势，但严格跨参数塌缩未通过",
    ]
    for index, old in enumerate(table["rows"]):
        if old and old[0] == row[0]:
            table["rows"][index] = row
            return
    table["rows"].append(row)


def update_log(report: dict[str, object]) -> None:
    section = next(item for item in report["sections"] if item["title"] == "进展日志")
    table = next(block for block in section["blocks"] if block.get("kind") == "table")
    row = [
        "2026-07-31",
        "有效能隙有限尺寸复核",
        "比较 Delta_s/J_eff 与 matched-size Heisenberg oracle",
        "受控偏差 1.10%–4.79%；p=0.8639；chi2/dof=5.30",
        "初步完成",
    ]
    for index, old in enumerate(table["rows"]):
        if old and old[1] == row[1]:
            table["rows"][index] = row
            return
    table["rows"].append(row)


def main() -> None:
    summary = json.loads((RUN / "summary.json").read_text(encoding="utf-8"))
    series = read_csv(RUN / "series_summary.csv")
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-07-31"
    report["lede"] = "持续记录 1x5 五聚体链复现工作的计算、验收与物理结论。本页只包含 alpha >= 0、beta >= 0 的研究内容；阶段结果仅进入本 HTML，不同步修改 paper/。"
    report["sections"] = [item for item in report["sections"] if item["title"] != SECTION_TITLE]
    insert_at = next(
        (index for index, item in enumerate(report["sections"]) if item["title"] == "数值验收"),
        len(report["sections"]),
    )
    report["sections"].insert(insert_at, build_section(summary, series))
    update_latest(report)
    update_log(report)
    shutil.copy2(RUN / "effective_gap_scaling.png", REPORT_DIR / FIGURE_NAME)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已更新 {REPORT}")


if __name__ == "__main__":
    main()
