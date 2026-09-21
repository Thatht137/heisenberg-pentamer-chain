# 本地交付 source-data、复算与补充材料清单

> 清单更新：2026-08-07。仅登记本地文件；范围为 `0 <= alpha,beta <= 1`，不含负 `alpha` 或参考 Fig. 9。
> round43 的 `q=pi` production 门已关闭；full-q production 仍计算中。所有“可复算”均要求先核对同目录 `checksums.sha256` 或图的 `.sources.json`。

## 1. 主图 source-data 与输出

| 图 | source-data（sidecar 已声明 SHA-256） | master 输出与 sidecar | 当前用途 |
|---|---|---|---|
| Fig. 1 | `results/autoresearch_v4_20260730/round2_local_spectral_channels_v4/multiplet_scan.csv` | `figures/paper_fig1_model_local_multiplets_20260804.{svg,pdf,png,tiff}`；`...sources.json` | manuscript master |
| Fig. 2 | `results/autoresearch_v4_20260730/round2_local_spectral_channels_v4/multiplet_scan.csv` | `figures/paper_fig2_level_flow_qpi_filter_20260804.{svg,pdf,png,tiff}`；`...sources.json` | manuscript master |
| Fig. 3 | `results/autoresearch_v5_20260802/round19_phase_diagram_positive_mesh/phase-diagram/observations_merged.json` | `figures/paper_fig3_positive_groundstate_diagnostics_20260804.{svg,pdf,png,tiff}`；`...sources.json` | manuscript master，有限尺寸无 crossing |
| Fig. 4 | `data/entanglement_spectrum/spectrum_a0.14_b0.50_L080.csv`；`data/entanglement_spectrum/spectrum_a0.33_b0.50_L080.csv`；`results/autoresearch_v4_20260730/round1_entanglement_scaling/analysis/{calibrated_estimators.csv,claim_summary.json}` | `figures/paper_fig4_entanglement_spectrum_20260804.{svg,pdf,png,tiff}`；`...sources.json` | manuscript master，校准后 `c=1` 一致性 |
| Fig. 5 | `results/autoresearch_v3_20260729/round1_doublet_projection/projection_scan.csv`；`results/autoresearch_v4_20260730/round2_local_spectral_channels_v4/{multiplet_scan.csv,folded_transition_weights.csv}` | `figures/paper_fig5_effective_chain_selection_rules_20260804.{svg,pdf,png,tiff}`；`...sources.json` | manuscript master，机制图 |

主图的 `.sources.json` 同时记录 source-data 与 SVG/PDF/PNG/TIFF 的 SHA-256。Fig.1–5 master 与 Fig.8 bounded bundle 的存在性、哈希、PDF/SVG/位图格式和分辨率均已通过本地 QA。

## 2. 动力学 source-data 状态

| 资产 | 本地路径 | 状态与允许用途 |
|---|---|---|
| 严格 `q=pi` TEBD | `results/autoresearch_v5_20260803/round26_qpi_tebd_production/cell-alpha023-qpi-dt0025-t30/` 和 `cell-alpha023-qpi-dt00125-t30/` | 含 `correlation.{csv,jld2}`、`spectrum.csv`、`manifest.json`、`run_config.json`、`checksums.sha256`。限定 `alpha=0.23,beta=0.5,L=40` 的 `dt/dt2` 收敛证据。 |
| TEBD 本地复核 | `results/autoresearch_v5_20260804/round36_local_qpi_reanalysis_recheck/` | `summary.json`、`spectrum_comparison.csv`、`cross-method-check.csv` 和 checksum。TEBD `Agreement`，CV--TEBD `NotEvaluable`。 |
| 已验收 CV 锚点 | `results/autoresearch_v5_20260805/round40_qpi_cv_anchor_assembly_accepted/` | `spectrum.csv`、`manifest.json` 与 `checksums.sha256`；accepted-only 七点为 `0.20–1.50`，不含失败 `0.05`。 |
| 单点 CV 来源 | `results/autoresearch_v5_20260730/round3_cv_L40_probe/cell-0001-L40-qpi-w020/`；`results/autoresearch_v5_20260802/round21_cv_triplet_warmstart/cell-0002-L40-qpi-w025-w035/`；`results/autoresearch_v5_20260803/round31_qpi_cv_extension_completed_cells_20260804/cell-l40-qpi-high-{055,100}/` | 每个目录保留 `manifest.json`、`spectrum.{csv,jld2}`、日志、诊断和 checksum；仅通过 residual 门的点纳入 assembly。 |
| 低频失败 CV | `results/autoresearch_v5_20260803/round31_qpi_cv_extension_completed_cells_20260804/cell-l40-qpi-low-000-020/` | 文件完整但 `0.00--0.15` 的最大 residual 为 `1.323762e-5`，超过 `1e-5`，必须隔离，不进生产表。 |
| `omega=1.50` | `results/autoresearch_v5_20260805/round40_qpi_cv_high150_fetch/cell-l40-qpi-high-150/` | residual=`5.540316e-6`；远端/本地 checksum、非覆盖回传和 validator 全部通过，属于 accepted-only。 |
| `omega=0.05` retry | `results/autoresearch_v5_20260805/round41_qpi_cv_low005_retry_fetch_20260805_2212/cell-l40-qpi-retry-005/` | 程序正常退出，但 residual=`1.1767006e-5>1e-5`；仅作失败审计，禁止进入 accepted-only。 |
| Fig. 6 旧谱 | `data/Sqw_tebd_pentamer_alpha=1.0_beta={0.1,0.4,0.5,0.7,1.0}.csv` | 可作为 exploratory supplementary 资产，不是生产级时域/收敛数据。 |
| Fig. 7 pilot | `data/Sqw_tebd_pentamer_alpha={0.14,0.23,0.33}_beta=0.5_L40_t15.{csv,jld2}` | 可作为 pilot supplementary 资产，不关闭路径或跨方法门。 |
| Fig. 8 bounded | `figures/paper_fig8_bounded_cv_tebd_20260805.sources.json` 与 `results/research_progress/fig8_bounded_source_data_20260805.csv` | 七点 CV–TEBD 共享频率比较；失败 `0.05` 为空心叉，总体标签仍为 `NotEvaluable`。 |
| Fig. 8 production | `results/autoresearch_v5_20260806/round43_handoff_final_v2/` 与 `figures/round43_fig8_final_20260806_v2.*` | accepted11、`production_ready=true`、Agreement；仅限 `alpha=0.23,beta=0.5,L=40,q=pi`。 |
| 精简 full-q | `results/research_progress/minimal_fullq_campaign_20260807/` 与 `scripts/autoresearch_v5/{fetch_fullq_tebd_run,validate_fullq_tebd_run,finalize_minimal_fullq_handoff,plot_minimal_fullq_campaign}.py` | 六个生产 run 计算中；本地接收、双门验收和四格式绘图入口已通过合成端到端测试。 |

