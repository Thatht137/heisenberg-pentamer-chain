# Post-Krylov claim audit（2026-09-20）

本文件记录 L80 Krylov-8 结果的证据审计。

## 已验证

- L80 compatibility release 已完成远端运行；terminal snapshot 记录 supervisor 正常结束、returncode=0、2 个 cell/4 个子任务完成、checksums 通过且无活动进程：
  `results/autoresearch_v5_20260919/static_krylov_controls_release_v2/compatibility_terminal_snapshot_20260920_0945.json`；当前汇总状态见 `results/research_progress/project_closeout_status_20260919.json:136-149`。
- 两个 L80 cell 的本地 PracticalV2 validator 均通过；当前状态和验证范围见 `results/research_progress/project_closeout_status_20260919.json:169-180`。这证明了运行、回传、文件完整性和既定数值门，不等于所有观测量的物理收敛。
- 最新比较明确是 baseline Krylov-3 → candidate Krylov-8，状态为 `audit_only`、`claim=none`、无失败记录：
  `results/autoresearch_v5_20260920/static_krylov_controls_r2_comparison_20260920/comparison_summary_20260920.json:1-7`；文字摘要也明确禁止自动推出收敛、相变或论文结论：
  `results/autoresearch_v5_20260920/static_krylov_controls_r2_comparison_20260920/comparison_summary_20260920.md:1-10`。
- 对称相对差显示，alpha=-0.10 两个初态的 gap 变化约 31.6%/43.8%，entropy 最大相对差约 41.0%/53.2%；alpha=-0.175 对应 gap 约 2.1%/4.6%、entropy 约 3.0%/6.7%。`entropymax` 来自各自独立的最大值 index，不得与 gap 或其他 observable 逐行误配。
- 独立调用既有 `analyze_profile` 对 `period=10, window=0.20` 的斜率诊断复核：alpha=-0.10 的主核旧 baseline_v3 值 `0.5822047695/0.4841201940`（center/ferro_j2）对应新 k8 值 `0.9324647204/0.9324647544`；alpha=-0.175 的旧值 `0.9322179068/0.9009138460` 对应新值 `0.9598967633/0.9598967912`。这里记录的是 analyzer 输出的 `c_eff=6×拟合斜率`，不是置信区间，也不是 thermodynamic central charge。
- 旧记录中的“L80 未启动/无 candidate”属于历史状态，不再是当前状态；历史失败区块必须保留为证据，不应覆盖当前 terminal success。当前/历史字段并存于 `results/research_progress/project_closeout_status_20260919.json:71-103,136-149,493-529`。

## 受影响的稿件与状态表述

- `docs/near_final_manuscript_draft_20260819.md:50,161` 以及 `docs/manuscript_claim_evidence_map_20260919.md:39,54,90,95` 旧有的“compatibility 未上传、Julia 未启动、无 L80 candidate/validation”已过时。应改成：L80 Krylov-8 已完成并通过完整性/validator；比较仍仅为 solver-control audit，未宣称 chi 收敛、bulk gap、相变或全局 (c=1)。
- `docs/project_closeout_upgrade_plan_20260919.md:16-19,27-33` 中 Stage 3 的“做困难点静态对照”已有数值审计结果，但其中关于“观测量收敛仍需单独验收”的门仍有效。通过 variance/truncation 或 PracticalV2 原门，不能替代 entropy、gap、谱细节的稳定性证明。
- 当前 L80 对照改变的是 Krylov 维度，不是 MPS bond dimension/chi。`maxdim=1200` 是配置上限而不是 chi sweep；实际新 k8 运行的 actual maxdim 约为 alpha=-0.10 的 264/186、alpha=-0.175 的 286/213。因此不能把本次结果描述为“增大 maxdim 后已完成 chi 收敛”，也不能假定继续增大 1200 必然解决差异。
- Sz=0 有 `center` 与 `ferro_j2` 两种初态；Sz=1 仍固定 `center`。不得把 sector 间差异或这组不对称初态设置当作独立的全初态统计：`docs/manuscript_claim_evidence_map_20260919.md:56`、`results/research_progress/project_closeout_status_20260919.json:194-197`。
- L80/OBC 仍是有限尺寸结果；即使 solver 和 chi 都稳定，也不能直接改写为 thermodynamic/bulk gap。现稿关于“不声称全局 (c=1)/新相”的边界仍应保留。

## 尚未验证的条件

1. solver 误差与截断误差的区分：当前 k3→k8 对照表明 Krylov 控制会影响部分 observable，但未提供实际生效 chi/maxdim 的收敛序列。
2. 关键 observable 的联合稳定性：尤其 alpha=-0.10 的 gap、entropy、dimer/connected/bond 量仍有明显 k 敏感性；不能只凭 variance/truncation 关门。
3. 有限尺寸到 bulk 的外推：L80 单点不能支持 bulk gap、全局中心荷或新相结论。
4. Stage 2 的“局部异常/机制—边界—适用范围”完整证据链尚未以最终稿件级链条闭合；应按现有数据补齐来源、适用范围和反例，而不是默认需要寻找新相。
5. Stage 4 谱学闭环尚未自动成立。是否需要谱学取决于最终保守主张：若只保留有限尺寸 crossover/机制表述，可由现有边界和静态证据决定；若要保留谱权重、极小 gap 或临界性强主张，则需另设谱学验收门。

## 待检验的数值控制

- 第一候选只针对最高敏感点：alpha=-0.10、beta=0.25、L=80；固定现有哈密顿量、初态、sweeps、maxdim 配置和其他 gates，做 Krylov-8 → Krylov-12 的单点对照，用来先判断 solver 残差是否仍是主导差异。
- 冻结最多 64 sweeps；不改成 128 sweeps，不扩展为全域扫描。此项只是一点决策测试，不是重新开展整个 phase scan。
- 若该点在所选 observables 上稳定，再考虑同协议的 L=60、k=8 对照，以分离有限尺寸效应；若仍不稳定，再根据 observable 证据决定是否需要实际生效 chi/cutoff 对照。不能预先把“继续增大 maxdim”当作必然方案。
- 后续是否进入 Stage 4 谱学，应由最终拟保留的主张触发，而不是以“必须找到新相”为完成条件。

## 可无新计算完成的收尾项

- 更新稿件、证据图和 closeout 状态中的 L80 历史表述，保留旧失败记录但标注为 historical。
- 将最新比较固定表述为 `audit_only / claim=none`，明确 Krylov 变化、有限 L、初态不对称和 chi 未收敛边界。
- 完成 Stage 2 证据链的路径、范围和限制整理，以及 Stage 4 是否必要的主张决策；未填作者资料不代填。

