#!/usr/bin/env python3
"""生成证据锁定的论文草稿并写入 HTML 事件源。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results" / "research_progress"
REPORT = RUN / "report.json"
STATUS = RUN / "negative_full_phase_campaign_status_20260809.json"
MARKDOWN = RUN / "manuscript_draft_20260811.md"
TITLE = "2026-08-11 论文完整草稿 · evidence-locked"


def negative_status() -> tuple[str, str]:
    if not STATUS.is_file():
        return "unknown", "负 alpha campaign 状态文件缺失。"
    data = json.loads(STATUS.read_text(encoding="utf-8"))
    state = str(data.get("status", "unknown"))
    if state in {"stage_a_r16_preparing", "stage_a_r16_running"}:
        key = "r16_repair"
    elif state in {"stage_a_r15_preparing", "stage_a_r15_running", "stage_a_blocked_final_tier"}:
        key = "r15_retry"
    elif state in {"stage_a_r14_running"}:
        key = "r14_continuation"
    elif state in {"stage_a_r13_running", "stage_a_r14_preparing"}:
        key = "r13_retry"
    elif state in {"stage_a_r12_running", "stage_a_r13_preparing"}:
        key = "r12_continuation"
    elif state == "stage_a_r12_preparing" or state.startswith("stage_a_r11"):
        key = "r11_retry"
    elif state.startswith("stage_a_r10"):
        key = "r10_retry"
    elif state.startswith("stage_a_r9"):
        key = "r9_continuation"
    else:
        key = "r8_retry"
    retry = data.get(key, {})
    snapshot = retry.get("health_snapshot", {})
    detail = (
        f"state={state}; run={retry.get('run_id', 'n/a')}; "
        f"progress={snapshot.get('completed_cells', 0)}/{snapshot.get('planned_cells', retry.get('cell_count', 1))}; "
        f"next={retry.get('next_read_window', '按 automation 读取')}"
    )
    return state, detail


def manuscript_markdown(state: str, detail: str) -> str:
    template = r"""# Manuscript draft v0.2 — evidence locked

更新时间：2026-08-11  
写入位置：研究报告，不修改 `paper/`  
计算范围：`-1 <= alpha <= 1`、`0 <= beta <= 1`；参考 Fig. 9 排除  
负区状态：`__NEGATIVE_STATE__`（__NEGATIVE_DETAIL__）

## One-sentence argument

Replacing an even tetramer by an odd pentamer reorganizes the low-energy sector of the Heisenberg cluster chain: the positive-coupling pentamer retains an effective spin-1/2 doublet with antiferromagnetic inter-cell exchange, weak virtual-process-induced frustration and momentum-selective local excitations, whereas any additional phases in the negative-alpha sector must be decided by the ongoing finite-size, multi-diagnostic campaign rather than inherited from the tetramer phase diagram.

## Provisional title

**Odd-cell spin-1/2 physics and momentum-selective excitations in a pentamer Heisenberg chain**

## Abstract

Clustered quantum magnets provide a setting in which the parity of the microscopic unit cell can reorganize the low-energy degrees of freedom. We study a spin-1/2 Heisenberg chain built from five-site units, using complete single-cell diagonalization, effective-Hamiltonian projection, finite-size density-matrix renormalization group calculations, correction-vector spectra and time-evolution cross-checks. The isolated pentamer has an even-parity spin-1/2 ground-state doublet for $\alpha>0$, an $S=3/2$ ground multiplet for $\alpha<0$, and a degeneracy at $\alpha=0$. Projecting the positive-side doublet yields an antiferromagnetic inter-cell coupling, with $J_{{\rm eff}}/\beta=0.4189$–$0.4396$ at representative points, while the leading deviations scale approximately as $\beta^2$. Second-order virtual processes generate a positive next-nearest-neighbour exchange whose controlled-edge ratio is $J_2^{{\rm eff}}/J_1^{{\rm eff}}=3.95$–$5.19\%$. Finite-size gap, correlation and entanglement diagnostics are consistent with an effective critical spin-1/2 chain, and 105 accepted positive-region records show no stable internal crossing under the stated acceptance rule. At $(\alpha,\beta)=(0.23,0.5)$ and $L=40$, correction-vector and time-evolution spectra agree at $q=\pi$; full-momentum time-evolution maps at three representative points also pass paired time-step convergence gates. These results establish an odd-cell effective-chain mechanism and momentum-selective excitation channels, but do not by themselves prove a thermodynamic single phase. **[FINAL NEGATIVE-SECTOR SENTENCE: insert only after Stages A–D pass.]**

