# Stage 3 静态收敛预检（2026-09-19）

这是对既有 `pilot_fetch_20260914_2243` 产物的只读预检，不是新的计算，也不是完整收敛验收。来源为：

`results/autoresearch_v5_20260913/negative_phase_independent_pilot_fetch_20260914_2243/negdiag-a01000-b02500-L080/`

`results/autoresearch_v5_20260913/negative_phase_independent_pilot_fetch_20260914_2243/negdiag-a01750-b02500-L080/`

四个运行目录的 `manifest.json` 均记录 `settings.cutoff=1e-11`、`settings.maxdim=1200`、`settings.nsweeps=64`。下表从各 `stdout.log` 的两个 64-sweep block 读取；block 顺序按 manifest 的 `sectors=["Sz=0","Sz=1"]`，`末步 ΔE` 是 sweep 64 与 sweep 63 能量差的绝对值。

| α | 初态 | 扇区 | 64 步 maxlinkdim 最大值 | sweep 64 maxlinkdim | 末步 ΔE |
|---:|---|---|---:|---:|---:|
| -0.100 | center | Sz=0 | 215 | 215 | 8.7830e-7 |
| -0.100 | center | Sz=1 | 209 | 187 | 4.6150e-10 |
| -0.100 | ferro_j2 | Sz=0 | 189 | 189 | 6.6064e-7 |
| -0.100 | ferro_j2 | Sz=1 | 209 | 187 | 4.6150e-10 |
| -0.175 | center | Sz=0 | 284 | 270 | 5.4821e-7 |
| -0.175 | center | Sz=1 | 228 | 207 | 3.9080e-14 |
| -0.175 | ferro_j2 | Sz=0 | 290 | 262 | 6.5421e-7 |
| -0.175 | ferro_j2 | Sz=1 | 228 | 207 | 3.9080e-14 |

结论仅限于预检事实：实际 `maxlinkdim` 未触及配置上限 1200，而两个 α 下 `Sz=0` 的末步能量变化仍约 `5.5–8.8e-7`；因此不能把本表当作完整收敛证明，也不预设 `cutoff` 是瓶颈。若继续 Stage 3，应先设计观测量和初态的收敛对照，再决定是否增加 bond dimension，而不是盲目加 χ。
