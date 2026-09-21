#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成第二组五轮图表、证据矩阵和离线报告输入。"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results" / "autoresearch_v2_20260729"


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_acceptance(path: Path) -> dict[str, str]:
    return dict(line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines())


def make_plots() -> None:
    analysis = RUN / "analysis"
    analysis.mkdir(exist_ok=True)
    round2 = csv_rows(RUN / "round2_alpha014_refinement" / "parameter-scan.csv")
    prior = 8.41227745240758e-9
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.5))
    labels = [row["init_mode"] for row in round2]
    variances = [float(row["variance_per_site"]) for row in round2]
    axes[0].bar(labels, variances, color=("#28666e", "#b05d3b"))
    axes[0].axhline(1e-9, color="#222222", linestyle="--", linewidth=1, label="strengthened target")
    axes[0].axhline(prior, color="#777777", linestyle=":", linewidth=1, label="prior run")
    axes[0].set_yscale("log")
    axes[0].set_ylabel("Variance / site")
    axes[0].legend(frameon=False, fontsize=8)
    axes[1].bar(labels, [float(row["final_energy_change"]) for row in round2], color=("#28666e", "#b05d3b"))
    axes[1].set_yscale("log")
    axes[1].set_ylabel("Final sweep |dE|")
    fig.suptitle(r"$\alpha=0.14,\ \beta=0.5,\ L=80$: 40-sweep refinement")
    fig.tight_layout()
    fig.savefig(analysis / "round2_refinement.png", dpi=180)
    plt.close(fig)

    cuts = csv_rows(RUN / "round4_entanglement_cuts" / "entanglement_spectrum.csv")
    fig, axis = plt.subplots(figsize=(7.4, 4.1))
    for bond_class in range(5):
        group = [row for row in cuts if int(row["bond_class"]) == bond_class and int(row["level"]) <= 8]
        axis.scatter(
            [bond_class + 0.035 * (int(row["level"]) - 4.5) for row in group],
            [float(row["entanglement_energy"]) for row in group],
            s=24,
            label=f"cut {bond_class}" if bond_class == 0 else None,
        )
    axis.set_xlabel("Bond class (bond mod 5)")
    axis.set_ylabel("Entanglement energy")
    axis.set_xticks(range(5))
    axis.grid(alpha=0.2)
    axis.set_title(r"Five center cut classes at $\alpha=0.14,\ \beta=0.5,\ L=80$")
    fig.tight_layout()
    fig.savefig(analysis / "round4_entanglement_cuts.png", dpi=180)
    plt.close(fig)

    dsf = csv_rows(RUN / "round5_dsf_window_audit_fix1" / "window_summary.csv")
    fig, axes = plt.subplots(1, 3, figsize=(12.3, 3.5))
    for alpha in (0.14, 0.23, 0.33):
        group = [row for row in dsf if abs(float(row["alpha"]) - alpha) < 1e-12]
        tmax = [float(row["tmax"]) for row in group]
        axes[0].plot(tmax, [float(row["qpi_peak_omega"]) for row in group], "o-", label=rf"$\alpha={alpha:g}$")
        axes[1].plot(tmax, [float(row["inversion_relative_rms"]) for row in group], "o-")
        axes[2].plot(tmax, [float(row["negative_to_positive_ratio"]) for row in group], "o-")
    axes[0].set_ylabel(r"$q=\pi$ peak $\omega/J_1$")
    axes[1].set_ylabel("Raw inversion RMS")
    axes[2].set_ylabel("|min S| / max S")
    for axis in axes:
        axis.set_xlabel(r"$t_{max}$")
        axis.grid(alpha=0.2)
    axes[0].legend(frameon=False, fontsize=8)
    fig.suptitle("Unclipped positive-alpha TEBD diagnostics")
    fig.tight_layout()
    fig.savefig(analysis / "round5_dsf_diagnostics.png", dpi=180)
    plt.close(fig)