## Introduction

Quantum spin chains with modulated exchange interactions interpolate between local cluster physics and collective many-body behaviour. In even-site cluster chains, a unit cell may form a singlet or an effective integer-spin object, enabling phase structures that include topologically trivial, Haldane-like and intermediate critical regimes [CITE: reference tetramer paper]. An odd number of spin-1/2 moments per translational unit cell changes this premise because the cell carries a half-integer low-energy degree of freedom. Subject to translation and spin-rotation symmetry, this distinction is also constrained by Lieb–Schultz–Mattis-type arguments [CITE: LSM/Oshikawa/Hastings].

Here we replace the four-site unit of the reference tetramer chain by a five-site unit while retaining the same coupling logic. The model is controlled by $\alpha=J_2/J_1$ and $\beta=J_3/J_1$, with $J_1=1$. Our purpose is not to transfer the tetramer phase labels geometrically. Instead, we ask which local multiplet survives at low energy, how neighbouring cells interact, which excitations are visible to $S^{zz}(q,\omega)$, and whether independently converged finite-size diagnostics require more than one phase in $-1\leq\alpha\leq1$ and $0\leq\beta\leq1$.

We organize the evidence in three layers. Exact diagonalization and a Schrieffer–Wolff construction identify the local degrees of freedom and induced interactions. Finite-size DMRG tests gaps, correlations, entanglement and candidate crossings. Finally, correction-vector and real-time evolution calculations test the dynamical response under independent numerical representations. This hierarchy separates robust mechanism-level conclusions from phase-boundary claims that still require the negative-alpha campaign.

## Model and methods

For $N$ five-site cells and open boundaries, we use

$$
H=\sum_{{n=1}}^N\left[J_2(\mathbf S_{{5n-4}}\cdot\mathbf S_{{5n-3}}+\mathbf S_{{5n-1}}\cdot\mathbf S_{{5n}})+J_1(\mathbf S_{{5n-3}}\cdot\mathbf S_{{5n-2}}+\mathbf S_{{5n-2}}\cdot\mathbf S_{{5n-1}})\right]+J_3\sum_{{n=1}}^{{N-1}}\mathbf S_{{5n}}\cdot\mathbf S_{{5n+1}}.
$$

The isolated pentamer was diagonalized in the complete 32-dimensional Hilbert space and classified by total spin and mirror parity. Low-energy matrix elements define $P\mathbf S_{{n,i}}P=c_i\mathbf T_n$. Two- and three-cell calculations were used to determine the first- and second-order effective interactions and to verify the perturbative residuals.

Finite chains were treated with symmetry-resolved matrix-product-state calculations in the $S^z=0$ and $S^z=1$ sectors. The positive-region evidence set contains accepted calculations at $L=40,60,80$. The full negative-alpha campaign uses two initial states, final variance per site not exceeding $10^{{-8}}$, final truncation error not exceeding $10^{{-9}}$, sector errors not exceeding $10^{{-8}}$, and independent checksum and validator gates. A phase name requires two independent diagnostics and a consistent finite-size trend; a final internal boundary additionally requires a two-standard-deviation bracket of width at most $0.025$ supported by $L=60$ and $80$.

