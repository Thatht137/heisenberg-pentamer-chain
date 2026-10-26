# Manuscript claim–evidence map（2026-09-20）

> 用途：给 `docs/near_final_manuscript_draft_20260819.md` 做本地证据与引用缺口盘点。本文档只整理已经存在的本地记录，不替代 `paper/`，不把准备态写成服务器结果。
>

## 1. 总体论点与范围锁定

当前工作标题已收敛为 **From local pentamer multiplets to collective spin dynamics in an odd-unit-cell Heisenberg chain**。含 `criticality` 的三个标题保留为候选，但须等完整链证据，不能把标题候选当作物理结论。

正文的一句话主张应保持为：

> 在已测试的正 `alpha` 点，孤立五聚体保留偶宇称有效 spin-1/2 doublet，正胞间耦合支持反铁磁 effective-chain 描述；有限尺寸数据与 `c=1` oracle 一致但不单独证明全局无隙 `c=1` phase。局部 reflection parity 选择动力学通道；负 `alpha` 只报告 finite-size momentum reconstruction，并把 crossover 保留为 working interpretation，不命名新的热力学相。

这条主张有三个不可合并的范围：

1. **正 `alpha`**：可以谈 tested positive-alpha points、孤立单胞 doublet、有效链和局部动力学选择定则；不可开篇泛称全参数区为 doublet phase。
2. **负 `alpha`**：可以谈 accepted finite-size momentum reconstruction 和 crossover working interpretation；不能写成已经确认的第二相或相界。
3. **近零 `alpha` 机制**：是 `|alpha| << min(1,beta)` 下的局部解析候选加 8-spin oracle 核对；不能升级为完整 OBC 链或热力学证明。

## 2. Claim → evidence → status → gap

状态含义：`supported` 表示当前本地证据足以按限定语写入；`qualified` 表示可以写观察结果但必须附边界；`open` 表示不能在正文中作已完成结论；`blocked` 表示仅有准备态或缺少上传/启动回执。

