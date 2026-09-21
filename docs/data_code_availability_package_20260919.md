# Data and Code Availability package（本地审计版，2026-09-19）

状态：`LOCAL_NOT_PUBLIC / NOT_SUBMISSION_READY`。

## 2026-09-20 补充审计入口

下列四组文件是对旧 2026-09-19 family-level 表的定点补充；旧表保留为当日盘点，新的 selected-file audit 只替代对应的 `unknown` 入口，不代表 public deposit、全量 raw/checkpoint 归档或期刊合规：

| 家族 | README | 审计 JSON | 状态 |
|---|---|---|---|
| 正区局部 ED/投影/纠缠（C1–C6） | `docs/positive_local_source_data_readme_20260920.md` | `results/research_progress/positive_local_source_data_audit_20260920.json` | 已完成有限入口核对 |
| 负区 Stage B/C | `docs/negative_phase_source_data_readme_20260920.md` | `results/research_progress/negative_phase_source_data_audit_20260920.json` | 已完成有限入口核对 |
| 动力学 q=pi/full-q | `docs/dynamics_source_data_readme_20260920.md` | `results/research_progress/dynamics_source_data_audit_20260920.json` | 已完成有限入口核对 |
| 总体 Data/Code Availability | `docs/data_code_availability_package_20260919.md` | `results/research_progress/data_code_availability_audit_20260919.json` | 本地总表；非公开发布包 |
| closeout mechanism | `docs/closeout_mechanism_source_data_readme_20260920.md` | `results/research_progress/closeout_mechanism_source_data_audit_20260920.json` | 已完成有限入口核对 |

## 范围与证据等级

这是仓库内的 partial/family-level inventory，不是上传包、DOI、accession 或期刊合规声明。未执行 public deposit，也未选择作者、仓库、许可证或持久标识符。`static_delivery_manifest_20260804.json` 历史记录 35 个静态文件；`figures/*.sources.json` 当前可见 35 个 sidecar。`source_data_inventory_20260804.json` 仅覆盖正区 `[0,1]`、排除负 alpha/Fig.9，不能当全项目清单。下表只列本轮已核对的入口；哈希未实测处保留 `null`，以 manifest/checksum 或目录证据说明检查层级。