The dynamical structure factor was evaluated by correction-vector DMRG and finite-chain real-time evolution. The accepted $q=\pi$ comparison uses $(\alpha,\beta)=(0.23,0.5)$, $L=40$, open boundaries and $S^z=0$. The full-momentum campaign used $t_{{\max}}=30$ and paired time steps $0.025$ and $0.0125$ at $(1,1)$, $(1,0.1)$ and $(0.23,0.5)$. A run entered the production set only after the $t=0$, variance, sector, raw negative-weight, checksum and independent-validator gates passed.

## Results

### 1. The local half-integer multiplet changes at alpha=0

Complete isolated-cell diagonalization gives an even-parity $S=1/2$ ground-state doublet for $\alpha>0$, an $S=3/2$ ground multiplet for $\alpha<0$, and an $S=1/2$–$S=3/2$ degeneracy at $\alpha=0$. This exact local rearrangement is a boundary control, not by itself a phase transition of the coupled chain. On the positive side, projection at $\alpha=0.14$, $0.23$ and $0.33$ gives $J_{{\rm eff}}/\beta=0.4396$, $0.4318$ and $0.4189$, respectively. The positive sign establishes an antiferromagnetic coupling between neighbouring effective spins in the controlled weak-coupling regime. The deviation of the complete two-cell spectrum from the first-order theory scales with exponents $1.9689$–$1.9915$; longer-chain estimates give $1.9483$–$1.9495$, consistent with a leading $O(\beta^2)$ correction.

### 2. Virtual excitations generate weak effective frustration

A second-order effective-Hamiltonian calculation over 100 positive-alpha points produces an antiferromagnetic next-nearest-neighbour coupling throughout the scanned interval. At the controlled edge of the perturbative regime, the resulting ratio $J_2^{{\rm eff}}/J_1^{{\rm eff}}$ is $3.95$–$5.19\%$. In an independent three-cell test, retaining this term changes the spectral-error scaling to $O(\beta^3)$, with fitted powers $3.0087$–$3.0141$; deleting it leaves powers $2.0783$–$2.1861$. This contribution is therefore measurable and mechanistically distinct, but too small on its own to establish a new frustrated phase.

### 3. Local symmetry filters the dynamical response

The lowest excited doublet has the opposite mirror parity from the ground-state doublet and carries less than $4.6\times10^{{-27}}$ spectral weight at $q=\pi$. By contrast, even-parity quartet states carry $84.1$–$97.6\%$ of the local inelastic weight at this momentum. The result is a selection rule for the single-cell response, not a direct assignment of an extended-chain quasiparticle. It nevertheless explains why local multiplet and collective effective-chain channels can occupy different parts of the spectrum.

### 4. Positive-region finite-size data support the effective-chain picture

The finite-size spin gap extrapolates towards zero, correlation exponents lie between $0.95$ and $0.98$, and matched-size entanglement calibrations give ratios equivalent to $c=1.0240$–$1.0331$. These numbers are consistent with a critical antiferromagnetic spin-1/2 chain, but the central-charge estimate is a calibrated finite-size comparison rather than an unbiased thermodynamic extraction. Across 105 accepted positive-region records, the $L=40$, $60$ and $80$ size differences do not produce a stable sign-changing bracket. Response maxima near $\alpha\simeq0.17$ and $0.30$ remain continuous across the available energy, bond, gap, correlation and entanglement diagnostics. We therefore find no accepted evidence for an internal positive-region boundary; we do not infer that the complete thermodynamic domain is necessarily a single phase.

### 5. Independent dynamical calculations agree within a bounded scope

At $(\alpha,\beta)=(0.23,0.5)$, $L=40$ and $q=\pi$, an 11-point correction-vector grid brackets the main time-evolution peak and covers the prescribed $0\leq\omega\leq1.5$ interval. Both methods place the shared-grid maximum at $\omega=0.05$, and their shared-window integrated weights differ by $1.04\%$. The full-momentum time-evolution campaign passes all six single-run validators and all three paired time-step checks. The largest global or $q=\pi$ peak drift is $0.01J_1$, and the low-frequency integrated-weight drift is at most $4.32\times10^{{-5}}$. These tests establish numerical convergence for the stated finite systems; the identification of individual high-energy branches remains tied to the local symmetry and effective-theory evidence rather than to line shape alone.

