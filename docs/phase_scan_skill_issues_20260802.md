# 正区相图扫描问题记录

更新时间：2026-08-02

本记录只针对 `alpha>=0`、`beta>=0` 的 1x5 五聚体相图扫描，不包含负 alpha。

## 已确认的问题

### 1. 域边界点被当作内部 crossing 未决点

`alpha=0` 是本次正区扫描的控制轴边界，也是局域解耦点。双初态半差在这里可能反映简并分支，而不是统计噪声。上游 `finite_size_crossing` controller 没有域边界语义，会把这个点的 `sign=0` 直接升级为 `HUMAN_REQUIRED`。

当前处理：项目 guard 增加 `axes.control.edge_controls=[0.0]`，内部 crossing 只使用 `alpha>0`，边界点保留在 `edge_entries` 中单独审计。

建议：支持 `edge_controls` 或 `exclude_from_bracket`，并在最终报告中同时输出内部结论和边界点状态。

### 2. 无 bracket 时过早停止

上游 controller 在第一个无 bracket slice 后就返回 `HUMAN_REQUIRED`，没有先汇总所有 beta slice 的同号/不确定证据。这样会把“固定区间内无内部 crossing”和“还有未检查 slice”混为一个问题。

建议：先完成所有当前 slice 的确定性分类，再根据整体结果决定 `NO_SIGNIFICANT_CROSSING`、`INCONCLUSIVE` 或尺寸升级选项。

### 3. Windows 本地缺少 `uv`

本机没有 `uv` 可执行文件，离线环境也无法直接下载。项目提供了 `phase_diagram_windows_controller.py` 作为标准库兼容入口，能完成同一 controller 的只读检查和 guard。

建议：随包提供无依赖入口，或在 `uv` 不可用时明确记录等价运行时和版本，而不是让任务在第一条 controller 命令处失败。

### 4. 直连服务器不适配 Slurm 默认流程

本服务器 scheduler 为 `none`，实际流程是 `flock + nohup + PID + run_status.json`。SLURM 的 `squeue/sacct/sinfo` 检查不适用；需要自定义 profile 和逐文件上传，应为直接运行方式记录等效的参数与验收条件。

建议：为 `scheduler=none` 增加锁、PID、状态心跳、断点恢复和逐 cell fetch 的标准接口。

### 5. 启动脚本中的哈希容易过期

标准文档或源码变化后，旧启动脚本中的 `standard_sha256` 会使所有 cell 正确拒绝。此次提交前发现工作区文档 hash 已从旧值变为 `4f00f333...`，必须重新生成启动脚本和上传清单。

建议：由上传工具从清单动态注入哈希，并在提交前强制做一次本地/远端 dry-run。

### 6. 长批次的心跳粒度过粗

直连 runner 只在 cell 开始和批次结束时更新 `run_status.json`。单个 L=80 cell 可能运行数分钟，监控期间容易误判为卡死。

建议：每个 cell 至少写入当前初态、sector、sweep 和最后更新时间；监控器按更新时间和子进程树判断活跃度。

### 7. 计算成本估计没有按尺寸和初态分层

扩展批次前四个点较快，但 `beta=0.05, alpha=0.125, L=60` 的单个双初态 cell 已明显超过前几点评估时间。当前 run spec 只给出统一 `budget=32`，没有记录预估 wall time 或按 `L/init_mode` 的成本模型。

建议：提交前用至少一个代表性的 L=60 和 L=80 探针估算每 cell 成本，并在 direct profile 中输出预计完成时间和剩余磁盘占用。

### 8. 长批次结果回传缺少断点接口

整批 `scp -r` 在服务器无外网、连接偶发超时的条件下不可靠；失败时难以区分已完整文件和半个目录。此次新增按 `run_status.json` 的 completed 列表逐 cell 回传，并在远端和本地分别执行 checksum；未完成 cell 不会被下载或纳入观察量。

建议：为 direct-run 提供按 cell manifest 的可恢复 fetch，临时目录验证通过后再原子移动到正式结果目录。

### 9. Windows 无 profile 模式不保证 PowerShell 哈希命令可用

后台 `powershell -NoProfile -NonInteractive` 未自动加载 `Get-FileHash`，导致同一回传脚本在前台可运行、后台 checksum 阶段失败。项目已改用 .NET `SHA256` 标准库，避免依赖 PowerShell 模块自动加载。

建议：校验脚本只依赖标准库，或在启动时显式导入所需模块并记录运行时。

### 10. 自动收尾必须区分部分结果和最终结果

