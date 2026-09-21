# 8 月 10 日计算与 HTML 交付计划

更新：2026-08-07 CST。交付范围仅 `0 <= alpha,beta <= 1`，排除负 `alpha` 与参考 Fig.9。未经用户明确授权，不向 `paper/` 写入论文正文。

## 当前基线

- 论断证据覆盖：`12/12` 已支持或有明确边界；C10/C11 采用 bounded 表述。
- round43 的 `q=pi` 生产动态门已关闭：`production_ready=true`、`tag=Agreement`、accepted11；bounded 七点分支独立保留。
- Fig.1–5 已具备四格式、sidecar、哈希和视觉 QA。
- Fig.6/7 的旧资产仍为 exploratory/pilot；Fig.8 同时保留 production Agreement 与 bounded 对照。
- high-150 已完成远端/本地 checksum、非覆盖回传和 validator；`omega=0.05` retry 正常退出但 residual=`1.17670e-5>1e-5`，已由 validator 拒绝。
- 严格 `q=pi` TEBD 的 Agreement 只适用于 `alpha=0.23,beta=0.5,L=40`：`dt=0.025/0.0125`、`tmax=25/30`、`maxdim=96/320` 已通过；`q=0` 与镜像动量尚未测。
- CV accepted 频点为 `0.20/0.25/0.30/0.35/0.55/1.00/1.50`；共享点最大差 `6.40%`、共享窗积分差 `1.53%`。低频覆盖门未关闭，所以总体仍为 `NotEvaluable`。
- round43 阶段 A/B、双端 checksum、非覆盖回传、validator、accepted11 和 CV–TEBD 分流均已完成。
- 2026-08-07 已启动精简 full-q 任务：三个代表点各做 `dt=0.025/0.0125`；本地回传、validator、handoff、绘图和合成端到端测试已完成准备。
- 独立 bounded manuscript 已生成并通过 QA；round43 成败不改变 8 月 10 日 bounded 交付日期。

## 日期与止损线

| 日期 | 计算 | 本机交付 | 决策门 |
|---|---|---|---|
| 8/04 | high-150 继续；已启动唯一受限 `omega=0.05` smoke | Methods/Results/Discussion、Fig.6–8 契约、源数据与补充材料清单 | 仅此一个 4 线程并行例外；禁止第三个 Julia |
| 8/05 | 两个任务分别终态后执行 checksum、非覆盖回传、validator、accepted-only 组装 | 重跑交叉分析与报告 | high-150 超过 24 h 先做只读诊断，再由作者决定继续/停止 |
| 8/06 | round43 阶段 A；四点全过后启动阶段 B `omega=0.00` | bounded manuscript、Fig.8 双分支和当前状态报告 | residual 门不降低；阶段 A 失败即停止 production 路径 |
| 8/07 | round43 已完成；启动精简 full-q 第一个 cell | 完成 full-q 回传/validator/handoff/绘图工具和文档统一 | full-q 每点必须通过单 run 与 `dt/dt2` 双门 |
| 8/08 | 只延续预注册 full-q 六 cell，不扩大扫描 | 完成 source-data、checksums、补充材料与复算命令 | 每张图逐项回溯；失败 cell 不自动升级 |
| 8/09 | 仅处理确定性错误 | 完整 HTML 审阅稿，目标 22:00 CST | 作者审阅科学措辞 |
| 8/10 | 不启动新重计算 | 最终 HTML、图表包、数据包和验收记录，目标 22:00 CST | 是否迁移到 `paper/` 需单独授权 |

## high-150 终态顺序（已完成）

1. 只读确认 supervisor 与 high-150 自然结束，且远端 manifest/status 完整。
2. 在远端执行 `sha256sum -c`；失败则不下载为 accepted 数据。
3. 回传到一个不存在的新目录，禁止覆盖既有 run。
4. 本地复核 SHA-256，并运行 `validate_cv_run.py`。
5. 用 `assemble_cv_accepted_anchors.py --run-dir ...` 组装 accepted-only 七点表，失败 low cell 永久隔离。
6. 用 `analyze_cv_tebd_crosscheck.py` 重算 peak、weight 和覆盖门。
7. 用 `finalize_round31_high150_report.py` 仅依据 validator、receipt、manifest 和 cross-check 更新报告。
8. 重跑 HTML、静态图 QA、source-data inventory 与全部 Python 测试。

## 动态准入规则

- CV residual `<=1e-5`，基态方差/格点 `<=1e-8`。
- TEBD 的 `dt`、`tmax`、`maxdim` 与 Fourier 重算通过。
- CV 网格包围 TEBD 主峰，并覆盖预注册的 `[0,1.5]` 主要积分窗。
- CV/TEBD 主峰差 `<=0.1 J1`，主要积分权重差 `<=15%`。
- 任一失败：结果保持 `pilot`、`bounded` 或 `NotEvaluable`，不得通过作图或措辞升级。

## 8 月 10 日最低交付

1. `results/research_progress/report.html`：当前完整审阅稿。
2. `results/research_progress/report_history.html`：不可丢失的完整事件记录。
3. `figures/`：Fig.1–5 production/bounded 主图；Fig.6–8 按最终证据等级交付。
4. `results/research_progress/source_data_inventory_20260804.*`：源数据与 SHA-256。
5. `docs/supplementary_materials_plan_20260804.md`：补充材料结构和未通过结果审计。
6. `docs/reproducibility_commands_20260804.md`：本地与远端复算顺序。

## 人工介入点

- 接受 C11 的有限尺寸措辞：“当前正区有限尺寸数据未见可验收内部 crossing”。
- high-150 与 low-005 已终态；round43 已按用户授权启动，无需人工连接服务器。
- bounded 交付已独立完成；round43 只决定动态部分是否可从 `NotEvaluable` 升级，不影响 bounded 包交付。
- 审阅 HTML 后明确授权是否迁移到 `paper/`。
- 投稿前确认期刊、作者顺序、数据仓库和署名信息。