### 6. Negative-alpha phase structure — pending evidence

**[PLACEHOLDER — DO NOT CONVERT TO A PHASE CLAIM.]** The strict negative-alpha campaign is still running. Until Stages A–D pass, the report may show exploratory momentum redistribution but must not state a phase count, name a negative-alpha phase, or draw a thermodynamic boundary. The final paragraph must report accepted $L=40,60,80$ trends, two-diagnostic agreement, boundary brackets and initial-state sensitivity. In particular, the recorded $R_\pi$ half-difference $0.0118775$ at $\alpha=-0.10$, $\beta=0.5$, $L=40$ remains a systematic uncertainty and cannot be used as high-precision boundary evidence.

## Discussion

The principal physical difference from the reference tetramer chain is the parity of the unit cell. Four spin-1/2 moments can form a singlet or an effective integer-spin object, allowing the reference work to distinguish trivial tetramer, Haldane-like and intermediate critical regimes. Five spin-1/2 moments instead leave a half-integer doublet in the positive-coupling local problem. The observed antiferromagnetic projection, near-$c=1$ finite-size trends and momentum filtering are therefore not a mere horizontal shift of the tetramer phase diagram.

Our strongest current contribution is a connected mechanism: the local doublet defines the collective low-energy chain; virtual processes add weak antiferromagnetic frustration; mirror parity suppresses the lowest local doublet at $q=\pi$ and transfers local inelastic weight to quartet states; and independently converged spectra connect these ingredients to the finite chain. Rival interpretations remain possible. The absence of an accepted crossing may reflect a common critical regime, but it could also reflect finite sizes or insensitive observables. A momentum shift in the negative-alpha sector could be a crossover or Lifshitz-like line rather than a distinct thermodynamic phase. These alternatives are why the negative-alpha controller requires non-analytic finite-size evidence beyond $q_{{\rm peak}}$ alone.

The present study has three explicit limitations. First, the positive-region central-charge evidence is calibrated at matched finite sizes. Second, the correction-vector/time-evolution Agreement is restricted to one parameter point, one size and $q=\pi$, although the full-momentum time-step convergence covers three representative points. Third, the complete negative-alpha phase map is not yet accepted. The last limitation affects the final phase count and the phase-diagram figure, but it does not invalidate the local spectrum, effective-Hamiltonian or positive-region dynamical conclusions.

## Conclusion

We have established that the five-site unit changes the organizing principle of the modulated Heisenberg chain. In the non-negative-coupling sector, a surviving $S=1/2$ doublet generates an antiferromagnetic effective chain, second-order processes add weak frustration, and local mirror symmetry produces a strong momentum-dependent selection rule. Finite-size ground-state and dynamical calculations support this mechanism under explicit convergence and validation gates. **[FINAL PHASE-MAP CONCLUSION: add only after the negative-alpha campaign reaches an accepted terminal state.]**

## Terminology ledger

| Preferred term | Use | Avoid |
|---|---|---|
| pentamer / five-site unit | Current microscopic cell | tetramer used for the present model |
| effective spin-1/2 doublet | Projected low-energy cell state | “free spin” without qualification |
| momentum redistribution | Change of dominant $q$ without non-analytic evidence | new phase / phase boundary |
| finite-size no-crossing result | Accepted positive-region statement | proof of a single thermodynamic phase |
| Agreement at the stated instance | CV–TEBD result at one point | universal method agreement |
| quartet channel | Local $S=3/2$ multiplet contribution | tetramer quasiparticle names |

## Claim–evidence map

