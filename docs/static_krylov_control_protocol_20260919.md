# L80 近收敛 Krylov 单因素对照协议（2026-09-19；2026-09-20 证据更新）

## 范围与目标

本协议只覆盖两个已存在的负 alpha、`beta=0.25`、`L=80` 基线点：

| cell_id | alpha | beta | L | n_units | 初态 |
|---|---:|---:|---:|---:|---|
| `negdiag-a01000-b02500-L080` | -0.100 | 0.25 | 80 | 16 | `center`, `ferro_j2` |
| `negdiag-a01750-b02500-L080` | -0.175 | 0.25 | 80 | 16 | `center`, `ferro_j2` |

目标是记录 `eigsolve_krylovdim=3 -> 8` 的单因素局部对照及其边界。该对照只比较观测量漂移，不建立新的数值通过门，不作相或全域收敛判定。

## 固定设置

候选计算必须保持基线的物理参数、边界、扇区和算法设置不变，唯一预期差异是 `eigsolve_krylovdim`：

| 设置 | 固定值 |
|---|---|
| 边界 | OBC |
| 扇区 | `Sz=0`, `Sz=1` |
| sweeps | 64 |
| chi/maxdim | 1200 |
| cutoff | `1e-11` |
| noise profile | `legacy` |
| q 点数 | 401 |
| 初态 | `center`, `ferro_j2` |
| Krylov | 基线 3；候选显式 8 |

旧基线 manifest 没有记录 `eigsolve_krylovdim`。只有当父、子 manifest 的
`negative_static_cell.jl` provenance hash 命中已登记历史 hash
`0363dbd631f8ad01ce7e6b0b3cf1489b55a157c834ac56919e38876a2d831c29` 时，才记录为 `recorded-default3`；未知 hash 或显式值混用不接受。

## 验收链

1. 对每个父 run 和两个 child 现场核对 `checksums.sha256`。
2. 用既有 `validate_negative_phase_run_practical_v2.validate` 重新验证父、双初态和双扇区；validator 失败时停止。
3. 提取每个初态的 gap、79 个逐 bond entropy、4 window × 2 period 的 8 个 fit、79 个 bond correlation、`dimer_rms` 和左右两点 `connected_quarter`。
4. 将原始 manifest、测量文件、run spec、validator 和分析脚本写入 source hash 清单；原始结果只读，不回写。
5. 候选出现后，先走同一 V2 validator 和设置一致性检查，再用完整 key 配对的 `compare_records` 计算 signed、absolute 和 symmetric-relative drift。空、缺失、重复、非有限或不一致 metadata 必须拒绝。

当前基线提取结果位于：

`results/autoresearch_v5_20260920/static_krylov_baseline_v3`

v3 只修复 `connected_quarter` 的既有配对读取；repair provenance 明确 helper 逻辑与科学数据未改变。当前 r2 comparison 的状态为 `audit_only`，baseline/candidate 均已验证，两个 L80 点各有 324 条配对记录，candidate 已存在并通过 validator。

本轮还保留了四点 L=10 ED/DMRG 对照和两点 Krylov=8 校准的历史记录；v1 的 wrapper timeout flag 与实际 returncode/metrics 分开记录。两个 L80、k=8 点现已通过 Practical V2 数值门、文件完整性和 validator，但旧 k=3 的 gap 与 entropy 仍对 Krylov 设置敏感，因此比较仅作数值审计，不作全部观测量收敛、相或全域单相结论。

当前 r2 对照的 gap 为：

| alpha | start | k=3 baseline | k=8 candidate | 对称相对差 |
|---:|---|---:|---:|---:|
| -0.100 | center | `5.291967069e-5` | `7.277203948e-5` | `31.59%` |
| -0.100 | ferro_j2 | `4.662458090e-5` | `7.277205361e-5` | `43.80%` |
| -0.175 | center | `1.554794869e-4` | `1.587107409e-4` | `2.06%` |
| -0.175 | ferro_j2 | `1.516237868e-4` | `1.587107429e-4` | `4.57%` |

对称相对差统一为 `2(new-old)/(|new|+|old|)`；最大逐 bond entropy 对称相对差分别为 `41.03%/53.16%`（alpha=-0.10，center/ferro_j2）和 `2.99%/6.69%`（alpha=-0.175，center/ferro_j2）。

机器可读证据为：

- `results/research_progress/project_closeout_status_20260919.json`
- `results/autoresearch_v5_20260920/static_krylov_controls_r2_comparison_20260920/comparison.json`
- `results/autoresearch_v5_20260920/static_krylov_controls_r2_comparison_20260920/comparison_summary_20260920.json`
- `results/autoresearch_v5_20260920/static_krylov_baseline_v3/repair_provenance_20260920.json`
- `results/autoresearch_v5_20260920/static_krylov_controls_r2_fetch_0945/validation_negdiag-a01000-b02500-L080-k08.json`
- `results/autoresearch_v5_20260920/static_krylov_controls_r2_fetch_0945/validation_negdiag-a01750-b02500-L080-k08.json`

## 观测量解释边界

比较器输出固定为 `audit_only`。双初态差异、entropy window/period 敏感性、dimer 和 connected 观测量只作为稳定性证据；`k≠chi`，不等于 bond dimension；不得加入任意百分比门，也不得据此命名新相或声称全域单相。不能把 k=3 的 L=40,60 记录与 k=8 的 L=80 记录混作最终 scaling。

## ED 小测与本地 k=8 校准状态

独立小链 ED 参考的本次独立总能量门为 `absE <= 1e-8`；它不是历史 Practical V2 的 `variance/site` 门。四点对照如下，timeout flag 与数值结果分列：

