# 2026-08-02 服务器与任务审计

审计对象：`USER@server.example.org:6000`，主机 `compute-node`，项目目录 `/home/USER/code/1x5_Heisenberg_Pentamer`。

## 通过项

- SSH BatchMode 连接通过，账户为 `USER`。
- Julia `1.12.3` 可执行。
- `using ITensors, ITensorMPS, KrylovKit` smoke test 输出 `ITENSOR_SMOKE_OK`。
- 服务器 `Project.toml` SHA-256：`39e917d3ca9615132999b4ae6a9731e8b592454267e38b5779423e76a8d2dd7e`。
- 服务器 `Manifest.toml` SHA-256：`37a53ffd73db57b9db9c4ce11f6265a9a41ac2035dc421b01f9a633d893ba12c`，与本地一致。
- `/home` 总容量约 `3.6 TiB`，可用约 `707 GiB`，已用 `80%`；项目结果目录约 `33 MiB`。
- 节点内存总量 `251 GiB`，可用约 `245 GiB`；当前负载 `0.21, 0.11, 0.09`。
- `pgrep -x julia` 无输出；当前没有正在运行的 Julia 计算任务。
- 本地回传的 CV 资产有 `5` 个 manifest、`5` 个 checksum 文件，`45/45` 条文件校验通过；其中 `4` 个结果状态为 success，`L=20, cv_cutoff=1e-12` 按既定残差门槛保留为收敛失败。

## 需要记录的事实

- 服务器项目是直连同步工作副本，没有 `.git` 元数据；因此后续 provenance 必须使用源码 SHA-256、`Project.toml/Manifest.toml` 哈希和 run 清单，不能依赖远端 Git commit。
- 服务器已有 CV 结果为 `round1_cv_oracle`、`round2_cv_cost_probe` 和 `round3_cv_L40_probe`；没有 `round4_cv_resume_oracle` 目录，也没有现成 `checkpoint_latest.jld2`。其中 L=20 的 `cutoff=1e-12` 失败点不能用于生产结论，但可作为收敛序列的负对照。
- 因此明日的 L=40 warm-start / 跨进程恢复必须从一个新的唯一 run 目录开始，不能覆盖 `round3_cv_L40_probe`。
- 服务器结果中已有正区 `round19_phase_diagram_positive_mesh`，但本次审计不重新下载或修改它。

## 环境验证结论

环境满足后续数值探针的前置条件，磁盘和内存均不是当前限制；主要操作风险是可恢复 CV run 尚未在服务器落地。下一步为新建独立 `round20_cv_resume_warmstart` 目录，先跑一个低频率、单点恢复 smoke，再扩展到三个相邻频率。仍不做负 `alpha`，不扩大相图，不提交 L=80 长作业。