| Claim | Evidence | Status |
|---|---|---|
| Local multiplet changes from $S=3/2$ to $S=1/2$ at $\alpha=0$ | 101-point complete 32-state ED | Writeable as a cell-level boundary control |
| $J_{{\rm eff}}>0$ | Three representative projections | Writeable in weak-coupling scope |
| Leading correction is $O(\beta^2)$ | Two-cell ED and $N=8,12,16$ DMRG exponents | Writeable |
| Weak induced AFM $J_2$ | 100-point second-order construction | Writeable as mechanism, not phase |
| $q=\pi$ filters lowest excited doublet | Parity-resolved local spectral weights | Writeable |
| Positive finite-size data show no accepted internal crossing | 105 accepted records, $L=40,60,80$ | Writeable with finite-size qualifier |
| CV and TEBD agree | accepted11 cross-check at $(0.23,0.5),L=40,q=\pi$ | Writeable only at stated instance |
| Full-$q$ maps are time-step converged | Six accepted runs, three paired checks | Writeable as numerical validation |
| Number and names of negative-alpha phases | Stage A–D campaign | Pending; prohibited now |

## Citation placeholders

- [CITE: Li et al., *Spin order and spin excitation spectra of spin-1/2 tetramer chains*, npj Quantum Materials 11, 37 (2026).]
- [CITE: Lieb–Schultz–Mattis and higher-dimensional/generalized constraints.]
- [CITE: DMRG/MPS method references.]
- [CITE: correction-vector DMRG and TEBD method references.]
- [CITE: spin-1/2 Heisenberg-chain continuum and $c=1$ field theory.]
"""
    return template.replace("__NEGATIVE_STATE__", state).replace("__NEGATIVE_DETAIL__", detail)


def section(state: str, detail: str) -> dict:
    return {
        "title": TITLE,
        "note": "完整英文结构已建立；正区与动力学只使用已验收证据，负 alpha 段保留显式占位符；不修改 paper/。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "完整草稿骨架已可读 · 最终相图结论仍等待负区 campaign",
                "why": "full-q 六个 run 和三组 dt/dt2 已 production-ready；负区尚未完成 Stage A–D，因此相数、相名和边界保持空缺。",
            },
            {"kind": "kv", "pairs": [
                ["草稿版本", "v0.2 evidence-locked · 2026-08-11"],
                ["覆盖章节", "Title / Abstract / Introduction / Model and methods / Results / Discussion / Conclusion"],
                ["计算范围", "-1<=alpha<=1, 0<=beta<=1；Fig.9 排除"],
                ["负区实时状态", detail],
                ["独立文本", "manuscript_draft_20260811.md"],
                ["写入边界", "仅 results/research_progress；paper/ 未修改"],
            ]},
            {"kind": "heading", "text": "One-sentence argument", "level": 2},
            {"kind": "text", "text": "Replacing an even tetramer by an odd pentamer reorganizes the low-energy sector of the Heisenberg cluster chain: the positive-coupling pentamer retains an effective spin-1/2 doublet with antiferromagnetic inter-cell exchange, weak virtual-process-induced frustration and momentum-selective local excitations, whereas any additional phases in the negative-alpha sector must be decided by the ongoing finite-size, multi-diagnostic campaign rather than inherited from the tetramer phase diagram."},
            {"kind": "heading", "text": "Provisional title", "level": 2},
            {"kind": "text", "text": "Odd-cell spin-1/2 physics and momentum-selective excitations in a pentamer Heisenberg chain"},
            {"kind": "heading", "text": "Abstract · working version", "level": 2},
            {"kind": "text", "text": "Clustered quantum magnets provide a setting in which unit-cell parity can reorganize the low-energy degrees of freedom. Complete isolated-cell diagonalization gives an even-parity S=1/2 ground-state doublet for alpha>0, an S=3/2 ground multiplet for alpha<0, and a degeneracy at alpha=0. Projecting the positive-side doublet yields J_eff/beta=0.4189–0.4396 at representative points, while second-order virtual processes generate a weak antiferromagnetic next-nearest-neighbour exchange. Finite-size diagnostics are consistent with an effective critical spin-1/2 chain, and 105 accepted positive-region records show no stable internal crossing under the stated rule. At (alpha,beta)=(0.23,0.5), L=40 and q=pi, correction-vector and time-evolution spectra agree; full-momentum maps at three representative points also pass paired time-step convergence gates. These results establish a local-multiplet and effective-chain mechanism, but do not by themselves prove a thermodynamic phase diagram. [Final negative-sector sentence pending Stages A–D.]"},
            {"kind": "heading", "text": "Results draft · evidence first", "level": 2},
            {"kind": "card", "title": "1 · Local multiplet switch and positive-side effective exchange", "blocks": [
                {"kind": "text", "text": "The isolated pentamer has S=1/2 for alpha>0, S=3/2 for alpha<0, and an exact degeneracy at alpha=0. This is a local boundary control, not a coupled-chain phase transition. On the positive side, projection at alpha=0.14, 0.23 and 0.33 gives J_eff/beta=0.4396, 0.4318 and 0.4189, establishing antiferromagnetic coupling in the controlled weak-coupling regime."},
            ]},
            {"kind": "card", "title": "2 · Weak virtual-process-induced frustration", "blocks": [
                {"kind": "text", "text": "A second-order construction over 100 positive-alpha points produces an antiferromagnetic next-nearest-neighbour coupling throughout the scan. At the controlled perturbative edge, J2_eff/J1_eff=3.95–5.19%. A three-cell validation changes the fitted spectral-error power to 3.0087–3.0141 when this term is retained, versus 2.0783–2.1861 when it is deleted. This is a quantitative correction, not evidence for a new phase by itself."},
            ]},
            {"kind": "card", "title": "3 · Momentum-selective local multiplets", "blocks": [
                {"kind": "text", "text": "The lowest excited doublet has the opposite mirror parity and less than 4.6e-27 weight at q=pi, whereas quartet states carry 84.1–97.6% of the local inelastic weight. This is a local selection rule and must not be relabelled with tetramer-specific quasiparticle names."},
            ]},
            {"kind": "card", "title": "4 · Positive-region finite-size result", "blocks": [
                {"kind": "text", "text": "The spin gap trends towards zero, correlation exponents lie at 0.95–0.98, and matched-size entanglement calibrations give c=1.0240–1.0331. Across 105 accepted records, L=40/60/80 differences show no stable sign-changing bracket. The supported statement is finite-size no-crossing evidence, not proof of one thermodynamic phase."},
            ]},
            {"kind": "card", "title": "5 · Dynamical cross-check and full-q convergence", "blocks": [
                {"kind": "text", "text": "At alpha=0.23, beta=0.5, L=40 and q=pi, the accepted11 CV grid and TEBD share a peak at omega=0.05 and differ by 1.04% in shared-window weight. Six full-q runs at three points pass all validators and paired time-step checks; the maximum peak drift is 0.01 J1 and the maximum low-frequency weight drift is 4.32e-5."},
            ]},
            {"kind": "note", "label": "6 · Negative-alpha results placeholder", "style": "pending", "text": "Stage A–D 尚未完成。现在不得写相数、相名或热力学边界。Rpi 双初态半差 0.0118775 必须作为系统误差持续保留。"},
            {"kind": "heading", "text": "Claim–evidence map", "level": 2},
            {"kind": "table", "columns": ["主张", "证据", "稿件状态", "边界"], "rows": [
                ["alpha=0 两侧局域多重态 S=3/2 与 S=1/2 切换", "101-point complete ED", "可写", "单胞边界控制，不是链相变"],
                ["反铁磁 J_eff", "3 representative projections", "可写", "弱耦合受控区"],
                ["首修正 O(beta^2)", "two-cell ED + longer-chain exponents", "可写", "大 beta 不外推"],
                ["弱 AFM 有效 J2", "100-point second-order construction", "可写", "机制，不是相"],
                ["q=pi 宇称过滤", "parity-resolved local weights", "可写", "局域选择定则"],
                ["正区未见 accepted crossing", "105 records, L=40/60/80", "可写", "有限尺寸否定结果"],
                ["CV–TEBD Agreement", "accepted11 at one instance", "可写", "仅当前 alpha,beta,L,q"],
                ["full-q 数值收敛", "6 runs + 3 dt pairs", "可写", "不自动等价于谱支命名"],
                ["负区相数与相界", "Stage A–D", "禁止", "等待完整验收"],
            ], "widths": ["25%", "30%", "14%", "31%"]},
            {"kind": "heading", "text": "Discussion · 核心解释与竞争解释", "level": 2},
            {"kind": "text", "text": "The principal difference from the reference tetramer chain is unit-cell parity. Four spin-1/2 moments can form singlet or effective integer-spin sectors; five moments leave a half-integer doublet in the positive-coupling local problem. The resulting antiferromagnetic projection, weak induced frustration and momentum filtering are therefore structural consequences of the pentamer rather than a shifted copy of the tetramer phase diagram."},
            {"kind": "text", "text": "The absence of an accepted positive-region crossing may indicate a common critical regime, but finite sizes and observable sensitivity remain rival explanations. Likewise, a negative-alpha momentum shift may be a crossover or Lifshitz-like line rather than a distinct phase. The final phase map therefore requires non-analytic finite-size evidence from at least two diagnostics."},
            {"kind": "heading", "text": "Methods and conclusion status", "level": 2},
            {"kind": "table", "columns": ["章节", "完成度", "还缺什么"], "rows": [
                ["Title / argument", "可审阅", "根据最终相图决定是否加入 phase-diagram 词语"],
                ["Introduction", "完整初稿", "补正式文献引用"],
                ["Model and methods", "完整初稿", "最终统一 DMRG 参数表与软件版本"],
                ["Results 1–5", "证据锁定", "图号和交叉引用排版"],
                ["Results 6", "占位符", "负区 Stage A–D accepted-only 结果"],
                ["Discussion", "完整初稿", "根据最终负区相数收束竞争解释"],
                ["Abstract / Conclusion", "条件初稿", "替换负区占位句"],
                ["References", "仅占位", "正式 BibTeX 与逐句引用"],
            ], "widths": ["22%", "20%", "58%"]},
            {"kind": "note", "label": "明确禁止升级", "style": "pending", "text": "在负区 Stage A–D 完成前，不得写“完整相图已完成”“发现 N 个相”“证明相变点”或“完美复刻参考论文”。"},
            {"kind": "code", "title": "主要证据入口", "text": "docs/claim_evidence_matrix.md\ndocs/effective_chain_mechanism_20260729.md\nresults/autoresearch_v5_20260731/round14_schrieffer_wolff/summary.json\nresults/autoresearch_v5_20260806/round43_handoff_final_v2/handoff_summary.json\nresults/autoresearch_v5_20260806/round43_handoff_final_v2/cross_method/cross-method-check.json\nresults/autoresearch_v5_20260807/minimal_fullq_handoff_eta020_20260808_1533/handoff_summary.json\nresults/research_progress/negative_full_phase_campaign_status_20260809.json"},
        ],
    }


def main() -> None:
    state, detail = negative_status()
    MARKDOWN.write_text(manuscript_markdown(state, detail), encoding="utf-8")
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    report["sections"] = [section(state, detail)] + [
        item for item in report["sections"] if item.get("title") != TITLE
    ]
    report["eyebrow"] = "FULL MANUSCRIPT DRAFT · EVIDENCE LOCKED · NEGATIVE SECTOR PENDING"
    report["lede"] = "1×5 Heisenberg 五聚体链完整论文草稿已建立；正区机制与动力学使用验收证据，负 alpha 相图结论等待 Stage A–D。"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "updated", "title": TITLE, "markdown": str(MARKDOWN), "negative_state": state}, ensure_ascii=False))


if __name__ == "__main__":
    main()
