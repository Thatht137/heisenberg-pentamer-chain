# 收尾机制来源数据说明（2026-09-20）

本文件是工作区内的局部来源说明，配套审计记录为
`results/research_progress/closeout_mechanism_source_data_audit_20260920.json`。
它只整理已存在的分析产物、CSV schema、图源映射和可复核哈希；不构成全项目数据可用性声明，也不表示 public release、公开仓库、许可证或 DOI 已完成。

## 范围与状态

| 数据组 | 实际范围 | 当前状态 |
|---|---|---|
| `closeout_stage1_joint_v2` | 12 个物理点、24 个初态记录、192 个拟合记录；`beta=0.25`，`alpha=-0.175,-0.150,-0.125,-0.100`，`L=40,60,80` | 已有的有限尺寸联合证据；未作热力学相判定 |
| `near_zero_alpha_oracle_v2` | 8-spin OBC，47 点（42 nonzero grid、3 个 `alpha=0`、2 个 finite-alpha control），11 gates | 局部 oracle 验证通过；不是完整链相图 |
| `negative_phase_independent_audit_v6` | 孤立五聚体/四重态局部扫描，各 201 行，`alpha∈[-1,-0.001]` | 局部负区投影与形状因子诊断；不是全链单相证明 |
| `static_krylov_baseline_v2` | `L=80` 的 2 个参数点、双起始态；六类 CSV，manifest 记录 Krylov `k=3` | 历史 baseline 快照；当前使用 v3，candidate 已完成数值验收 |

所有路径均相对于仓库根目录。文件级 bytes/SHA256、CSV 列和行数见配套 JSON；本说明不复制原始大状态。

## 来源与图映射

### Stage 1 四面板

主源是 `results/autoresearch_v5_20260919/closeout_stage1_joint_v2/joint_size_evidence.csv`，导出为同目录的 `negative_size_joint_evidence.png/.svg/.pdf/.tiff`。四面板映射为：

- **a**：仅绘制 `c10_*` 截距拟合；固定 `f=.20` 的双初态均值与所有窗口 envelope。`c5_*` 虽保留在 CSV，未绘入 panel a。
- **b**：`N` 与有限 OBC `Sz=1-Sz=0` gap（含 `gap_*`）；`N·gap` 不是体能隙外推。
- **c**：中央区间 dimer RMS（`dimer_*`）。
- **d**：带符号 staggered connected bond（`staggered_connected_*`）。

范围和双初态差异是敏感性范围，不是统计置信区间。双初态只对应 `Sz=0` 主态的 `center/ferro_j2` 起始分支，不应写成两个独立的 `Sz=1` 覆盖。

### 近零 α 机制入口

`near_zero_alpha_oracle_v2` 的数值源为 `oracle_points.csv`、`spec.json`、`summary.json` 与 `checksums.sha256`。对应机制页面是 `results/autoresearch_v5_20260919/near_zero_alpha_mechanism_report_v2/report.html`（及其 `report.json`），内容把 `[1,1,alpha,beta,alpha,1,1]` 的局部构造、
`Delta_8/alpha^2 -> 2/(9 beta)`、alpha=0 multiplet 和 11 gates 结构化呈现。该目录没有独立 PNG/SVG 机制图；

这里必须保留一条误差口径：两个 finite-alpha control 的 `prediction_relative_error` 是相对 leading coefficient `2/(9 beta)` 的误差，**不是 L=80 误差**。2% gate 只作用于 42 个 nonzero grid rows；finite-alpha control 不套该 gate。局部 8-spin oracle 不能证明完整链的形状因子、相或全域单相。

### Stage 2 负 quartet 局部诊断

新增说明纳入既有目录 `results/autoresearch_v5_20260913/negative_phase_independent_audit_v6/`，不扩展其 DMRG 或 2–3-cell ED。`single_pentamer_multiplet_scan.csv` 记录孤立五聚体 `S=3/2` 局部多重态扫描；`negative_quartet_projection_scan.csv` 记录 `c1..c5` 投影、`J_eff/beta` 与折叠权重。对应图为 `negative_alpha_quartet_projection.png/.svg/.pdf/.tiff`：