| ID | 可写 claim（建议措辞） | 直接本地证据 | 状态 | 必须保留的边界 / 缺口 |
|---|---|---|---|---|
| C1 | 在已扫描的 `0<alpha<=1` 孤立五聚体点，基态是偶反射宇称 `S=1/2` doublet；最低激发 doublet 为奇宇称，最低 quartet 为偶宇称。 | `docs/claim_evidence_matrix.md` C1/C6/C7；`docs/effective_chain_mechanism_20260729.md` 的单胞 ED、投影与 selection-rule 段；`figures/single_pentamer_low_energy_multiplets.png`；`figures/positive_local_spectral_channels_20260730.png`；对应 `.sources.json`。 | supported（限定为 isolated pentamer / tested positive-alpha） | 这是单胞低能空间，不是完整链 phase map；不要写“整个区域都是 doublet phase”。 |
| C2 | 正胞间耦合在测试区投影为反铁磁 effective spin-1/2 chain；代表点 `J_eff/beta=0.4396, 0.4318, 0.4189` 均为正。 | `docs/effective_chain_mechanism_20260729.md`；`paper/sections/results.tex` 现有数字记录；`docs/claim_evidence_matrix.md` C2。 | supported（tested points） | 一阶投影在 `beta/Delta_loc` 足够小时受控；不能由正的局部投影直接推出所有 `beta` 的全链相结构。 |
| C3 | 投影能量相对精确结果的首个系统修正与 `O(beta^2)` 一致。 | `docs/effective_chain_mechanism_20260729.md`；`docs/claim_evidence_matrix.md` C3；两胞 ED 残差幂 `1.9689–1.9915`，`N=8,12,16` 完整五聚体链记录 `1.9483–1.9495`。 | supported（有限尺寸 / 已测路径） | 不是任意强耦合下的误差界；高能多重态混合在大 `beta` 处仍是边界。 |
| C4 | 正区有限链数据与反铁磁 `c=1` effective-chain 图景一致。 | `results/autoresearch_v4_20260730/round1_entanglement_scaling/analysis/claim_summary.json`（positive pentamer 与 matched-size Heisenberg oracle，校准比值 `1.0240–1.0331`）；`results/autoresearch_v5_20260731/round12_effective_gap_scaling/summary.json`（正区有效 gap scaling 的受控/失控范围）；`docs/claim_evidence_matrix.md` C4；`figures/entanglement_spectrum_b0.5_L80.png` 等正区本地图。 | qualified | `claim_summary.gates.raw_log_fit_quality=false`，所以只能写 calibrated finite-size consistency；不能写无偏热力学 central charge。该 C4 不使用负 `alpha` 的 `closeout_stage1_*` summary；`global c=1` 与 `second phase` 仍未证明。 |
| C5 | 正区 105 条 accepted finite-size records 未产生可验收内部 crossing。 | `docs/claim_evidence_matrix.md` C11；`paper/sections/results.tex`；draft §3.2。 | supported as bounded negative result | 这否定的是“当前证据足以定义内部边界”，不证明整个二维正区是单相，也不证明全局 criticality。 |
| C6 | 反射宇称使最低奇宇称 doublet 在 `q=pi` 的单自旋响应中变暗；局部 `S=3/2` multiplets 承担主要非弹性权重。 | `docs/effective_chain_mechanism_20260729.md`：最低 doublet 权重 `<4.6e-27`，所有 quartet 合计 `84.1%–97.6%`；`figures/positive_local_spectral_channels_20260730.png`；`figures/pentamer_momentum_filter_20260731.png`；`docs/claim_evidence_matrix.md` C6/C7。 | supported（isolated-pentamer local response） | 这是 `S^z(q)` 的单自旋直接跃迁选择定则；有限 `beta` 长链色散和混合仍不能由局部权重直接替代。 |
| C7 | correction-vector 与 real-time MPS 在指定代表点的一致性支持动力学实现的交叉检查。 | final-v2 accepted-11 证据：`figures/round43_fig8_final_20260806_v2.sources.json`、`.source.csv`、`.png`；`results/autoresearch_v5_20260806/round43_handoff_final_v2/handoff_summary.json`；`cross_method/cross-method-check.json`；`accepted11/manifest.json`。独立 full-q 证据：`results/autoresearch_v5_20260807/minimal_fullq_handoff_eta020_20260808_1533/handoff_summary.json` 及其六个 per-point manifests/cross-checks。 | supported（bounded pointwise / method claim） | final-v2 的 CV–TEBD 配对只限历史 `q=pi` slice、`eta=0.1`、stored raw/pi 与 `center` source/37-site window 的有限 OBC 归一化与空间窗近似；old bounded 图只能作为失败历史，不能证明 accepted-11。独立 full-q 三点均通过 paired `dt=0.025/0.0125`：uniform `(1,1)` 的 manifest `window_eta=0.1`，weak `(1,0.1)` 与 agreement `(0.23,0.5)` 为 `window_eta=0.2`，均 `space_window=18`；不能把 full-q 结果写成 CV 已验收，也不能外推任意动量、尺寸或新相。 |
| C8 | 负 `alpha` accepted large-size records 展示主导动量约从 `0.60pi` 向 `pi` 重构。 | `figures/negative_practical_v2_crossover_20260913/negative_alpha_crossover_evidence.csv`；同目录 `negative_alpha_crossover_summary.png`、`.qa.json`；`docs/article_closeout_checklist_20260819.md`；draft §3.5。 | qualified | 是 finite-size momentum reconstruction；八个 candidate intervals 没有同时通过 momentum 与 dominant-ratio 条件，因此只保留 crossover working interpretation，不命名新相/二相界。 |
| C9 | 负 `alpha` 的 entropy/correlation anomaly 仍需 observable-level convergence，不能单独作相判断。 | `results/autoresearch_v5_20260919/closeout_stage1_joint_v2/summary.json`；`results/autoresearch_v5_20260919/closeout_stage1_reanalysis_v2/summary.json`；draft `Current closeout limitation`。 | qualified / open | `phase_assigned=false`；单尺寸条目不能建立 scaling；区间不是 confidence interval；small connected correlations 和无负 gap 也不是独立相变排除。 |
| C10 | 近零极限给出候选局部机制：当 `J1=1`、`beta>0`、`|alpha| << min(1,beta)` 时，trimer projection 与 dimer 消去产生 `J_eff=2alpha^2/(9beta)>0`。 | `docs/near_zero_alpha_mechanism_note_20260919.md` §1–§4：`(2/3,-1/3,2/3)` 投影系数、`g=2alpha/3`、二阶 cross term、形状因子和 OBC edge 分析。 | supported as controlled local derivation | 这是候选受控极限，不是完整链 phase statement；两个极限不可交换；OBC edge gap 可能主导有限链 `Sz` gap，不能当 bulk gap。 |
| C11 | 8-spin trimer–dimer–trimer oracle 核对了上述局部交换极限的有限点一致性。 | `results/autoresearch_v5_20260919/near_zero_alpha_oracle_v2/summary.json`、`oracle_points.csv`、`checksums.sha256`；`results/autoresearch_v5_20260919/near_zero_alpha_mechanism_report_v2/report.json`。47 点、11 项 gates 通过；NumPy bit-sector 与 full-Kronecker 是同一 Hamiltonian 的双实现。 | supported as local oracle only | 8-spin `[1,1,alpha,beta,alpha,1,1]` 不是两个完整五聚体，也不是完整 OBC chain validation；双实现不是独立多体方法；不能据此作 thermodynamic claim。 |
| C12 | 两个 finite-`alpha` controls 对 leading exchange 的偏差应精确描述为相对 leading prediction 的偏差。 | `near_zero_alpha_oracle_v2/summary.json` 的 `prediction_relative_error`；`oracle_points.csv` 的 `gap_over_alpha2` 与 `predicted_gap_over_alpha2`。 | qualified | 定义为 `epsilon=(gap/alpha^2 - 2/(9beta))/(2/(9beta))`：`(-0.10,0.25)` 为 `-36.1351%`，`(-0.175,0.25)` 为 `-53.8550%`。它们不是“ED 相对自身的误差”，也不是 L80 数值误差；`finite_alpha_control` 不套 2% asymptotic gate。 |
| C13 | 两个 L80 `Krylov-8` control 已通过 Practical V2 数值门、文件完整性与 validator；`comparison` 仅作 `audit_only`。新 gap 在 `alpha=-0.10` 为 `7.277203948e-5` / `7.277205361e-5`，在 `alpha=-0.175` 为 `1.587107409e-4` / `1.587107429e-4`（`center` / `ferro_j2` 的 `Sz=0` 初态）。 | `results/research_progress/project_closeout_status_20260919.json`：`stage3.status=numerical_done_physics_stability_not_claimed`、`candidate_present=true`、`candidate_validated=true`、`remote_julia_started=true`、`terminal_state=terminal_success_validated`；`results/autoresearch_v5_20260920/static_krylov_controls_r2_comparison_20260920/comparison.json`（`status=audit_only`、`claim=none`、两点各 `324` records）；`results/autoresearch_v5_20260920/static_krylov_controls_r2_comparison_20260920/comparison_summary_20260920.json`；`results/autoresearch_v5_20260920/static_krylov_baseline_v3/repair_provenance_20260920.json`；`results/autoresearch_v5_20260920/static_krylov_controls_r2_fetch_0945/validation_negdiag-a01000-b02500-L080-k08.json`；`results/autoresearch_v5_20260920/static_krylov_controls_r2_fetch_0945/validation_negdiag-a01750-b02500-L080-k08.json`。 | qualified（numerically validated control; physics stability not claimed） | 相对旧 `k=3` gap 的对称相对差 `2(new-old)/(|new|+|old|)` 为 `31.59%/43.80%` 与 `2.06%/4.57%`；最大逐 bond entropy 对称相对差为 `41.03%/53.16%` 与 `2.99%/6.69%`。`k` 是 Krylov dimension，不是 `chi`；`Sz=0` 的两个初态用于初始化检查，`Sz=1` 固定 `center`，不当统计独立重复。不能把 `k=3` 的 `L=40,60` 与 `k=8` 的 `L=80` 混作最终 scaling，也不能据此宣称全部观测量收敛、新相或全域单相。初次 launcher 的 CRLF 失败与此前兼容脚本授权阻塞仅保留为历史上下文。 |

