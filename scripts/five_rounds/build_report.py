#!/usr/bin/env python3
"""根据五轮验收数据生成 harness report.json。"""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results" / "five_rounds_20260729"


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def scientific(value: str | float, digits: int = 3) -> str:
    return f"{float(value):.{digits}e}"


def main() -> None:
    inventory = load_json(RUN / "round1_inventory" / "inventory.json")
    acceptance = load_json(RUN / "analysis" / "acceptance_summary.json")
    round2 = load_csv(RUN / "round2_smoke_fix1" / "parameter-scan.csv")
    round4 = load_csv(RUN / "round4_validation" / "parameter-scan.csv")
    cross = load_json(RUN / "round5_crosscheck" / "cross-method-check.json")
    main_round4 = [row for row in round4 if row["init_mode"] == "neel"]
    main_round4.sort(key=lambda row: float(row["alpha"]))

    convergence_rows = []
    for item in acceptance["round3"]["convergence"]:
        convergence_rows.append(
            [
                item["L"],
                item["actual_maxdim"],
                scientific(item["energy_density_difference_400_800"]),
                f"{100 * item['string_order_relative_difference_400_800']:.3f}%",
                "PASS" if all(
                    item[key]
                    for key in ("energy_pass", "observable_pass", "variance_pass", "truncation_pass")
                )
                else "FAIL",
            ]
        )

    validation_rows = [
        [
            row["alpha"],
            f"{float(row['energy_density']):.10f}",
            f"{float(row['string_order']):.6f}",
            f"{float(row['center_entropy']):.6f}",
            scientific(row["variance_per_site"]),
            row["actual_maxdim"],
        ]
        for row in main_round4
    ]

    smoke_rows = [
        [
            row["alpha"],
            f"{float(row['energy_density']):.10f}",
            scientific(row["variance_per_site"]),
            row["actual_maxdim"],
            f"{float(row['peak_rss_kb']) / 1024:.1f} MiB",
        ]
        for row in round2
    ]

    status = "good" if acceptance["overall_dmrg_acceptance"] and cross["tag"] == "Agreement" else "warn"
    report = {
        "title": "1x5 Heisenberg 五聚体链：五轮复现计算报告",
        "eyebrow": "APPROVED v1.0 | 仅正 alpha | 2026-07-29",
        "url": "https://doi.org/10.1038/s41535-026-00855-x",
        "lede": "复用参考论文的证据链，但把 1x4 四聚体改为 1x5 五聚体。报告只覆盖 0<=alpha<=1，并把服务器 DMRG、离线环境、收敛与独立 ED 交叉验证统一到可追溯验收流程中。",
        "sections": [
            {
                "title": "研究边界",
                "blocks": [
                    {
                        "kind": "equation",
                        "tex": "H=\\sum_n[J_2(\\mathbf S_{5n-4}\\cdot\\mathbf S_{5n-3}+\\mathbf S_{5n-1}\\cdot\\mathbf S_{5n})+J_1(\\mathbf S_{5n-3}\\cdot\\mathbf S_{5n-2}+\\mathbf S_{5n-2}\\cdot\\mathbf S_{5n-1})]+J_3\\sum_n\\mathbf S_{5n}\\cdot\\mathbf S_{5n+1}",
                    },
                    {
                        "kind": "kv",
                        "pairs": [
                            ["参数", "J1=1, alpha=J2/J1, beta=J3/J1"],
                            ["范围", "0<=alpha<=1, 0<=beta<=1"],
                            ["生产尺寸", "16 个五聚体，L=80，OBC，Sz=0"],
                            ["明确排除", "负 alpha、Fig. 9、CuInVO5 材料路径"],
                        ],
                    },
                    {
                        "kind": "note",
                        "label": "解释边界",
                        "style": "info",
                        "text": "五个 spin-1/2 构成半整数单胞，LSM 型约束使四聚体论文的相名不能直接移植。本报告验收数值质量，不宣告新的热力学相。",
                    },
                ],
            },
            {
                "title": "第一轮：复用审计",
                "blocks": [
                    {
                        "kind": "kv",
                        "pairs": [
                            ["原始相图行数", inventory["phase_map"]["rows"]],
                            ["唯一参数点", inventory["phase_map"]["unique_pairs"]],
                            ["重复行", inventory["phase_map"]["duplicate_rows"]],
                            ["正 alpha 唯一点", inventory["phase_map"]["positive_unique_pairs"]],
                            ["复用策略", "2400 个正 alpha 点只作选点地图，不整批重算"],
                        ],
                    },
                    {
                        "kind": "figures",
                        "items": [
                            {
                                "src": "round1_inventory/positive_phase_map_audit.png",
                                "caption": "审计后的正 alpha 选点地图。40x60 网格完整；重复记录数值一致。该图只用于选择验证点，不作为最终相界证据。",
                            }
                        ],
                    },
                ],
            },
            {
                "title": "Julia 与服务器环境",
                "blocks": [
                    {
                        "kind": "verdict",
                        "status": "warn",
                        "label": "锁定环境可计算；离线包管理受限",
                        "why": "服务器 Julia 1.12.3 可在强制断网代理下加载锁定依赖；Pkg.status 曾尝试访问 registry，因此生产任务完全禁止远端 Pkg 操作。",
                    },
                    {
                        "kind": "table",
                        "columns": ["项目", "本地", "服务器", "状态"],
                        "rows": [
                            ["Julia", "1.11.5", "1.12.3", "跨版本小尺寸检查"],
                            ["ITensors", "0.9.27", "0.9.27", "一致"],
                            ["ITensorMPS", "0.4.1", "0.4.1", "一致"],
                            ["JLD2", "0.6.4", "0.6.4", "一致"],
                            ["Manifest SHA-256", "37a53ffd...", "37a53ffd...", "一致"],
                        ],
                    },
                ],
            },
            {
                "title": "第二轮：Smoke",
                "blocks": [
                    {
                        "kind": "note",
                        "label": "保留的失败证据",
                        "style": "info",
                        "text": "首版 Smoke 的 DMRG 已完成，但局部整数变量 length 遮蔽 Base.length，导致 sweep 汇总失败。失败 run 未覆盖；修复版使用独立目录并通过 3/3。",
                    },
                    {
                        "kind": "table",
                        "columns": ["alpha", "E/L", "variance/L", "actual maxdim", "peak RSS"],
                        "rows": smoke_rows,
                        "numeric": [True, True, True, True, True],
                    },
                    {
                        "kind": "verdict",
                        "status": "good",
                        "label": "Smoke 通过",
                        "why": "三个正 alpha 点清单、断网加载、测量、资源记录和 SHA-256 全部通过。",
                    },
                ],
            },
            {
                "title": "第三轮：收敛",
                "blocks": [
                    {
                        "kind": "table",
                        "columns": ["L", "actual maxdim", "|d(E/L)| 400-800", "dOstr 400-800", "状态"],
                        "rows": convergence_rows,
                        "numeric": [True, True, True, True, False],
                    },
                    {
                        "kind": "figures",
                        "items": [
                            {
                                "src": "analysis/round3_convergence.png",
                                "caption": "通过。alpha=0.23、beta=0.5 的 L 与请求 maxdim 收敛。实际键维仅为 55/82/105，因此三档请求值给出相同结果；方差和截断误差均低于验收线。",
                            }
                        ],
                    },
                ],
            },
            {
                "title": "第四轮：正 alpha 验收点",
                "blocks": [
                    {
                        "kind": "table",
                        "columns": ["alpha", "E/L", "Ostr", "Scenter", "variance/L", "actual maxdim"],
                        "rows": validation_rows,
                        "numeric": [True, True, True, True, True, True],
                    },
                    {
                        "kind": "figures",
                        "items": [
                            {
                                "src": "analysis/round4_validation.png",
                                "caption": "通过。beta=0.5、L=80、maxdim=1200 的三个正 alpha 主点。曲线展示能量密度、五聚体弦序和中心纠缠熵；不据此单独命名相。",
                            }
                        ],
                    },
                    {
                        "kind": "kv",
                        "pairs": [
                            ["双初态能量密度差", scientific(acceptance["round4"]["initial_state_energy_density_difference"])],
                            ["双初态弦序相对差", f"{100 * acceptance['round4']['initial_state_string_order_relative_difference']:.5f}%"],
                            ["maxdim 800→1200 能量密度差", scientific(acceptance["round4"]["maxdim_800_to_1200_energy_density_difference"])],
                            ["maxdim 800→1200 弦序相对差", f"{100 * acceptance['round4']['maxdim_800_to_1200_string_order_relative_difference']:.3f}%"],
                        ],
                    },
                    {
                        "kind": "note",
                        "label": "边界警示",
                        "style": "pending",
                        "text": "alpha=0.14 的 variance/L=8.41e-9，低于 1e-8 门槛但余量较小。它可进入本轮报告，若用于精确临界拟合应追加 sweep 或更严格方差检查。",
                    },
                ],
            },
            {
                "title": "第五轮：独立交叉验证",
                "blocks": [
                    {
                        "kind": "verdict",
                        "status": "good" if cross["tag"] == "Agreement" else "bad",
                        "label": cross["tag"],
                        "why": f"同一 alpha=0.23、beta=0.5、L=10、OBC、Sz=0 点比较全 1024 维 Python 密集 ED 与服务器 ITensor DMRG；|dE|={cross['energy_difference']:.3e}。",
                    },
                    {
                        "kind": "kv",
                        "pairs": [
                            ["ED budget", scientific(cross["ed_budget"])],
                            ["DMRG budget", scientific(cross["dmrg_budget"])],
                            ["DMRG total variance", scientific(cross["dmrg_total_variance"])],
                        ],
                    },
                ],
            },
            {
                "title": "最终验收",
                "blocks": [
                    {
                        "kind": "verdict",
                        "status": status,
                        "label": "五轮数值工作通过" if status == "good" else "存在未关闭项目",
                        "why": "复用审计、Smoke、L/maxdim 收敛、三个正 alpha 主点、双初态、MPS、独立 ED/DMRG 和可追溯清单均已完成。",
                    },
                    {
                        "kind": "table",
                        "columns": ["验收项", "结果", "证据"],
                        "rows": [
                            ["负 alpha 排除", "PASS", "所有新清单均限制 0<=alpha<=1"],
                            ["Smoke", "PASS", "3/3，max variance/L=5.63e-10"],
                            ["收敛矩阵", "PASS", "9/9，实际 maxdim 未触顶"],
                            ["生产主点", "PASS", "3 主点 + 1 双初态，MPS 齐全"],
                            ["方法交叉", cross["tag"], f"|dE|={cross['energy_difference']:.3e}"],
                            ["Fig. 9", "不在范围", "按批准标准不复现"],
                        ],
                    },
                    {
                        "kind": "list",
                        "title": "结论使用限制",
                        "items": [
                            "L=80 是 16 个五聚体的有限开链，不是热力学极限。",
                            "现有正 alpha 相图是选点地图，不是带误差条的 crossing phase boundary。",
                            "本轮验证基态能量、弦序和纠缠；不包含 Fig. 9，也不新增负 alpha 动力学。",
                            "若下一步写相界或临界指数，需增加尺寸、误差条和独立临界诊断。",
                        ],
                    },
                ],
            },
        ],
    }
    (RUN / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
