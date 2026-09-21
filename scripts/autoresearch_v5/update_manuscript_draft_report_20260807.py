#!/usr/bin/env python3
"""把当前证据版论文草稿和结论边界写入研究报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results" / "research_progress" / "report.json"
TITLE = "2026-08-07 论文草稿与结论判断"


def section() -> dict:
    return {
        "title": TITLE,
        "note": "仅写入 HTML 报告；不修改 paper/。范围为 0<=alpha,beta<=1，排除负 alpha 与参考 Fig.9。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "当前证据版草稿可写，最终动力学结论待服务器",
                "why": "C1--C5、C10--C12 已有可追溯证据；full-q 六个生产 cell 尚未全部完成。",
            },
            {
                "kind": "heading",
                "text": "核心论点（one-sentence argument）",
                "level": 2,
            },
            {
                "kind": "text",
                "text": "在 1x5 Heisenberg 五聚体链的正耦合区域内，完整单胞谱和有限尺寸诊断表明，奇数个自旋 1/2 留下低能 S=1/2 双重态，并在受控胞间耦合下形成有效反铁磁自旋链；现有有限尺寸数据未发现可验收的内部 crossing，但这仍是有边界的有限尺寸结论，而不是热力学单相证明。",
            },
            {
                "kind": "heading",
                "text": "English manuscript draft（可供后续转入正文）",
                "level": 2,
            },
            {
                "kind": "heading",
                "text": "Provisional title",
                "level": 3,
            },
            {
                "kind": "text",
                "text": "Odd-unit-cell doublets and effective antiferromagnetism in a 1x5 Heisenberg chain",
            },
            {
                "kind": "heading",
                "text": "Abstract",
                "level": 3,
            },
            {
                "kind": "text",
                "text": "Odd-unit-cell quantum magnets provide a controlled setting in which local multiplet structure and extended-chain dynamics can be separated. We study a 1x5 Heisenberg chain in the non-negative coupling domain, 0<=alpha,beta<=1, using complete single-cell diagonalization, finite-size tensor-network calculations and validated dynamical cross-checks. The five-spin cell retains a low-energy S=1/2 doublet with fixed even mirror parity. Projecting the inter-cell coupling onto this doublet gives a positive effective exchange, J_eff/beta=0.4189--0.4396 at representative points, while two-cell and longer-chain calculations show the leading correction to scale approximately as beta^2. Matched-size finite-size diagnostics are consistent with a c approximately equal to 1 antiferromagnetic chain and the existing positive-region scans contain no stable, acceptance-level internal crossing. At alpha=0.23 and beta=0.5, correction-vector and TEBD spectra agree at q=pi under a documented normalization and coverage protocol. The remaining full-momentum production runs are required before claims about momentum folding and high-energy local branches are finalized. Thus the present evidence establishes an effective-chain mechanism and a bounded no-crossing result, but does not establish a thermodynamic single phase or a new phase boundary.",
            },
            {
                "kind": "heading",
                "text": "Introduction",
                "level": 3,
            },
            {
                "kind": "text",
                "text": "Quantum magnets built from strongly coupled clusters can exhibit low-energy behavior that is not visible from the microscopic bond pattern alone. The parity of the number of spins in a unit cell is especially important: an even cluster may form an internal singlet, whereas an odd cluster necessarily retains an unpaired spin-1/2 degree of freedom. This distinction changes the appropriate question from simply locating a phase boundary to identifying the effective degrees of freedom that survive below the local excitation scale.",
            },
            {
                "kind": "text",
                "text": "Here we investigate the five-spin analogue of a cluster-chain construction in the positive coupling domain. The main technical challenge is to separate robust single-cell symmetry information from finite-size features that can mimic a transition. We therefore combine complete local diagonalization, effective-chain projections, matched-size finite-size diagnostics and independent dynamical checks. The analysis is deliberately restricted to non-negative alpha and beta and does not use the reference Fig.9 sector.",
            },
            {
                "kind": "text",
                "text": "Our goal is not to assume that replacing a 1x4 cell by a 1x5 cell simply translates the reference phase diagram. Instead, we test whether the odd cell produces a surviving doublet, whether the projected inter-cell exchange is antiferromagnetic, and whether the available finite-size data require an additional phase assignment.",
            },
            {
                "kind": "heading",
                "text": "Methods",
                "level": 3,
            },
            {
                "kind": "text",
                "text": "The isolated five-spin cell was diagonalized over the complete 32-dimensional Hilbert space, with total-spin and mirror-parity labels retained. The projected low-energy basis was then used to evaluate the leading inter-cell exchange and its higher-order deviation. Longer chains were treated with finite-size DMRG and entanglement diagnostics at matched sizes. Dynamical response functions were evaluated with correction-vector DMRG and finite-temperature-evolution/TEBD pipelines using Sz=0, open boundaries, explicit t=0 inclusion and raw-spectrum diagnostics. Every production result is required to pass the variance, sector, negative-weight, checksum and independent-validator gates before entering the manuscript evidence set.",
            },
            {
                "kind": "heading",
                "text": "Results",
                "level": 3,
            },
            {
                "kind": "text",
                "text": "The isolated five-spin cell retains an S=1/2 ground-state doublet with even mirror parity throughout the sampled positive-alpha domain. This result is a local symmetry statement: it identifies the low-energy degree of freedom of one cell, but by itself it is not a phase diagram for the infinite chain.",
            },
            {
                "kind": "text",
                "text": "Projecting the inter-cell coupling onto the doublet produces a positive effective exchange. At three representative points, J_eff/beta lies between 0.4189 and 0.4396. The residual between the projected description and the two-cell spectrum scales with an exponent of approximately 1.97--1.99, while matched longer-chain DMRG gives an exponent near 1.95. These results support an antiferromagnetic effective spin-1/2 chain in the controlled weak-coupling regime, with higher local multiplets entering as the coupling is increased.",
            },
            {
                "kind": "text",
                "text": "Finite-size observables are consistent with this effective-chain picture. The extrapolated spin gap approaches zero, correlation exponents lie near 0.95--0.98, and matched-size central-charge calibrations give c=1.0240--1.0331. Independent positive-region scans at L=40, 60 and 80 show no stable sign-changing bracket that would meet the acceptance rule for an internal crossing. The response peaks near alpha approximately 0.17 and 0.30 remain continuous across the tested diagnostics. We therefore report that the present data do not support an additional phase assignment, rather than claiming that the entire thermodynamic quadrant contains only one phase.",
            },
            {
                "kind": "text",
                "text": "At alpha=0.23 and beta=0.5, an accepted eleven-point q=pi correction-vector spectrum brackets the TEBD main peak and covers the prescribed 0--1.5 frequency window under the stated finite-open-chain normalization. The shared-window relative weight difference is about 1.0%, and the two methods locate the peak at the same frequency. This is a production-level Agreement for the stated parameter point, size, momentum and normalization; it is not evidence for all momenta or all couplings.",
            },
            {
                "kind": "heading",
                "text": "Discussion",
                "level": 3,
            },
            {
                "kind": "text",
                "text": "The central result is a mechanism rather than a newly resolved phase boundary. The odd five-spin unit cell leaves a doublet that couples antiferromagnetically between cells, explaining why the low-energy finite-size trends resemble an effective c=1 chain. The local even-parity four-spin excitation remains a distinct high-energy channel in the controlled regime, so low-energy chain physics and local multiplet response should be discussed as coexisting spectral sectors rather than as two phases.",
            },
            {
                "kind": "text",
                "text": "Several boundaries are essential. The c approximately equal to 1 statement is calibrated from finite sizes and should not be presented as an unbiased thermodynamic central-charge extraction. The no-crossing statement is limited to the sampled positive-region sizes and observables. The q=pi Agreement is limited to alpha=0.23, beta=0.5, L=40 and the documented normalization. Full-momentum production data at the three representative points are still needed to decide whether the predicted momentum folding and high-energy branch assignment survive the dt/dt2 convergence gates.",
            },
            {
                "kind": "heading",
                "text": "Conclusion",
                "level": 3,
            },
            {
                "kind": "text",
                "text": "The current evidence supports a five-spin odd-unit-cell mechanism: a surviving S=1/2 doublet generates an effective antiferromagnetic chain, while local multiplet channels remain at higher energy. Finite-size scans do not require an internal positive-region crossing, and one q=pi dynamical instance passes an independent CV--TEBD Agreement gate. These findings justify writing the local mechanism, finite-size evidence and bounded dynamical result now. The final phase-level and full-momentum claims must remain provisional until the remaining six-cell full-q campaign and its dt/dt2 acceptance analysis are complete.",
            },
            {
                "kind": "heading",
                "text": "中文核对版：现在能写什么",
                "level": 2,
            },
            {
                "kind": "table",
                "columns": ["结论", "当前状态", "可否写入草稿", "边界"],
                "rows": [
                    ["奇数五聚体保留 S=1/2 双重态", "C1 可写", "可以", "单胞低能结构，不等于完整链相图"],
                    ["胞间投影交换为反铁磁", "C2/C3 可写", "可以", "弱耦合受控区；大 beta 需考虑高能混合"],
                    ["有限尺寸趋势符合 c=1 有效链", "C4 较强", "可以，需校准语气", "不能写成无偏热力学中心荷"],
                    ["正区有限尺寸未见可验收 crossing", "C5/C11 可写", "可以", "不能写成整个正区只有一个相"],
                    ["q=pi CV--TEBD Agreement", "C10 已关闭", "可以作为限定结果", "仅 alpha=0.23,beta=0.5,L=40,q=pi"],
                    ["全动量折叠和高能支", "full-q 计算中", "暂不能定稿", "等待六个生产 cell 与 dt/dt2 门"],
                ],
                "widths": ["24%", "16%", "18%", "42%"],
            },
            {
                "kind": "note",
                "label": "禁止升级的表述",
                "style": "pending",
                "text": "当前不能写“证明五聚体正区只有一个相”“发现了新相”“证明热力学无相变”或“已经完成完整全动量动力学复刻”。这些表述需要更强的热力学标度、独立序参量或全部 full-q 生产证据。",
            },
            {
                "kind": "code",
                "title": "草稿使用的证据入口",
                "text": "docs/claim_evidence_matrix.md\nresults/autoresearch_v5_20260806/round43_handoff_final_v2/handoff_summary.json\nresults/autoresearch_v5_20260806/round43_handoff_final_v2/cross_method/cross-method-check.json\nresults/research_progress/minimal_fullq_local_readiness_20260807.json\nresults/research_progress/minimal_fullq_campaign_status_20260807.json",
            },
        ],
    }


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    report["sections"] = [section()] + [item for item in report["sections"] if item.get("title") != TITLE]
    report["eyebrow"] = "RESEARCH STATUS · DRAFT ARGUMENT · BOUNDED EVIDENCE"
    report["lede"] = "1x5 Heisenberg 五聚体论文草稿与结论边界。当前可写机制和有限尺寸结果；full-q 最终动力学仍等待服务器生产验收。"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "updated", "title": TITLE}, ensure_ascii=False))


if __name__ == "__main__":
    main()
