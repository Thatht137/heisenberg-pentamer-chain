# 正区 C1–C6 本地源数据入口（2026-09-20）

状态：`local-only`、family-level inventory；未上传公共仓库，未指定许可证或 DOI。本文件不修改 `paper/`，也不把历史图当作新计算。

## 范围与计数

本清单只覆盖 `docs/manuscript_claim_evidence_map_20260919.md` 的 C1–C6：孤立五聚体局部 ED/投影/局部谱、正区有限尺寸诊断和正区纠缠有限尺寸来源。负 `alpha`、动力学时间域、完整 raw/checkpoint 归档均不在本次范围。

`observations_merged.json` 有 105 条 parameter-size records = 35 个 `(alpha,beta)` 耦合点 × `L=40,60,80`，不是 105 个耦合点。其中 `alpha=0` 边界控制为 21 条（7 个耦合点），严格 `alpha>0` 为 84 条（28 个耦合点）；`beta=0` 没有记录。网格为 `alpha={0,.125,.25,.5,1}`、`beta={.05,.1,.25,.5,.75,.9,1}`。

## 图、面板与源文件映射

以下映射由五个 `.sources.json` sidecar 和 `scripts/autoresearch_v5/plot_paper_static_figures_20260804.py` 的实际读入路径确定。

| 图/面板 | 读入源 | 对应 C | 证据边界 |
|---|---|---|---|
| Fig.1a | 无数值源；脚本绘制五自旋结构示意 | C1 | 示意 panel，不应当作观测量或 ED 数据 |
| Fig.1b | `round2_local_spectral_channels_v4/multiplet_scan.csv`；孤立单胞多重态能级 | C1 | 五自旋单胞局部 ED；不是完整链相图 |
| Fig.2a–b | 同一 `multiplet_scan.csv`；能级流与 `q=pi` 权重 | C6 | 反射宇称/局部选择定则；需要长链动力学才能谈色散 |
| Fig.3a–d | `round19_phase_diagram_positive_mesh/phase-diagram/observations_merged.json`；R(L=80)、R 的截面和尺寸差 | C5 | 40/60/80 的有限尺寸诊断；无热力学边界或全域单相结论 |
| Fig.4a–b | `spectrum_a0.14_b0.50_L080.csv`、`spectrum_a0.33_b0.50_L080.csv`；每个参数点五类 bond cut | C4 | 长链有限尺寸纠缠谱，不是局部单胞谱 |
| Fig.4c | `calibrated_estimators.csv` 与 `claim_summary.json` | C4 | 与同尺寸 Heisenberg `c=1` oracle 的校准一致性；raw log-L 质量门失败 |
| Fig.5a–f | `projection_scan.csv`、`multiplet_scan.csv`、`folded_transition_weights.csv` | C2、C6 | a 为示意；b/c 为投影系数与 `J_eff/beta`；d/e/f 为局部能级、折叠权重和 quartet 份额；不含 C3 二阶残差 |
| C3（无对应 Fig.5 面板） | `round3_two_pentamer_ed/{summary.json,comparison.csv}`；`round2_effective_scan/analysis_final/{summary.json,effective_comparison.csv}` | C3 | 两胞 ED 与有限完整链 effective-scan 的二阶残差；仅已测路径/有限尺寸 |

实际入口脚本为：

- `scripts/autoresearch_v5/plot_paper_static_figures_20260804.py`：统一生成 Fig.1–5，直接声明上述源路径；Fig.1a 的结构示意没有观测量源 CSV。
- `scripts/autoresearch_v5/plot_model_excitation_mechanism.py`、`scripts/autoresearch_v5/plot_reference_aligned_figures_20260803.py`：局部投影/多重态绘图入口。
- `scripts/autoresearch_v4/analyze_positive_local_spectral_channels.py`：生成局部 `multiplet_scan.csv`、`folded_transition_weights.csv`。
- `scripts/autoresearch_v5/merge_positive_mesh_observations.py`：合并正区有限尺寸观察；不在本次重新计算。
- `scripts/autoresearch_v3/analyze_entanglement_scaling.py`、`scripts/autoresearch_v3/finalize_entanglement_claim.py`：纠缠 profile、尺寸标度和校准 claim summary。
- `scripts/autoresearch_v5/plot_positive_phase_delta_summary_20260804.py`：历史有限尺寸差诊断入口；不把其有限尺寸 guard 升格为相图证明。

