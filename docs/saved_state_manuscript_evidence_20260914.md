# 保存态结果写作记录

一句话论点：六点保存态计算数值验收通过，但取消类别筛选后仍有单尺寸纠缠异常，因此局部尺寸核验尚不可省略，现阶段不命名第二个相。

## 草稿改动

`docs/near_final_manuscript_draft_20260819.md` 新增 3.6、纠缠拟合可复现性说明和收尾限制。paper/ 未修改。Results 依次说明数值验收、观测异常和推断边界；方法说明单列，避免将软件测试写成物理验证。

## 术语

- c_eff：有效纠缠拟合系数，不直接称热力学中心荷。
- Practical V2 acceptance：冻结数值门下的验收，不是相确认。
- sensitivity range：窗口、拟合模型或初态改变导致的范围，不是置信区间。
- localized anomaly：局部异常，不等同于新相或相界。

## 论断与证据

| 论断 | 本地来源 | 状态 |
|---|---|---|
| 六点/十二初态验收通过 | results/research_progress/negative_phase_independent_pilot_status_20260913.json；原始回传 validation_practical_v2 | 数值层面支持 |
| 最大方差/site 1.2875e-9 | 上述状态与六点 validator 记录 | 数值层面支持 |
| 十二剖面哈希、336次拟合及系数范围 | results/autoresearch_v5_20260913/pilot_entropy_robustness_20260914/summary.json、fits.csv | 已复核 |
| 两点复用通过、十点缺失 | results/autoresearch_v5_20260914/negative_entropy_sizes_r1/local_coverage_prelaunch.json | 历史快照，已由下方 2026-09-19 更新取代 |
| 第二个热力学相 | 尚无充分证据 | 未确认 |
| 全域不存在相变 | 当前计算不能证明 | 不可声称 |

## 2026-09-19 最新验收状态

当前十二点联合尺寸比较已完成并通过数值验收：`results/autoresearch_v5_20260919/closeout_stage1_reanalysis_v2/summary.json` 记录 12/12 个物理点、24 个初态剖面和 192 次共享斜率拟合；对应 $L=40,60,80$ 仅为 $N=L/5=8,12,16$ 个五聚体。联合输出位于 `results/autoresearch_v5_20260919/closeout_stage1_joint_v2/`，其中 $L=80,\alpha=-0.10,\beta=0.25$ 的两初态扇区 gap 全差为均值的 12.65%。初态差异和拟合窗口范围是敏感性范围，不是统计置信区间或显著性估计；开边界扇区 gap 也不直接等同于体能隙。

此前六点 $L=80$ 审计的 12 个剖面和 336 次拟合来自独立历史来源 `results/autoresearch_v5_20260913/pilot_entropy_robustness_20260914/summary.json`，现保留并与本次 12 点/24 剖面/192 次共享拟合分开。旧快照中的“两点复用通过、十点缺失”仅描述 2026-09-15 之前的本地状态，不代表当前验收结果。

## 2026-09-19 初始化协议文字修正

草稿 Methods 原文曾写成：`The negative-region calculation uses two product-state initializations in both $S^z=0$ and $S^z=1$ sectors.` 该句把 Sz=1 错写成具有两种独立初态，现已狭义修正为：负区使用两种 Sz=0 product-state 初态；Sz=1 始终使用固定 `center` 参考。修正只涉及方法口径，不改变物理结果、数据或验收门。

源码依据为 `scripts/autoresearch_v5/negative_static_cell.jl:83`（`target_sz == 1 && mode != :center` 时拒绝非 center 模式）以及 `scripts/autoresearch_v5/run_negative_static_cell.py:215`（manifest 明确记录 `init_mode_sz0=args.init_mode`、`init_mode_sz1="center"`）。因此，涉及初态差异的结果应表述为两种 Sz=0 初态的敏感性；Sz=1 是固定 center 参考，不是第二个独立初态族。

该文字修正不关闭观测量收敛问题：有限尺寸纠缠、键关联、扇区 gap 及负区响应的观测量级收敛仍需按既定 Stage 3 链完成；当前证据不能据此宣布第二个热力学相，也不能证明全域单相。

## 尚缺内容

现有十二点的机制解释与观测量收敛对照、统一分析后的相图定稿、负区响应是否需要补算的判定，以及目标期刊格式和最终文献核对。草稿并非可直接投稿的最终稿。本轮不新增外部文献事实，不用参考作者的口头反馈代替本项目的数值证据。
