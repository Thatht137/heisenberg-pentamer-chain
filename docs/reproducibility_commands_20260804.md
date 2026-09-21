# 复算与验收命令

以下命令从项目根目录运行；绘图只使用 Python/matplotlib。

## 本地回归与静态图

```powershell
.venv\Scripts\python.exe -m unittest discover -s scripts\autoresearch_v5 -p "test_*.py"
.venv\Scripts\python.exe scripts\autoresearch_v5\plot_paper_static_figures_20260804.py
.venv\Scripts\python.exe scripts\autoresearch_v5\render_research_progress.py
.venv\Scripts\python.exe scripts\autoresearch_v5\audit_paper_static_and_report_20260804.py
```

## 已完成的七点 CV 验收

```powershell
.venv\Scripts\python.exe scripts\autoresearch_v5\validate_cv_run.py `
  --run-dir results\autoresearch_v5_20260805\round40_qpi_cv_high150_fetch\cell-l40-qpi-high-150 `
  --output results\research_progress\recheck_high150_validator.json

.venv\Scripts\python.exe scripts\autoresearch_v5\assemble_qpi_cv_anchors.py `
  --run-dir results\autoresearch_v5_20260730\round3_cv_L40_probe\cell-0001-L40-qpi-w020 `
  --run-dir results\autoresearch_v5_20260802\round21_cv_triplet_warmstart\cell-0002-L40-qpi-w025-w035 `
  --run-dir results\autoresearch_v5_20260803\round31_qpi_cv_extension_completed_cells_20260804\cell-l40-qpi-high-055 `
  --run-dir results\autoresearch_v5_20260803\round31_qpi_cv_extension_completed_cells_20260804\cell-l40-qpi-high-100 `
  --run-dir results\autoresearch_v5_20260805\round40_qpi_cv_high150_fetch\cell-l40-qpi-high-150 `
  --output-dir results\autoresearch_v5_recheck\accepted7
```

当前 accepted-only 频点为 `0.20,0.25,0.30,0.35,0.55,1.00,1.50`。`omega=0.05` retry 必须单独运行 validator，并预期因 residual 超门得到 `fail`；不得把该目录传给 accepted-only 组装器。

## bounded Fig.8 与交付审计

```powershell
.venv\Scripts\python.exe scripts\autoresearch_v5\analyze_cv_tebd_crosscheck.py `
  --cv-dir results\autoresearch_v5_20260805\round40_qpi_cv_anchor_assembly_accepted `
  --tebd-dir results\autoresearch_v5_20260803\round26_qpi_tebd_production\cell-alpha023-qpi-dt00125-t30 `
  --output results\autoresearch_v5_recheck\cv_tebd_accepted7\cross-method-check.json

.venv\Scripts\python.exe scripts\autoresearch_v5\plot_fig8_bounded_seven_point_20260805.py
.venv\Scripts\python.exe scripts\autoresearch_v5\audit_bounded_delivery_20260805.py
.venv\Scripts\python.exe scripts\autoresearch_v5\build_source_data_inventory_20260804.py
```

预期交叉标签为 `NotEvaluable`，分析器退出码为 `2`（incomplete）：七个共享点可以比较，但 CV 未包围 `omega≈0.05` 主峰。退出码 `2` 不是程序崩溃；必须同时检查已生成 JSON 的标签和覆盖门。production 绘图入口仍保留为拒绝式门控；除非全部覆盖门通过，否则 `plot_dynamic_figures_production.py` 必须拒绝契约。

`plot_fig8_bounded_seven_point_20260805.py` 会重建当前 Fig.8 master；需要保留旧导出时，应先在独立工作副本中运行。服务器 run 和 accepted-only 目录始终使用新目录，禁止覆盖。

## Round43 终态交接

round43 回传到新目录并完成双端 SHA-256 后，使用单一入口执行 validator、五点网格核对、11 点 accepted-only 组装和 CV–TEBD 分流：

```powershell
.venv\Scripts\python.exe scripts\autoresearch_v5\finalize_round43_handoff.py `
  --round43-run results\autoresearch_v5_20260806\round43_qpi_cv_lowfreq_desc_fetch\cell-l40-qpi-lowfreq-desc `
  --output-root results\autoresearch_v5_20260806\round43_handoff_final_v2
```

交接完成后，按摘要中的 `next_figure_command` 生成与证据等级一致的 Fig.8：

```powershell
.venv\Scripts\python.exe scripts\autoresearch_v5\plot_fig8_round43_branch.py `
  --handoff-root results\autoresearch_v5_20260806\round43_handoff_final_v2 `
  --output-base figures\round43_fig8_final_20260806_v2
```

绘图器只使用 Python/matplotlib，按 89 mm 单栏合同输出 SVG、PDF、PNG、TIFF、source CSV、来源 sidecar 和 QA JSON。若终态仍为 bounded，图内必须保留 `bounded · NotEvaluable` 与未关闭的门，不得生成 production 表述。

退出码与证据等级固定为：`0 = production_ready / Agreement`，`2 = bounded / NotEvaluable`，`1 = bounded_disagreement` 或执行错误。只有 `handoff_summary.json` 同时给出 `production_ready=true` 和 `tag=Agreement` 时，才允许更新 production 动态论断。任一 validator、checksum、五点网格或 residual 失败都会在组装前停止。

## 精简 full-q 回传与验收

每个终态 cell 先生成远端 checksum 预览；预览只接受六个预注册 cell 名，且本地目标必须不存在：

```powershell
.venv\Scripts\python.exe scripts\autoresearch_v5\fetch_fullq_tebd_run.py preview `
  --cell-id fullq-uniform-dt025 `
  --destination results\autoresearch_v5_20260807\minimal_fullq_fetch\fullq-uniform-dt025 `
  --output results\research_progress\fullq-uniform-dt025-fetch-preview.json

.venv\Scripts\python.exe scripts\autoresearch_v5\fetch_fullq_tebd_run.py fetch `
  --preview results\research_progress\fullq-uniform-dt025-fetch-preview.json `
  --destination results\autoresearch_v5_20260807\minimal_fullq_fetch\fullq-uniform-dt025 `
  --output results\research_progress\fullq-uniform-dt025-fetch-receipt.json `
  --confirmed

.venv\Scripts\python.exe scripts\autoresearch_v5\validate_fullq_tebd_run.py `
  --run-dir results\autoresearch_v5_20260807\minimal_fullq_fetch\fullq-uniform-dt025 `
  --output results\research_progress\fullq-uniform-dt025-validator.json
```

六个 cell 全部非覆盖回传后，统一执行三组 `dt/dt2` handoff 和论文图：

```powershell
.venv\Scripts\python.exe scripts\autoresearch_v5\finalize_minimal_fullq_handoff.py `
  --campaign-dir results\autoresearch_v5_20260807\minimal_fullq_fetch `
  --output-dir results\autoresearch_v5_20260807\minimal_fullq_handoff

.venv\Scripts\python.exe scripts\autoresearch_v5\plot_minimal_fullq_campaign.py `
  --handoff-dir results\autoresearch_v5_20260807\minimal_fullq_handoff `
  --output-base figures\paper_fullq_minimal_20260807
```

validator 强制检查 `t=0`、variance/site、`Sz=0`、raw 负谱权、矩阵形状、终态与 checksum。handoff 强制三个物理点各自通过 `dt=0.025/0.0125` 的峰漂移和低频权重门；任一失败时绘图器必须拒绝。
