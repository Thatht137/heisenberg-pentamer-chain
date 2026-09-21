# Full-q 重规划：weak 点正性门失败后的处理

更新时间：2026-08-07（北京时间）  
范围：仅 `0 <= alpha,beta <= 1`；排除负 alpha 与参考 Fig.9；不修改 `paper/`。

## 当前结论

`fullq-weak-dt025` 的 TEBD/Fourier 执行正常，但原始负谱权占比为 `0.15728494`，超过严格门 `0.15`。旧结果、checksum、回传和 validator 证据全部保留，不覆盖、不降门槛。

本计划已启动首个唯一 cell `fullq-weak-eta020-dt025`；旧失败结果未覆盖。

## 推荐配置

新建独立输出批次，时间窗先采用 exponential `eta=0.20`。本地失败诊断显示，在 `q/pi=1.0--1.5`、`omega=0--2` 的小网格中，eta=0.20 的负权分数约为 `0.0179`，优于旧 eta=0.10；这不是生产验收结果，必须重新跑完整网格并通过全部门槛。

不推荐直接采用 sin²：同一局部诊断约为 `0.494`。eta=0.30 可作为 eta=0.20 失败后的第二候选，但需要重新评估谱峰展宽和 dt/dt2 一致性。

## 顺序安排与 ETA

| 阶段 | 工作 | 预计耗时 |
|---|---|---:|
| A | 新批次配置、哈希、远端 guard 和 smoke | 0.5--1 h |
| B | weak `dt=0.025, eta=0.20` 全网格生产 | 0.7--1.2 h |
| C | checksum、非覆盖回传、本地 validator | 0.25--0.5 h |
| D | weak `dt=0.0125, eta=0.20` 生产与验收 | 1.5--2.5 h |
| E | weak dt/dt2 交叉验收 | 0.25--0.5 h |
| F | agreement 两档 `eta=0.20` 生产、回传和 validator | 2.5--4.5 h |
| G | agreement 交叉验收、handoff、CV--TEBD 分流与最终图件 | 2--4 h |

全部顺利时约 **7--14 小时**；考虑服务器断网、回传重试或任一档重跑，按 **1--2 天** 安排。任何单 run 或 pair 门失败都立即停止，不进入下一阶段。

## 验收门

每个新 run 必须同时满足：

- `t0_included=true`；
- variance/site `<= 1e-8`；
- `Sz=0`；
- raw negative-weight fraction `<= 0.15`；
- 远端 checksum、非覆盖回传、本地 checksum 和独立 validator 全部通过。

每个 dt/dt2 pair 还必须满足：全局峰和 `q=pi` 峰漂移 `<= 0.05 J1`，低频谱权漂移 `<= 5%`。

## 启动条件

收到明确启动指令后，创建唯一 cell-id（例如 `fullq-weak-eta020-dt025`）并运行 eta=0.20 批次；旧 `fullq-weak-dt025` 目录永不覆盖。当前只安排首个 cell，后续仍按验收门逐档推进。
