# Dynamics C7 source-data README

更新时间：2026-09-20  
范围：仅核对两个已存在的动力学图源链；不复制 raw correlation、JLD2 或大状态，不重算、不重绘、不上传。

## 目的与边界

本 README 对应 `results/research_progress/dynamics_source_data_audit_20260920.json`，记录 final-v2 的 q=π CV–TEBD Agreement 图源和 minimal full-q 三组 `dt`/`dt/2` 图源。所有路径均为本项目相对路径，SHA256 与字节数为本地实测值。

本页说明动力学资料的来源对应关系；公开归档与文件清单见 https://github.com/Thatht137/heisenberg-pentamer-chain/releases/tag/archive-2026-10-26。

## final-v2 q=π CV–TEBD

图像 `figures/round43_fig8_final_20260806_v2.png` 的实际面板为：

- **a — Agreement**：`alpha=0.23, beta=0.5, L=40, q/pi=1, eta=0.1, OBC, Sz=0`；蓝线是历史 stored TEBD，橙点是 11 个 accepted CV anchors，横轴为 `omega/J1`。
- **b — relative difference**：同一 11 行 source CSV 的相对差，图内标注最大 6.40%。
- **c — PASS gates**：`peak bracket`、`weight window`、`peak budget`、`weight budget` 四个门均为 PASS。

图源 `figures/round43_fig8_final_20260806_v2.source.csv` 只有 11 行比较表，不是完整谱矩阵。CV 的归一化为 `O_q=(1/sqrt(L))*sum_j exp(iqj) Sz_j`、强度 `-Im(G)/pi`；TEBD 使用 historical q=pi slice 的 stored raw 除以 `pi`，并采用 center-source 与 37-site spatial window 的有限 OBC 近似。该 CV–TEBD 验证仅限这个 q、尺寸、参数和归一化协议，不能外推到所有 q。

低频 5 点的 `cv_residual`/`relative_residual=0` 是原始 point CSV、source-run `metrics.csv` 和 manifest 中的 reported value，不是组装时缺失值填零的证据；同样不能解释为数学残差严格等于零。source-run 的 `cv_dsf_resumable.jl` SHA256 与 manifest 一致（`ce3fddb48ad141387d0276c73b982e0fb229b037123ff13e10bc3da75e828d61`），其非负截断后的 residual 报告仍需要独立稳定残差复核，原始 accepted/validator 记录不改写。

## minimal full-q 三组 `dt` 对照

图像 `figures/fullq_minimal_eta020_20260808.png` 的实际面板分组为：

- **a** `Uniform chain alpha=1, beta=1`；**b** `Weak coupling alpha=1, beta=0.1`；**c** `Agreement point alpha=0.23, beta=0.5`：三张 raw full-q heatmap。
- **d、e、f**：分别对应 a、b、c 的 q=pi `Delta t=0.025` 与 `Delta t=0.0125` 收敛切片；图内报告 peak/weight drift。

`scripts/autoresearch_v5/plot_minimal_fullq_campaign.py` 明确读取每个点的 coarse/refined `spectrum_raw.csv`：上排 heatmap 使用 refined 矩阵并按 refined positive maximum 归一化，下排使用 coarse/refined 的 q=pi 行。六个 raw CSV 均无表头、形状为 121 rows × 301 columns；manifest 给出 `q_points=121`、`omega_points=301`、`omega_max=3.0`、`space_window=18`。三组均为 `tmax=30`、`dt=0.025/0.0125`；uniform 使用 `eta=0.1`，weak/agreement 使用 `eta=0.2`。

三组 handoff/crosscheck 均为 pass，且 six single runs 与 three dt pairs pass。不同 `eta` 不是不同 `dt`；因此 uniform 与 weak/agreement 之间的谱线宽度、弱峰和展宽不能直接作定量比较。raw 矩阵中的负值是保留并显示的谱值，不是缺失码。

## CSV 元数据约定

完整表头、行数、单位说明、缺失字段和每个选定文件的 SHA256/字节数见 audit JSON 的 `csv_schema` 与 `selected_files`。关键约定如下：

- `omega`/`omega/J1` 使用 `J1=1` 的无量纲频率；`q_over_pi` 为无量纲动量。
- `relative_delta`、`relative_residual`、权重相对变化和负权重 fraction 为无量纲诊断量；`solve_seconds` 为秒，`solution_maxdim` 为配置整数。
- full-q summary CSV 的 uniform 行中 `beta_over_local_gap` 为空，是不适用字段，不应填 0。
- full-q raw 矩阵没有列名；其轴和单位来自对应 manifest/plotter，而不是 CSV 表头。未观察到 `NaN`、`NA`、`null` 或 `None` 缺失 token。

## 可复核性与限制

选定来源包括图 PNG、source/QA sidecar、handoff summary、crosscheck、per-run manifest、实际 CSV 以及相关 plotter/source-run diagnostics；没有遍历或复制全部时域 correlation 和大状态文件。来源链支持“指定实例的 CV–TEBD Agreement”和“三组 full-q 的 `dt`/`dt/2` 通过”这两个局部结论，不支持无条件的全动量 CV 验证、所有展宽下的谱宽比较或全谱/热力学收敛声明。