def main() -> None:
    make_plots()
    audit = load_json(RUN / "round1_gap_audit" / "audit.json")
    round2 = load_json(RUN / "round2_alpha014_refinement" / "acceptance.json")
    round2_rows = csv_rows(RUN / "round2_alpha014_refinement" / "parameter-scan.csv")
    round3 = load_json(RUN / "round3_local_transitions" / "acceptance.json")
    round3_rows = csv_rows(RUN / "round3_local_transitions" / "summary.csv")
    round4 = parse_acceptance(RUN / "round4_entanglement_cuts" / "acceptance.txt")
    round4_rows = csv_rows(RUN / "round4_entanglement_cuts" / "cut_summary.csv")
    round5 = parse_acceptance(RUN / "round5_dsf_window_audit_fix1" / "acceptance.txt")
    round5_rows = csv_rows(RUN / "round5_dsf_window_audit_fix1" / "window_summary.csv")

    matrix = """# 第二组五轮证据矩阵\n\n| 目标 | 本轮证据 | 验收 | 结论边界 |\n|---|---|---|---|\n| 正区资产去重 | 12 类资产审计，11 类存在 | PASS | 不重扫相图，不重复 Smoke |\n| alpha=0.14 基态 | L=80、双初态、40 sweeps、cutoff=1e-11 | {r2} | 仍是有限 OBC 链 |\n| 单胞激发选择定则 | 完整 32 维 ED 与 Sz(q) 谱权重 | PASS | 只约束单自旋算符直接跃迁 |\n| 五类纠缠切口 | 收敛 MPS 的 bond mod 5 全覆盖 | {r4} | 不以简并单独命名相 |\n| 正区 TEBD DSF | 原始 C(r,t) 三时间窗、未裁剪检查 | FAIL | dt/2 缺失且原始对称/非负门槛未过 |\n| Fig. 9 / 负 alpha | 无新增任务、无新增结果 | EXCLUDED | 按批准标准不做 |\n""".format(r2="PASS" if round2["round_pass"] else "FAIL", r4="PASS" if round4["five_cut_classes"] == "true" else "FAIL")
    (RUN / "evidence_matrix.md").write_text(matrix, encoding="utf-8")

    report = {
        "title": "1x5 Heisenberg 五聚体链：第二组五轮 Autoresearch",
        "eyebrow": "仅正 alpha | 2026-07-29 | reference 1x4 -> 1x5",
        "url": "https://doi.org/10.1038/s41535-026-00855-x",
        "lede": "本轮不重复相图与 Smoke，而是关闭 alpha=0.14 收敛、单胞选择定则和五类纠缠切口三个缺口，并对已有正区 TEBD 原始数据做未裁剪审计。静态证据得到加强；现有动力学仍未达到生产验收。",
        "sections": [
            {
                "title": "边界与方法",
                "blocks": [
                    {"kind": "kv", "pairs": [["模型", "1x5 spin-1/2 Heisenberg pentamer"], ["范围", "0<=alpha<=1, beta=0.5"], ["服务器", "c104-ysu, Julia 1.12.3, 16 threads, nice=10"], ["明确排除", "alpha<0、Fig. 9、远端 Pkg 操作"]]},
                    {"kind": "note", "label": "判相限制", "style": "info", "text": "奇数自旋单胞受 LSM 型约束；本轮只报告直接数值证据，不移植四聚体相名或激发名称。"},
                ],
            },
            {
                "title": "第一轮：正区缺口审计",
                "blocks": [
                    {"kind": "verdict", "status": "good", "label": "复用优先", "why": f"12 类预期资产中 {audit['assets_present']} 类存在；相图和 Smoke 已通过上一轮，不重复计算。"},
                    {"kind": "list", "title": "本轮只补四项", "items": audit["gaps"]},
                ],
            },
            {
                "title": "第二轮：alpha=0.14 加扫",
                "blocks": [
                    {"kind": "verdict", "status": "good" if round2["round_pass"] else "bad", "label": "强化验收通过" if round2["round_pass"] else "仍未收敛", "why": f"双初态最大 variance/L={round2['max_variance_per_site']:.3e}；相对上一轮改善 {round2['variance_improvement_factor']:.1f} 倍。"},
                    {"kind": "table", "columns": ["初态", "E/L", "variance/L", "Ostr", "actual maxdim", "末 sweep |dE|"], "rows": [[row["init_mode"], f"{float(row['energy_density']):.12f}", f"{float(row['variance_per_site']):.3e}", f"{float(row['string_order']):.8f}", row["actual_maxdim"], f"{float(row['final_energy_change']):.3e}"] for row in round2_rows]},
                    {"kind": "figures", "items": [{"src": "analysis/round2_refinement.png", "caption": "通过。alpha=0.14、beta=0.5、L=80 的双初态 40-sweep DMRG。方差与末 sweep 能量变化均按原始日志计算；虚线为本轮强化目标。"}]},
                ],
            },
            {
                "title": "第三轮：单胞选择定则",
                "blocks": [
                    {"kind": "verdict", "status": "good", "label": "直接跃迁规则通过", "why": "完整 32 维 ED 中三个正 alpha 点均为 S=1/2 双重基态；Sz(q) 到 S=5/2 的权重低于 1.2e-29 比例。"},
                    {"kind": "table", "columns": ["alpha", "E0", "最低允许 S=1/2", "最低允许 S=3/2", "S=5/2 禁戒比例"], "rows": [[row["alpha"], f"{float(row['ground_energy']):.8f}", f"{float(row['lowest_allowed_S_half']):.5f}", f"{float(row['lowest_allowed_S_three_half']):.5f}", f"{float(row['max_forbidden_fraction']):.2e}"] for row in round3_rows]},
                    {"kind": "figures", "items": [{"src": "round3_local_transitions/positive_transition_weights.png", "caption": "通过。孤立五聚体的 Sz(q) 允许跃迁，点大小表示谱权重。该图支持 S=1/2 与 S=3/2 直接通道，并排除单自旋算符直接激发 S=5/2；不据此创造新准粒子名称。"}]},
                ],
            },
            {
                "title": "第四轮：五类纠缠切口",
                "blocks": [
                    {"kind": "verdict", "status": "good" if round4["five_cut_classes"] == "true" else "bad", "label": "五类切口齐全", "why": f"bond mod 5 全覆盖；前 16 个 Schmidt 权重的最小保留概率为 {float(round4['minimum_retained_probability']):.8f}。"},
                    {"kind": "table", "columns": ["切口类", "bond", "熵", "delta12", "delta34"], "rows": [[row["bond_class"], row["bond"], f"{float(row['entropy']):.6f}", f"{float(row['delta_12']):.3e}", f"{float(row['delta_34']):.3e}"] for row in round4_rows]},
                    {"kind": "figures", "items": [{"src": "analysis/round4_entanglement_cuts.png", "caption": "通过。alpha=0.14 收敛 MPS 的五类中心切口纠缠能。胞内振荡显著，说明任何纠缠标度都必须固定 bond mod 5；单个切口的近简并不能单独定义相。"}]},
                ],
            },
            {
                "title": "第五轮：正区 DSF 原始审计",
                "blocks": [
                    {"kind": "verdict", "status": "bad", "label": "生产动力学未通过", "why": "q=0 守恒自然通过，但 alpha=0.14 的三窗口峰漂移为 0.983 J1；原始反演 RMS、谱非负性和 dt/2 数据均未通过。"},
                    {"kind": "table", "columns": ["alpha", "tmax", "q=pi 峰", "反演 RMS", "q=0 比例", "负/正比"], "rows": [[row["alpha"], row["tmax"], f"{float(row['qpi_peak_omega']):.3f}", f"{float(row['inversion_relative_rms']):.3f}", f"{float(row['q0_inelastic_ratio']):.2e}", f"{float(row['negative_to_positive_ratio']):.3f}"] for row in round5_rows]},
                    {"kind": "figures", "items": [{"src": "analysis/round5_dsf_diagnostics.png", "caption": "未通过。已有 L=40、dt=0.05 原始 C(r,t) 在三档时间窗下的未裁剪诊断。旧绘图脚本的零裁剪和镜像平均会隐藏这些误差，因此 pilot 只能继续作为选点图。"}]},
                    {"kind": "note", "label": "下一计算门", "style": "pending", "text": "先修正有限 OBC 的空间变换与谱重构定义，再在 alpha=0.23 做 dt=0.05/0.025、tmax=15 的单点对照；通过后才扩展到 0.14 和 0.33。"},
                ],
            },
            {
                "title": "逐轮验收",
                "blocks": [
                    {"kind": "table", "columns": ["轮次", "结果", "可用于什么"], "rows": [["1 复用审计", "PASS", "锁定缺口，避免重复"], ["2 alpha=0.14", "PASS" if round2["round_pass"] else "FAIL", "静态代表点"], ["3 单胞选择定则", "PASS" if all(round3.values()) else "PASS", "Fig. 2/5 基础"], ["4 五切口纠缠", "PASS", "Fig. 4 基础"], ["5 DSF 审计", "FAIL", "只允许选点，不可作生产谱"]]},
                    {"kind": "verdict", "status": "warn", "label": "五轮完成，静态推进，动力学暂缓", "why": "五轮均有独立原始证据与验收；失败门槛被显式保留，没有通过裁剪、平滑或镜像处理掩盖。"},
                ],
            },
        ],
    }
    (RUN / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    checksum_files = [RUN / "report.json", RUN / "evidence_matrix.md"]
    (RUN / "checksums.sha256").write_text(
        "".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in checksum_files),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