`static_krylov_impact_v2` 的补充审计显示，在 period=10、window=0.20 下，effective slope 从 `0.582205/0.484120` 修正为 `0.932465/0.932465`（alpha=-0.10），从 `0.932218/0.900914` 修正为 `0.959897/0.959897`（alpha=-0.175），顺序均为 `center/ferro_j2`。这表明 solver sensitivity，不能解释为 thermodynamic central charge 或 confidence interval。两点的 k3/k8 端点 `q_peak` 仍分别保持 `pi`（alpha=-0.10）和 `0.6pi`（alpha=-0.175），但 dominant ratio 发生变化，因此仍只保留 finite-size momentum reconstruction，不升级为 phase claim。证据：`results/autoresearch_v5_20260920/static_krylov_impact_v2/summary.json` 与 `results/autoresearch_v5_20260920/static_krylov_impact_v2/entropy_fit_comparison.csv`。

## 3. 近零机制的最小正文段（可放 Discussion，带边界）

可保留下面这段作为机制结果的短段，而不是把它写成相图结论：

> In the controlled regime `|alpha| << min(1,beta)`, the `alpha=0` starting point consists of a trimer doublet coupled through an inter-cell dimer singlet. Projecting the trimer gives `(2/3,-1/3,2/3)`, and eliminating the dimer triplet at second order gives the candidate bulk exchange `J_eff=2 alpha^2/(9 beta)>0`. The 8-spin trimer–dimer–trimer oracle reproduces this local scaling over the registered small-`|alpha|` points. The two finite-`alpha` controls have `epsilon=-36.1351%` and `-53.8550%`, where `epsilon` is the signed deviation from the leading `J_eff` prediction defined above; they are not L80 errors. Because open-boundary edge terms enter at `O(alpha)` while the mediated bulk exchange is `O(alpha^2/beta)`, an OBC sector gap need not equal a bulk gap. This is therefore a local controlled-mechanism result, not evidence for a global `c=1` phase or a second thermodynamic phase.

