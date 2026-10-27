# Round43 计算记录与 bounded 结果

更新时间：2026-08-06 15:37 CST。范围固定为 `0<=alpha,beta<=1`，排除负 alpha 和参考 Fig.9；不修改 `paper/`。

## 计算参数

| 项目 | 值 |
|---|---|
| 任务 | `round43 q=pi CV`，阶段 B |
| 参数 | `alpha=0.23`，`beta=0.5`，`L=40`，`eta=0.1` |
| 顺序 | 阶段 A 已完成；阶段 B 只计算 `omega=0.00` |
| 精度 | `Ddmrg=320`，`Dcv=1200`，residual `<=1e-5` |

阶段 A 于 12:35:55 CST 自然结束为 `partial 4/5`，elapsed `11239.812 s`。远端 `checksums.sha256` 全部通过；四点 residual 均为 `0.0`，因此满足阶段 B 启动门。

## 阶段门控

1. 阶段 A 的四点记录和远端 checksum 已通过。
2. 阶段 B 必须自然结束并给出 `omega=0.00` residual `<=1e-5`。
3. 终态后依次执行远端 checksum、非覆盖回传、本地 checksum 和 `validate_cv_run.py`。
4. 任一点失败，保持 `bounded / NotEvaluable`，不组装 accepted-only，不降低 residual 门槛。

## 同步 bounded 交付

当前 bounded 版本已经独立完成：

- HTML：`results/research_progress/bounded_manuscript_20260806.html`
- Fig.8：七个 accepted CV 点与 TEBD 的 bounded overlay
- 交付审计：`10/10`
- 复算命令审计：`11/11`
- 源数据清单：`90` 条记录，low-005 失败点只保留在审计中
- 图注审计：`8/8`

当前 bounded 结论仅支持共享频率窗内的数值接近、五聚体有效 `S=1/2` 链机制、局域 `q=pi` 选择定则和弱二阶挫折；不支持完整 CV–TEBD Agreement、完整二维相图或热力学极限单相结论。

## 2026-08-06 终态交接

阶段 B 于 `16:04:56 CST` 成功结束，`status=success`、`5/5` 点、returncode `0`、elapsed `1733.08 s`，stderr 为空且无残留 Julia。omega=`0.20, 0.15, 0.10, 0.05, 0.00` 五点的 `relative_residual=0.0`；远端 `checksums.sha256` 22/22 通过。

结果以非覆盖方式回传到 `results/autoresearch_v5_20260806/round43_qpi_cv_lowfreq_desc_fetch_20260806_1815/cell-l40-qpi-lowfreq-desc`；本地 22/22 checksum 与 `validate_cv_run.py` 全部通过。`finalize_round43_handoff.py` 生成 `accepted11`，独立 CV–TEBD 交叉分析为 `status=pass`、`tag=Agreement`、`production_ready=true`，peak/major-weight 两个覆盖门通过。

最终 production 图为 `figures/round43_fig8_final_20260806_v2.{png,svg,pdf,tiff}`；独立 bounded HTML 仍保留七点、失败路径和 `NotEvaluable` 口径，不被 production 结果覆盖。范围仍固定为 `0<=alpha,beta<=1`，排除负 alpha 和 Fig.9。