## 3. checksum 与复算顺序

1. 对 Fig. 1--5：读取各自 `figures/paper_fig*_20260804.sources.json`，确认其中声明的 source-data 和四种输出文件存在且 SHA-256 一致。
2. 对独立 run：先读取 `manifest.json` 与 `status.json`，再对同目录 `checksums.sha256` 逐项计算 SHA-256；失败、缺失或非终态 run 不得并入汇总表。
3. 对 CV：使用 `round40_qpi_cv_anchor_assembly_accepted/manifest.json` 的 provenance 列表回溯每个单点，而不是从图像反推数值。
4. 对 TEBD：复算应从 `correlation.{csv,jld2}`、`run_config.json` 和 Fourier 定义开始；`spectrum.csv` 只作为衍生输出。`round36` 的 `spectrum_comparison.csv` 是收敛诊断，不是原始时域数据。
5. 对所有动态主张：重跑 gate 前必须检查残差、非负性、覆盖范围、`q=0`、镜像动量和 CV--TEBD 门。共享稀疏窗不替代 `[0,1.5]` 全窗验收。

可用的分析/绘图入口包括：

```text
scripts/autoresearch_v5/analyze_qpi_tebd_production.py
scripts/autoresearch_v5/assemble_qpi_cv_anchors.py
scripts/autoresearch_v5/analyze_fig7_pilot_quantitative_20260804.py
scripts/autoresearch_v5/analyze_effective_continuum_overlap.py
scripts/autoresearch_v5/plot_reference_aligned_fig6_positive_beta_20260803.py
scripts/autoresearch_v5/plot_reference_aligned_fig7_positive_alpha_20260804.py
```

本清单不要求直接运行这些脚本，也不授权连接服务器或覆盖历史 run。

## 4. 补充材料包

| 包 | 建议内容 | 交付等级 |
|---|---|---|
| SM-A：模型与局域 ED | Fig. 1--2 的完整多重态表、反射宇称、投影系数、局域谱权和 sidecar。 | 可交付 |
| SM-B：静态与纠缠审计 | Fig. 3--4 source-data、尺寸/初态限制、纠缠校准表、`mesh-cell-0051` 的排除理由。 | 可交付 |
| SM-C：严格 `q=pi` 方法验证 | `round26` 原始相关函数、TEBD `dt/dt2`、`tmax`、`maxdim` 和 Fourier 复算；CV oracle/稀疏锚点。 | 可交付，但明确只限该实例 |
| SM-D：未关闭的动态门 | low-005 residual 失败记录、high-150 验收记录、七点覆盖图和 `NotEvaluable` 判定。 | 可交付，不能充当 production Agreement |
| SM-E：Fig. 6--8 边界资产 | `alpha=1` exploratory、正 `alpha` pilot、Fig.8 bounded 七点叠加和各自 sidecar。 | 按 exploratory/pilot/bounded 分级交付 |

最终包无需等待 full-q 才保留已有 Fig.1--5 与限定 `q=pi` Fig.8；full-q 仅在六 run 和三组 `dt/dt2` 全部通过后加入。SM-C--E 同时保留 production、bounded 与失败路径，所有材料继续排除负 `alpha` 和参考 Fig. 9。