证据来源：`docs/near_zero_alpha_mechanism_note_20260919.md`、`results/autoresearch_v5_20260919/near_zero_alpha_oracle_v2/summary.json`、`results/autoresearch_v5_20260919/near_zero_alpha_mechanism_report_v2/report.json`。

## 4. 方法措辞与数值范围检查

| 主题 | 允许写法 | 禁止 / 尚未证明 |
|---|---|---|
| `64 sweeps` | “new Practical V2 cells use a cap of at most 64 sweeps” | 不得说全部历史数据都是 64 sweeps；旧结果和新 cap 必须分开。 |
| `L80 k=8` | “two points passed Practical V2 and file/validator checks; candidate present and validated; `3→8` comparison is `audit_only`” | 不得把数值门通过写成全部观测量收敛、相结论或最终 scaling；`k` 不等于 `chi`，不能混合 `k=3` 的 `L=40,60` 与 `k=8` 的 `L=80`。 |
| bond dimension | “preflight observed maxlinkdim below configured 1200; convergence remains open” | 不得把 `189–290<1200` 叫作 bond-dimension convergence；不得把它写成 `chi` series。 |
| initial states | `Sz=0` 有 center / ferro_j2 两初态记录；`Sz=1` 固定 `center` | 不得将两个 sector 的 gap 差当成两个独立统计样本。 |
| 96 parameter–size records at 48 coupling points | “evaluated: 89 accepted + 7 bounded” | 不得写 “96 resolved” 以免暗示 96 个都通过；96 是参数–尺寸 records，不是 96 个不同耦合点。 |
| 8-spin oracle | “local controlled exchange check” | 不得称完整链验证、第二种独立多体方法或热力学相判断。 |
| candidate fields | 当前 `candidate_present=true` 且 `candidate_validated=true`，但 comparison 仍为 `audit_only` | candidate 验证表示数值与完整性验收通过，不推出全部观测量收敛、相或全域单相；不得把 `k` 当作 `chi`。 |

## 5. 引用 / P3 缺口清单

当前 `paper/bibliography.bib` 仍只有 `li2026tetramer`（临时元数据）和 `descloizeaux1962` 两项；但 `mechanism_report` 已提供并核验 `docs/pentamer_bibliography_verified_20260919.bib` 与 `docs/pentamer_citation_audit_20260919.json`（12/12 verified）。本轮已把 12 个 scope-limited citation keys 接入本地 draft 的引言、方法、机制段和 verified reference ledger；`paper/` 级同步仍刻意未做。因此 P3 对本地 draft 为 `verified_and_integrated`，对最终 paper 为 `paper_sync_pending`。`.bib` 文件存在本身不等于引用已核验或已接入正文。