扩展批次是 60 个新 cell；前若干 cell 回传后不能直接运行最终 guard 或更新完成状态。当前收尾器只有在远端 `run_status.status=success` 且 60 个 cell 均回传后，才执行 merge、guard、summary 和 HTML 渲染。

建议：把“部分 fetch”“完整 fetch”“最终科学验收”做成三个不可混淆的状态，并把每个状态写入 durable log。

### 11. 计算成功不等于科学验收成功

`mesh-cell-0035` 的两个 Julia 子进程都正常返回，截断误差也通过，但两种初态的 `variance/L` 超过 `1e-8`，因此 cell manifest 必须是 `accepted=false`，批次在该点停止。原始 32-sweep 目录已归档到 `cells_failed/`，并按固定统计上限用 64 sweeps 恢复。

建议：把资源/程序返回码和科学 acceptance 分成两层状态；允许在保留失败证据的前提下按 policy 的统计倍率恢复单 cell，恢复成功后再从下一个 cell 继续。

### 12. 上传器硬编码旧批次，且跨 shell 转义脆弱

现有 `upload_phase_bundle.ps1` 固定读取 round17 清单，不能安全复用于 round19；第一次恢复上传因此在旧文档 hash 校验处停止。Windows PowerShell 拼接远端 bash 条件命令时，未使用参数数组也会造成 `$` 和引号被本地 shell 提前解释。

当前处理：新增 `upload_phase_mesh_bundle.ps1`，从本轮清单动态读取文件和远端根目录，上传前做本地 hash 校验，上传后逐文件远端 hash 校验；远端操作改用参数数组和明确的单 cell 归档命令。

建议：上传器必须参数化 run/manifest，禁止固定历史路径；跨 shell 命令应提供结构化参数接口或内置 dry-run，并把清单 hash 与目标批次绑定。

### 13. 统一 32 sweeps 预算在不同尺寸和参数点不稳定

本批次先后在 `L=60`、`L=80` 和 `L=40, alpha=0.125, beta=1.0` 触发科学验收失败。0049 的两个初态都正常结束且截断误差通过，但 `Sz=1` 方差约 `2.60e-8`，domain 的 `Sz=0` 方差约 `1.41e-8`，结构因子半差 `1.086e-4`，超过固定门限。随后 0050 在 `L=60, alpha=0.125, beta=1.0` 出现更严重的初态分支：domain 的 `Sz=0` 方差约 `5.86e-7`，结构因子半差约 `5.26e-2`；0051 在 `L=80` 仍有 domain `Sz=0` 方差约 `1.93e-7`、结构因子半差 `6.32e-3`。说明失败由收敛/初态一致性引起，而非单纯随系统尺寸单调变化。

当前处理：每个失败 cell 保留原始目录，预算按固定上限恢复为 64 sweeps，不改变方差阈值或误差地板。

建议：统计预算应允许由探针或 cell 级 acceptance 自适应升级，并在 run spec 中显式记录 `base_budget -> recovery_budget`；不能只按 L 预设一个统一 sweeps 值。

### 14. 有限但很大的 observable error 仍可被标记 accepted

0051 在 64 sweeps 下通过了方差和截断误差检查，但两个初态结构因子半差约 `6.05e-3`；manifest 的 `error` 仍约 `0.00605`，远高于 `1e-4` floor，当前 acceptance 仍将其标记为 `accepted=true`，因为只检查误差是否有限。该点不应直接用于精确边界估计，至少应由 guard 标记为高不确定性。

建议：把 `observable_error_max` 纳入 cell acceptance 或 phase guard 的硬门槛，区分“可用于粗图的 accepted”与“可用于边界拟合的 precision-accepted”。

### 15. 直连 SSH 偶发 banner 超时会打断单次回传

结果回传在服务器继续运行时遇到 `Connection timed out during banner exchange`，该次 fetch 失败但远端 batch 未受影响。当前收尾器会保留批次并在下一轮重试，避免把网络故障误判为计算失败。

建议：direct-run fetch 应把 SSH 建连失败单独分类，采用指数退避和连接次数/时间上限；状态日志需区分 `remote_compute`、`fetch_retry` 与 `scientific_failure`。

## 已采用措施

- 不把 `pgrep -f` 结果当成冲突证据，改用 PID 文件、锁文件和精确进程树。
- 新批次仅上传 12 个必要文件，不上传 controller、state、SSH 配置或本地认证信息。
- 远端先执行 Julia 1.12.3 smoke 和单 cell dry-run，再启动 60-cell 批次。
- 所有结果必须以 manifest、checksum 和本地 observations 为科学证据。