- **a**：`S=3/2` quartet projection coefficients 与 `J_eff/beta`；
- **b**：`q/pi=0.2,0.6,1.0` 折叠形状因子权重。

已有 summary 给出的 `J_eff/beta` 局部范围约为 `0.10751475–0.11111110`、主折叠动量为 `q/pi=0.6`。这些是孤立局部投影/形状因子证据，不是全链单相证明。

### Static Krylov baseline

`static_krylov_baseline_v2` 的六类 CSV 是 `gap_records.csv`、`entropy_records.csv`、`entropy_fits.csv`、`bond_correlations.csv`、`connected_quarter.csv`、`dimer_rms.csv`；`manifest.json`、`baseline_inventory.json` 与 `source_hashes.json` 是来源登记。它只覆盖两项 `L=80` 参数和两种起始态，manifest 一致记录 `k=3`。

### 2026-09-20 勘误：baseline v2 的 connected-quarter 行绑定

旧 `static_krylov_baseline_v2/connected_quarter.csv` 的行标签存在 target/dist 坐标绑定错位；这是后处理导出/标注错误，不是 DMRG 失败，也没有放宽任何数值门。原始 pilot connected CSV 与其余五类导出未变。已从同一 raw 来源以修复后的导出器独立生成当前目录：
`results/autoresearch_v5_20260920/static_krylov_baseline_v3/`，登记文件为 `baseline_inventory.json`、`manifest.json`、`repair_provenance_20260920.json`。

当前 comparison 使用 v3；五类未受影响 CSV 的 SHA 与 v2 一致，8 行 staggered connected 数值保持不变，v2 仅作为可追溯历史快照保留。不要把旧 v2 的 connected-quarter 哈希与修复后的导出器混称为同一版本。L80 k8 candidate 已完成两点数值验收，但 648 条对照仍标记 `audit_only`；Krylov `k` 也不是 MPS bond dimension `chi`，不能据此宣称全部观测量收敛。

**2026-09-20 终态勘误补充。** v2 的坐标错配已由 v3 从同一 raw pilot 来源修正并通过五类 SHA、8 行 staggered 值和 target 20/60 原始行核验；L80 k8 两个物理点及四个初态子运行已通过终态与独立 validator。早期以错误 v2 坐标尝试的 candidate comparison 未生成可用结果，相关失败诊断仅作为历史快照保留；当前可读比较唯一指向 v3 baseline 与 `audit_only` comparison，不把历史未生成文件写成物理结论。

## CSV 口径与缺失码

四组目录的列定义、单位、实际行数和 observed missing code 已完整列在 JSON 的 `csv_schema`。共同规则是：

- `alpha/beta` 为 `J1=1` 约定下的无量纲耦合；能量/gap 以 `J1` 单位记录，相关、投影系数、权重和误差诊断为无量纲，索引/计数列为 count。
- `near_zero_alpha_oracle_v2/oracle_points.csv` 中 `alpha=0` 行的 alpha-divided prediction 字段为空；空字符串表示“不适用”，不能改填零。
- 其余本次选定 CSV 未观察到空单元；未知值也不能被静默填零。
- 熵列保留生成脚本的 log 约定；其数值为无量纲熵，不应把起始态范围写成 CI。

## 可复核性与边界

分析/验证入口和实测文件哈希在审计 JSON 的 `code_entrypoints`、`selected_files` 中列出。已有 checksums、manifest 和 source-hash registry 原样作为 provenance；84 个原始大状态未在本清单中重新校验。

该说明仅提供工作区内可追溯入口；尚未选择 public repository、license、DOI 或 accession。任何对外数据可用性声明都需要在另行确认访问路径、许可证、元数据和长期归档后再写。