| 来源/cell | alpha | k | Sz=0 absE | Sz=1 absE | sweeps | norm/Sz | 执行事实 |
|---|---:|---:|---:|---:|---:|---|---|
| v1 `a-0100-k3` | -0.100 | 3 | `5.6143420579e-8`（fail） | `1.0643028681e-9` | 16/16 | 1；0/1 | rc=0，`timed_out=true`，metrics 完整 |
| v2 `a-0100-k8` | -0.100 | 8 | `1.2586198750e-10` | `3.8312464312e-11` | 16/16 | 1；0/1 | rc=0，未超时，metrics 完整 |
| v3 `a-0175-k3` | -0.175 | 3 | `2.2880808359e-11` | `3.0005331553e-11` | 16/16 | 1；0/1 | rc=0，未超时，metrics 完整 |
| v3 `a-0175-k8` | -0.175 | 8 | `2.4154012124e-12` | `3.0007996088e-11` | 16/16 | 1；0/1 | rc=0，未超时，metrics 完整 |

因此 `local_k8_calibration_verified=true`，两个 L80 k=8 点通过 Practical V2 gate。L80 对照使用两个 Sz=0 初态（`center`、`ferro_j2`）；Sz=1 固定为 `center`，不当作独立统计重复。本地 L=10 校准只作局部求解检查，不能替代 L80 对照。

该部分结果的 state/norm/Sz 检查已生成（norm=1，Sz=0/1 正确），但不能以小链结果推出 L80 收敛，也不能替代候选的 3→8 对照。

原计划 180 s 不足以覆盖四个冷启动；v3 只对未完成的两个 alpha=-0.175 cell 追加明确 240 s wall 安排，实际总耗时 `167.203 s`。物理参数、sweeps/maxdim/cutoff、初始化协议和验收门均未改变，v1/v2 旧输出未覆盖。四点表与机器可读证据位于：

- `results/autoresearch_v5_20260919/static_krylov_smoke_v1`
- `results/autoresearch_v5_20260919/static_krylov_smoke_v2`
- `results/autoresearch_v5_20260919/static_krylov_smoke_v3`
- `results/autoresearch_v5_20260919/static_krylov_smoke_v3/cross-method-check.csv`

随后新增独立 v4 保存态/增强诊断校准（不覆盖 v1–v3）：两个 L=10、k=8 cell 使用 `SAVE_STATE=1`、`ENRICHED=1`，16 sweeps、maxdim=64、cutoff=`1e-11`、2 threads、legacy noise，合计 wall=`172.016 s`，两点 `k8_gate=true` 且 v4 范围内 `all_cases_gate=true`。两点均有非空 `metrics.csv`、`entropy_profile_full.csv`、`bond_correlations.csv`、`bond_bond_connected.csv` 和 `state_sz0.jld2`；source 与旧 v1–v3 输出 hash 稳定。新 Julia 源 `negative_static_cell.jl` SHA256 为 `291eb369d5441b53d4abafd36d8469e107f4c1d91622ed33478912228ed3635f`，差异范围只记录为 15/16-args 解析修复；v4 driver SHA256 为 `ebbad376886767e33e42f34ef26323d57b104fab52f1530f6d7bb1f0f9fc5cba`。v4 对照表位于：

- `results/autoresearch_v5_20260919/static_krylov_smoke_v4/manifest.json`
- `results/autoresearch_v5_20260919/static_krylov_smoke_v4/cross-method-check.csv`

注意，状态文件中的 `preflight_artifact=r1`、18 项 source hash 和 21 项 shared settings 是历史 baseline/r1 字段，不冒称新版 r2 release；当前 r2/v3 输入与回传文件有独立 manifest/hash 证据。

## 历史前置记录（截至 2026-09-19）

以下状态只描述 r1/pre-authorization snapshot，已被当前 r2 终态替代：当时 r2 尚未发布，L80 production candidate 尚未启动，`remote_julia_started=false`，Stage 3 为 `prepared_not_launched`。初次 launcher 随后确认因 `source_hashes` 的 CRLF/POSIX 文件名解析失败而未启动 Julia；此前兼容脚本上传也曾处于授权阻塞。该段保留历史上下文，不代表当前 candidate 或 validation 状态。

## 当前 r2 终态（2026-09-20）

当前 r2 release 已完成启动、回传和终态验证：`remote_julia_started=true`、`candidate_present=true`、`candidate_validated=true`、`terminal_state=terminal_success_validated`，validator 无 failure。Stage 3 当前为数值完成但 physics stability 未宣称，Stage 2 完整链与 Stage 4 仍按 closeout 状态管理。

`static_krylov_impact_v2` 的 period=10/window=0.20 审计显示 effective slope 从 `0.582205/0.484120` 变为 `0.932465/0.932465`（alpha=-0.10），从 `0.932218/0.900914` 变为 `0.959897/0.959897`（alpha=-0.175），顺序为 `center/ferro_j2`。这量化了 solver sensitivity，但不是 thermodynamic central charge 或 confidence interval。k3/k8 的端点 q_peak 仍为 alpha=-0.10 的 pi、alpha=-0.175 的 0.6pi，dominant ratio 仍变化，因此只保留 finite-size reconstruction，不作 phase claim。证据：`results/autoresearch_v5_20260920/static_krylov_impact_v2/summary.json`、`results/autoresearch_v5_20260920/static_krylov_impact_v2/entropy_fit_comparison.csv`。

## 本地 QA 记录

与本地 hook/分析链直接相关的既有测试已运行且通过：Krylov hook 6 项、负区 entropy size 6 项、联合尺寸比较 4 项；handoff synthetic 测试 PASS；R16 validator synthetic 的 strict-pass、tamper、energy-spread 分支均符合预期。上述测试不等同于 L80 候选收敛验收。
