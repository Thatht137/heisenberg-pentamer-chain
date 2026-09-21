# Round43 q=pi 低频 CV 计算安排

## 目标

关闭 production 动态门所缺的低频覆盖，同时保持 `relative residual <= 1e-5` 不变。研究范围仅为 `0 <= alpha,beta <= 1`，排除负 alpha 和参考论文 Fig.9。

## 失败诊断

两次 `omega=0.05` 运行都从 source 向量重新开始，参数和基态 sweep 轨迹完全相同，因此 retry 没有形成新的 warm-start。旧五点结果的 residual 随频率降低单调变差：

| omega | residual | 状态 |
|---:|---:|---|
| 0.20 | 7.7978e-6 | 通过 |
| 0.15 | 9.2445e-6 | 通过 |
| 0.10 | 1.0714e-5 | 拒绝 |
| 0.05 | 1.2289e-5 | 拒绝 |
| 0.00 | 1.3238e-5 | 拒绝 |

L=20 cutoff 对照中，CV cutoff 从 `1e-12` 收紧到 `1e-14` 后 residual 从 `4.67e-5` 降至 `5.62e-6`。新任务据此同时改变求解顺序和数值截断精度。

## 阶段 A

- 物理参数：`alpha=0.23, beta=0.5, L=40, q=pi, eta=0.1, OBC, Sz=0`。
- 求解顺序：`omega=0.20 -> 0.15 -> 0.10 -> 0.05`。
- 资源：单个 Julia，4 Julia threads，BLAS 1 thread，`nice=15`。
- 精度：`Ddmrg=320, Dcv=1200, nsweeps=24, cv_cutoff=1e-16`。
- ETA：4–8 小时；启动后 6 小时只读检查一次，不短间隔轮询。
- 阶段终态：预期 `partial 4/5`，保存 checkpoint 和 checksum。

只有阶段 A 四个点全部不超过 `1e-5`，且 `omega=0.05` 已形成有效 checkpoint，才进入阶段 B。

## 阶段 B

- 从阶段 A 的 `omega=0.05` solution checkpoint 恢复。
- 只计算 `omega=0.00`。
- ETA：1–3 小时；启动后 2 小时只读检查一次。
- `omega=0.00` residual 超门时终止 production 路径，保留 bounded 结论，不降低门槛。

## 终态验收顺序

1. 远端 `checksums.sha256`。
2. 非覆盖回传到新的本地目录。
3. 本地 checksum。
4. `validate_cv_run.py`。
5. 仅通过后更新 accepted-only anchor。
6. 重新执行 CV–TEBD peak/weight 分析。
7. 更新 bounded manuscript 和研究进展 HTML。

## 完成判据

- 五个低频点全部自然终态且 `relative residual <= 1e-5`。
- accepted-only 网格覆盖 `omega=0.00–1.50`。
- `omega≈0.05` 的 CV 与 TEBD 共享峰不位于网格端点。
- peak 位置差和 `[0,1.5]` 积分权重差同时通过既定预算。