| 家族 | 已核对本地入口 | 角色/检查层级 | 图映射与访问现状 |
|---|---|---|---|
| 局部 ED、投影、局部谱 | `results/autoresearch_v3_20260729/round1_doublet_projection/projection_scan.csv`；`results/autoresearch_v4_20260730/round2_local_spectral_channels_v4/{multiplet_scan.csv,folded_transition_weights.csv,checksums.sha256}` | generated numerical/processed CSV；目录与 checksums 入口已核对，未本轮重算 | Fig.1/2/5 sidecar 已指向；panel 级 mapping unknown；local-only、未发布 |
| 正区静态与纠缠 | `results/autoresearch_v5_20260802/round19_phase_diagram_positive_mesh/phase-diagram/observations_merged.json`；`results/autoresearch_v4_20260730/round1_entanglement_scaling/analysis/{calibrated_estimators.csv,claim_summary.json}`；`data/entanglement_spectrum/{spectrum_a0.14_b0.50_L080.csv,spectrum_a0.33_b0.50_L080.csv}` | processed analysis/generated spectra；Fig.3/4 sidecar 与路径已核对，未本轮重算 | Fig.3/4 有明确 sidecar；其他 panel unknown；local-only、未发布 |
| CV accepted/动态 overlay | `results/autoresearch_v5_20260805/round40_qpi_cv_anchor_assembly_accepted/{manifest.json,checksums.sha256,spectrum.csv}`；`results/autoresearch_v5_20260806/round43_handoff_final_v2/{handoff_summary.json,cross_method/cross-method-check.json,accepted11/manifest.json,accepted11/checksums.sha256}`；`figures/round43_fig8_final_20260806_v2.{source.csv,sources.json}` | generated spectra + processed cross-method；manifest/checksum 与 figure source 入口已核对 | final_v2 accepted11 production_agreement（同点 q=π、η=.1）；round40 accepted7 仅为历史；完整点到 panel mapping unknown；local-only、未发布 |
| q=π TEBD 与 limited full-q | `results/autoresearch_v5_20260803/round26_qpi_tebd_production/`；`results/autoresearch_v5_20260807/minimal_fullq_handoff_eta020_20260808_1533/{handoff_summary.json,checksums.sha256}`；`figures/fullq_minimal_eta020_20260808.{source.csv,sources.json}` | generated correlation/spectrum + processed handoff；目录、handoff/checksum 与 sidecar 入口已核对 | 仅限定 q=π/minimal full-q；不代表全频率闭环；local-only、未发布 |
| Stage1 closeout joint_v2 | `results/autoresearch_v5_20260919/closeout_stage1_joint_v2/{joint_size_evidence.csv,qa.json,summary.json}` | source/QA summary；三文件入口已由项目状态确认；没有 manifest，不假定完整 | 主图/补图 mapping 未本轮核对；local-only、未发布 |
| 近零点 oracle | `results/autoresearch_v5_20260919/near_zero_alpha_oracle_v2/{summary.json,oracle_points.csv,checksums.sha256}` | registered result；既有状态已记录，本轮不重验数值 | 机制报告入口；figure mapping unknown；local-only、未发布 |
| Stage3 静态观测量基线 | `results/autoresearch_v5_20260919/static_krylov_baseline_v2/{baseline_inventory.json,manifest.json,source_hashes.json,gap_records.csv,entropy_records.csv,entropy_fits.csv,bond_correlations.csv,connected_quarter.csv,dimer_rms.csv}` | processed extraction/audit provenance；目录和既有 manifest 已核对 | 无已核实图映射；candidate/Stage B/C/完整 saved-state publication mapping 未本轮重核；local-only |

## 代码、环境与排除项

核心环境入口是 `Project.toml`、`Manifest.toml`；代码入口是 `src/` 的 PentamerChain/hamiltonian/ED/DMRG/spectral 文件及 `scripts/02_dmrg_chain.jl`、`scripts/05_tebd_pentamer_server.jl`。本轮只记录入口，不声称完整 code closure；`docs/julia_environment_audit_20260729.md` 是历史本地环境证据。

第三方 `references/` PDF/代码未经授权不打包；`paper/`、SSH/PID/凭据/用户路径、环境 dump、远端日志和 launcher 运维 payload 不进入公开集。失败 provenance 若以后公开，须先脱敏。图像是 figure product，不替代 raw/processed source data；Stage B/C、完整 saved-state、全图逐 panel mapping 和全 repo coverage 均未本轮确认。

## Availability statements

**Current local/not-public (not submission-ready).** The data and analysis outputs listed in the accompanying local audit are retained in the local project workspace and are not currently deposited in a public repository. No DOI, accession, or repository URL has been assigned for the proposed deposit, and the deposit licence remains unresolved. This is a bounded family-level inventory, not a claim that all raw checkpoints, processed files, figures, saved states, or manuscript claims have been released. Third-party materials and operational records containing hosts, user paths, PIDs, credentials, or environment dumps are excluded.

**Submission template (not submission-ready).** Data and code will be deposited at **[UNRESOLVED: repository and public URL]** under **[UNRESOLVED: licence]**, with **[UNRESOLVED: DOI/accession]**. The release will include README, data dictionary, checksums, versioned figure-to-source mapping, and environment information. Code will be released at **[UNRESOLVED: code URL and commit/tag]**. Author/data-owner details are **[UNRESOLVED: authors, affiliations, steward, permissions]**; the exact main/supplementary panel mapping is **[UNRESOLVED: author-confirmed mapping]**. Third-party materials remain under their original terms.

中文说明：本轮未执行 public deposit；作者、数据负责人、仓库、许可证、DOI/accession、代码版本和逐图 source mapping 待确认。目标期刊未定，不声称任何具体期刊政策合规。