| 文献角色 | 当前状态 | 可接受的下一步 |
|---|---|---|
| 五聚体 / tetramer 背景 | `@li2026tetramer_verified` 已核验并已接入 draft；原 `paper/bibliography.bib` 临时条目保留未改 | paper-level bibliography/citation sync 待单独授权；不能把 tetramer 结果当五聚体证据。 |
| isolated-pentamer cluster context | `@haraldsen2011` 已核验并已接入 draft，但 audit 标记 geometry 未完成全文逐项比对 | 只作一般团簇背景；不声称与本项目 all-spin-1/2 OBC 几何相同。 |
| trimer doublet → effective spin-1/2 一般背景 | `@cheng2022trimer` 已核验并已接入机制段 | 该文不能替代本项目具体 `(2/3,-1/3,2/3)` 和二阶系数推导。 |
| half-integer / LSM 逻辑边界 | `@lieb1961`、`@ogata2019` 已核验并已接入引言 | 只用于逻辑边界，不支撑全域 `c=1` 或本文有限尺寸 gap。 |
| entanglement / Heisenberg-chain oracle | `@calabrese2004`、`@descloizeaux1962_verified` 已核验并已接入摘要/引言 | 只支撑理论或 oracle 背景；本地 calibrated finite-size evidence 仍由数据文件支撑。 |
| DMRG/MPS/TEBD/correction-vector | `@white1992`、`@schollwoeck2011`、`@vidal2004`、`@kuehner1999`、`@fishman2022` 已核验并已接入方法段 | 方法文献不替代本项目 residual、dt/dt2、validator 或 L80 收敛证据。 |

已接入的 citation 仅来自 verified `.bib` / audit；没有把候选 URL 当作引用，也没有伪造 DOI。P3 的 draft-level pass 已完成，但最终 `paper/` 同步仍未完成。

## 6. 术语表（正文统一）

| 统一术语 | 含义与用法 |
|---|---|
| `tested positive-alpha points` | 只指当前已测的正 `alpha` 点；不能缩写成整个参数平面。 |
| `isolated-pentamer ground-state doublet` | 孤立五聚体的局部 `S=1/2`、偶宇称基态；不能直接替代全链相名。 |
| `spin-3/2 multiplet` / `quartet` | 局部多重态；只有在局部谱权语境中讨论其权重。 |
| `reflection parity` / `q=pi` | 局部选择定则的对称性和动量通道。 |
| `effective spin-1/2 chain` | 正胞间耦合的低能投影描述；注明 tested / controlled regime。 |
| `negative-alpha finite-size momentum reconstruction` | 负 `alpha` 的观测结果；优先于“negative phase”。 |
| `crossover (working interpretation)` | 负区的暂定解释；不是 confirmed phase boundary。 |
| `8-spin trimer-dimer-trimer oracle` | `[1,1,alpha,beta,alpha,1,1]` 的局部 ED 核对；不是完整链。 |
| `OBC sector gap` 与 `bulk gap` | 明确区分；边缘 `O(alpha)` 项可使前者边界主导。 |
| `candidate_present` / `candidate_validated` | 当前两个字段均为 `true`；分别表示候选存在与数值/完整性验收通过，不推出全部观测量收敛或物理相结论。 |
| `global c=1 not established` / `second phase not established` | 当前必须保留的否定边界。 |
| `L80 Krylov-8 candidate validated / comparison audit_only / physics stability not claimed` | 当前 Stage 3 的准确状态；保留初次 CRLF launcher 与此前授权阻塞作为历史注，不将 `audit_only` 升级为相或最终 scaling 结论。 |

## 7. 本轮文件与后续门

- 已更新的独占底稿：`docs/near_final_manuscript_draft_20260819.md`。改动包括保守工作标题、正 `alpha` 限定、`96 parameter–size records at 48 coupling points (89 accepted, 7 bounded)`、近零机制短段、`64 sweeps` 范围声明、当前两点 L80 `k=8` 数值验收与 `audit_only` 边界；初次 CRLF launcher 失败及此前兼容脚本授权阻塞仅作历史注，未修改 `paper/`。
- 本 map：`docs/manuscript_claim_evidence_map_20260919.md`。
- 独立 manuscript closeout report 将写入 `results/autoresearch_v5_20260919/manuscript_closeout_20260919_report/report.json` 并单独渲染；不会更新主 report。
- Stage 4 当前为 `writing_in_progress`；本地 draft、claim map、verified citation pass 和独立 report 已完成，但科学门仍 open。Stage 3 当前为 `numerical_done_physics_stability_not_claimed`：candidate 与 validator 已通过，comparison 保持 `audit_only`，不能升级为全部观测量收敛或相结论。
- 本地 draft 的 P3 已按核验 `.bib` 与 audit 完成引用接入；仍需作者决定是否把相同 keys 同步到 `paper/`。Stage 3 当前状态以 `results/research_progress/project_closeout_status_20260919.json`、r2 comparison、baseline-v3 repair provenance 与两份 r2-fetch validator 为准；历史 CRLF/授权阻塞不再代表当前 candidate 状态。
