# Negative-alpha source-data README（Stage B/C 本地支持数据，2026-09-20）

状态：`LOCAL_SUPPORTING_DATA / NOT_PUBLIC`。本文档只整理已有本地结果，不改原始数据、不上传、不选择仓库或许可证，也不把任何 `no_boundary` 结果解释成全域单相。

## 权威入口与计数

权威目录为 `results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha/phase-diagram-v2/`：

- Stage B：`stage_b_practical_v2_completion_summary.json` 为 `grid=96, accepted=89, bounded=7, pending=0`；`stage_b_practical_v2_accepted_index_final.json` 是 accepted-only index（89 条），`stage_b_practical_v2_bounded_records_final.json` 是 7 条 `bounded/NotEvaluable`。
- 96 是 `8 alpha × 6 beta × 2 sizes(L=40,60)` 的 cells/records，对应 48 个 unique `(alpha,beta)` 点；beta=.5 的旧 Stage-A calibration 不计入这个 Stage-B 96。
- Stage C：`stage_c_practical_v2_r1_terminal_summary.json` 为 29 success、0 failed、0 pending；这是 29 个 action/size records，覆盖 22 个 unique `(alpha,beta)`，不是 29 个 unique couplings。`stage_c_practical_v2_r1_boundary_decision.json` 给出 8 个候选 target、0 confirmed、8 unresolved，`stage_d_ready=false`。
- `negative_alpha_crossover_evidence.csv` 有 8 个 target：2 个 momentum reconstruction、5 个 two-sigma ratio sign、0 个 dual diagnostic、1 个 width≤0.025（beta=.05）；beta=.1 没有支持区间。7 个只保留单诊断，不能升格为相界。

## accepted-only → 图/CSV → validator 映射

```text
stage_b_practical_v2_accepted_index_final.json (89)
  + stage_b_practical_v2_bounded_records_final.json (7, excluded from boundary)
  -> stage_b_practical_v2_cross_slice_diagnostic_v2.json (8 targets, 29 actions)
  -> stage_c_practical_v2_r1_terminal_observations.json (29)
  -> stage_c_practical_v2_r1_boundary_decision.json (0 confirmed, 8 unresolved)
  -> negative_alpha_crossover_{points,evidence}.csv (22/8 rows; crossover diagnostic only)
```

`figures/full_alpha_phase_evidence_20260811.source.csv`（23 rows）和 `figures/full_alpha_working_phase_diagram_20260812.source.csv`（24 rows）是历史 Stage-A/working figure sources；各自 QA 为 pass，但不能冒充最终 Stage-B accepted-only index。working figure 的 `boundary_eligible` 只表示该行的局部门，不是相界；`full_alpha_phase_evidence` 的 QA 已标明 negative 2D 未扫描、momentum shift 可能只是 crossover。

实际 cell 验证入口是 `scripts/autoresearch_v5/validate_negative_phase_run_practical_v2.py`（Practical V2：variance/site≤5e-8、truncation≤1e-9、sector tolerance 1e-8、gap≥−1e-8、full-q≥401）；其严格基础脚本 `validate_negative_phase_run.py` 仍使用 variance/site≤1e-8。最终 Stage-B/C index 的 `validation_basis`/validation files 以 Practical V2 为准，不能写成 strict 1e-8 全部通过。

生成/分析入口：`analyze_negative_phase_stage_b.py`、`make_negative_phase_stage_c_r1.py`、`stage_negative_phase_stage_c_terminal.py`、`analyze_negative_phase_stage_c_round.py`、`finalize_full_alpha_phase_diagram.py`、`plot_final_full_alpha_phase_diagram.py`、`plot_negative_practical_v2_crossover_summary.py`。其中通用 `analyze_negative_phase_stage_c_round.py` 的裸默认输入是旧 strict 文件，`next_action()` 还包含 L80=128；本 README 不把它当 Practical V2 重跑命令，也不执行预算生成。V2 图应使用专用 plotter 与已落盘 source CSV。

## CSV 数据字典

### `full_alpha_phase_evidence_20260811.source.csv`

| 列 | 含义/单位 | 缺失与限制 |
|---|---|---|
| `record_type` | 记录类别（controller/calibration/positive 等） | 分类字符串；不能据此合并为同一验收等级 |
| `alpha`,`beta` | 无量纲耦合；模型按 `J1=1` 归一 | 空值不补零 |
| `L` | 链长度/自旋数 | 整数；有限尺寸，不是热力学极限 |
| `R`,`R_error` | 图中有限尺寸诊断量及其误差 | 无量纲；定义由生成器/对应 manifest 给出，不能当相序参量 |
| `q_peak_over_pi`,`q_error` | 主峰位置及误差，均以 `q/π` 表示 | 无量纲；动量重构不等于相界 |
| `E0`,`E1`,`spin_gap` | 能量、`Sz=1` 扇区最低能量（不保证为全谱第一激发）和能隙 | `J1` 能量单位；空字段保持空，不当作 0 |
| `final_energy_change_sz0` | `Sz=0` 最后能量变化 | `J1` 能量单位；缺失保持空 |
| `variance_per_site_sz0` | `Sz=0` 每站点方差 | `J1²` 单位（数值计算以 `J1=1` 归一）；需结合实际 validator 门 |
| `evidence_class` | strict accepted 等证据类别 | 分类标签不是全局相判断 |

### `full_alpha_working_phase_diagram_20260812.source.csv`

`alpha`,`beta` 为无量纲耦合，`L` 为有限链长度，`R`/`R_error` 为无量纲有限尺寸诊断及误差，`q_peak_over_pi` 为 `q/π` 主峰，`boundary_eligible` 为布尔局部门，`artifact` 为相对仓库的 manifest 路径。该表是 working figure source，不能替代 accepted-only index，也不能把 `boundary_eligible=false` 解释成“无相界”。

### `negative_alpha_crossover_evidence.csv`（8 rows）

`target` 为候选目标编号；`beta`、`alpha_left`、`alpha_right` 为无量纲耦合端点；`momentum_reconstruction`、`two_sigma_ratio_sign`、`width_le_0p025`、`dual_diagnostic` 为 0/1 gate；`status` 为 `single_diagnostic_or_not_evaluable` 或 `no_supported_internal_boundary`。0/1 是验收布尔值，不是连续观测量；缺失码无，异常应为拒绝而非填 0。

### `negative_alpha_crossover_points.csv`（22 rows）

`beta`、`alpha` 为无量纲耦合；`q_l60`、`q_l80` 为 L=60/80 的 `q/π`；`momentum_class` 是离散分类：`max(q60,q80)<0.9` 为 incommensurate，`min(q60,q80)>=0.98` 为 q=π，其余为 mixed；`delta_r=R80-R60`，`delta_r_error=hypot(e80,e60)`，`delta_r_sigma=abs(delta_r)/delta_r_error`。这些误差是有限尺寸诊断误差，不是统计置信区间。L60/L80 混合点用于有限尺寸 crossover 诊断，不是热力学相标签。

## 可公开性与科学边界

目前所有入口均为 local-only、未公开归档；拟议 public research repository 尚未选择。第三方 PDF/代码、SSH/PID/凭据、用户路径、环境 dump 和远端运维日志不进入公开数据集。Stage B 的 bounded 7 条从 boundary 排除；Stage C 的 29 条虽通过 Practical V2 数值验收，8 个 target 仍无双诊断，故不能宣称新相、相界或全域单相。`no_boundary` 只表示当前严格标准下未确认边界。
