# 1x5 五聚体论文图件计划

更新：2026-08-07。范围固定为 `0 <= alpha,beta <= 1`；负 `alpha` 与参考论文 Fig.9 永久排除。绘图后端固定为 Python/matplotlib。

## 总体原则

- 复现参考论文的证据角色和阅读顺序，不照搬 1x4 的物理结论。
- 主图必须有源数据、生成脚本、SVG/PDF/PNG/TIFF、SHA-256 和 `.sources.json`。
- `pilot`、`exploratory`、`bounded` 与 `production` 是不同等级，排版不能提升证据等级。
- 动态图只有在 CV、TEBD 和覆盖门均通过后才能标为 production。

## 图件状态

| 图 | 核心问题 | 当前状态 | 生产准入 |
|---|---|---|---|
| Fig.1 | 五聚体结构、局域多重态与低能投影 | manuscript master | `paper_fig1_model_local_multiplets_20260804.sources.json` |
| Fig.2 | 正 `alpha` 能级流和 `q=pi` 选择定则 | manuscript master | `paper_fig2_level_flow_qpi_filter_20260804.sources.json` |
| Fig.3 | 正区是否出现可验收内部 crossing | bounded manuscript master | `paper_fig3_positive_groundstate_diagnostics_20260804.sources.json` |
| Fig.4 | 有限尺寸低能标度是否符合 `c=1` 有效链 | bounded manuscript master | `paper_fig4_entanglement_spectrum_20260804.sources.json` |
| Fig.5 | 有效链连续谱与局域多重态如何共存 | manuscript master | `paper_fig5_effective_chain_selection_rules_20260804.sources.json` |
| Fig.6 | 全动量谱如何从均匀链演化到五站点折叠 | production 计算中 | 三个代表点均需单 run 与 `dt/dt2` 门通过；raw 负谱权不得隐藏 |
| Fig.7 | `q=pi` 切片与全动量谱的时间步稳健性 | production 计算中 | 三个代表点的峰漂移 `<=0.05 J1`、低频权重漂移 `<=5%` |
| Fig.8 | 有效连续谱、局域通道与数值谱如何对应 | production Agreement；bounded 对照保留 | round43 accepted11 已包围主峰并覆盖 `[0,1.5]`；结论仅限当前 `alpha,beta,L,q` |

## Fig.6--8 最终契约

生产入口为：

```powershell
.venv\Scripts\python.exe scripts\autoresearch_v5\plot_dynamic_figures_production.py `
  --contract <production-contract.json> `
  --output figures\paper_fig<N>_<name>_YYYYMMDD
```

示例契约 `docs/dynamic_figure_contract.example.json` 故意处于 blocked 状态，必须被脚本拒绝。生产契约必须满足：

1. `status=production_accepted`。
2. `cv_residual_pass`、`tebd_convergence_pass`、`peak_bracketed`、`major_window_covered`、`cross_method_gate_pass` 全为 true。
3. 每个源数据文件提供真实路径与 SHA-256。
4. Fig.6/7 输入为未经平滑和裁剪的矩阵；Fig.8 输入含 CV、TEBD、continuum 三类 CSV。
5. 图注列明 `L`、边界条件、`dt/tmax/maxdim`、`eta`、频率窗和误差定义。

round43 已在 `alpha=0.23,beta=0.5,L=40,q=pi` 补齐 `omega=0.00--0.20`，与既有频点组成 accepted11；validator、主峰包围、`[0,1.5]` 覆盖和 peak/weight 门均通过，因此该实例为 production Agreement。旧七点与失败 `omega=0.05` retry 继续作为 bounded/失败路径保留，不能覆盖或混入 accepted11。其他动量由 2026-08-07 精简 full-q 任务补算，不能用单一 `q=pi` 结果替代。

精简 full-q 图的固定合同为 183 mm 双栏、2x3 quantitative grid：上排三个代表点的 raw `S(q,omega)` 热图，下排同点 `q=pi` 的 `dt/dt2` 切片。热图按各点正峰归一化，但使用以零为中心的发散色标显示负振铃；均匀链叠加精确两自旋子边界，只有 `beta/Delta_loc<=0.65` 的点叠加五站点折叠有效链边界。

## 图注边界

- Fig.3：当前正区有限尺寸数据未给出可验收内部 crossing，不等同于证明整个热力学区域只有一个相。
- Fig.4：匹配尺寸校准支持 `c=1` 图景，不把裸拟合写成无偏中心荷。
- Fig.6/7：在六个 full-q run 与三组 `dt/dt2` 门关闭前，旧图仍只能标为探索或 pilot。
- Fig.8：production Agreement 只限 round43 的 `alpha=0.23,beta=0.5,L=40,q=pi`；七点 bounded 图与失败 `0.05` 继续作为独立审计对照。

## 最终 QA

图宽采用单栏约 89 mm 或双栏约 183 mm；正文/刻度在最终尺寸下保持 5–7 pt；面板标签统一；SVG/PDF 文本可编辑；颜色不作为唯一编码；全部 quantitative panel 可回溯到 CSV 或原始矩阵。