## 选定 CSV/JSON 数据字典

| 文件 | 记录/行数 | 列或键及含义 | 单位、缺失码与范围说明 |
|---|---:|---|---|
| `projection_scan.csv` | 100 | `alpha, ground_energy, local_gap, c1..c5, coefficient_sum, reflection_error, jeff_over_beta, dominant_q_over_pi, dominant_weight_fraction` | `alpha` 与 `J_eff/beta` 无量纲；能量/能隙按 `J1=1`；系数、权重无量纲；选定文件未见空、`NA`、`null` |
| `representative.csv` | 3 | 同投影字段，另有 `weight_q0..weight_q4` | 权重无量纲；仅代表点，不替代 100 点扫描；未见缺失码 |
| `multiplet_scan.csv` | 1000 | `alpha, branch, spin_S, parity, degeneracy, energy, excitation, qpi_weight` | `spin_S`/宇称/简并度为离散标签；`energy, excitation` 按 `J1=1`；`qpi_weight` 无量纲；未见缺失码 |
| `folded_transition_weights.csv` | 5000 | `alpha, q_over_pi, branch, spin_S, parity, excitation, weight` | `q_over_pi`、`weight` 无量纲，`excitation` 按 `J1=1`；未见缺失码 |
| `observations_merged.json` | 105 records | `params.{alpha,beta,L,n_units}`, `value`, `error`, `status`, `budget`, `artifact` | `alpha=J2/J1`、`beta=J3/J1` 无量纲，`L/n_units` 为尺寸计数；`value` 是脚本绘为 `R` 的归一化诊断量，JSON 未提供独立物理单位；本次记录均 `success` 且必需键齐全。`artifact` 含历史路径字符串，公开发布前需脱敏 |
| `calibrated_estimators.csv` | 3 | `estimator, ratio` | 比值无量纲：1.0331008571、1.0240221003、1.0274564248；未见缺失码 |
| `midchain_scaling_pentamer.csv` | 5 | `model, N_units, entropy, entropy_error, D_low, D_high` | entropy 为无量纲纠缠熵；`D_low/high` 为截断维度；未见缺失码 |
| 两个 `spectrum_a*_b0.50_L080.csv` | 各 80 | 公共列 `alpha,beta,L,bond,bond_class,level,probability,entanglement_energy,energy`；`a0.14` 另有 `schmidt_sz` | 概率无量纲，纠缠能级为谱的对数尺度，`energy` 按 `J1=1`；`schmidt_sz` 仅 a0.14 文件存在，不能假定两文件同列；未见缺失码 |

## 科学判读边界

1. C1/C6 的 `multiplet_scan` 与 transition weights 是孤立五聚体单胞 ED。它们支持局部 `S=1/2` 双重态、反射宇称和 `q=pi` 选择规则，不是完整 OBC 链的相结论。
2. C2 的 `projection_scan` 是 tested positive-alpha 路径的低能投影诊断；正的 `J_eff/beta` 不自动推出所有 `beta` 的全链结构。
3. C3 的二阶能量残差来自单独的两胞 ED 与 `analysis_final` effective-scan（不是 Fig.5 的 `projection_scan`）。`summary.json` 给出两胞 `1.9689–1.9915`、有限链 `N_units=8,12,16` 为 `1.9483–1.9495` 的拟合幂；这是有限尺寸/已测路径证据，不是任意强耦合误差界。
4. C5 的 105 条记录是有限尺寸 `R` 网格。无 accepted crossing 只能表述为“当前有限尺寸证据未定义内部边界”，不能宣称正区全域单相或热力学无隙。
5. C4 的校准比值范围为 `1.0240–1.0331`，支持 matched-size `c=1` 一致性；`claim_summary.gates.raw_log_fit_quality=false`，因此不能写成已测得热力学 central charge，也不能由此命名新相。
6. 本清单只核对所列入口的文件字节、SHA、CSV 表头/行数和 JSON 结构；未重跑全部 validator，未验收完整 raw/checkpoint 归档。第三方参考 PDF/code、SSH/PID/凭据和用户路径不应进入公开数据包。

## 公开交付状态

当前仅为本地 supporting-data inventory。仓库、作者、许可、DOI 和最终公开目录均待作者确认；没有执行 public deposit。投稿替换模板（尚未 ready）：`[UNRESOLVED: repository/accession/DOI/license/author contact]`。
