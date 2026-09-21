# 负 α 区论文级实用收敛标准（V2）

> 日期：2026-08-29  
> 适用范围：`-1 <= alpha < 0`、`0 <= beta <= 1` 的静态相图与代表性动力学。  
> 背景：参考工作的作者确认当前 Hamiltonian、DMRG 方法与程序路线没有原则性问题；此前主要问题是负 `alpha` 区的方差门过严、sweep 预算过大。V2 将这一反馈转成可复现标准，不回写或删除 V1 失败证据。

## 1. 固定物理与数值设置

| 项目 | V2 设置 |
|---|---|
| 模型 | 1×5 自旋 `1/2` Heisenberg 五聚体链，`J1=1` |
| 区域 | `-1 <= alpha < 0`、`0 <= beta <= 1`；`alpha=0` 单独作为奇异边界 |
| 边界 | 有限开放链（OBC） |
| 尺寸 | 粗扫 `L=40,60`；最终边界使用 `L=60,80` |
| 扇区 | `Sz=0` 与 `Sz=1` |
| 初态 | `center` 与 `ferro_j2` 两个独立初态 |
| 结构因子 | `q in [0,pi]`，不少于 401 点 |
| 相界 | 主波矢重构 + 尺寸流/ratio 第二诊断；不能只凭热图命名相 |

## 2. V2 静态 cell 验收门

所有条件必须同时成立：

1. Julia/Python 正常退出，远端 checksum、非覆盖回传、本地 checksum 全部通过。
2. 两个初态都完成 `Sz=0` 与 `Sz=1` 计算，参数、Hamiltonian、尺寸和 sweep 数一致。
3. `variance_per_site <= 5e-8`。这是 V2 唯一主动放宽的核心数值门。
4. 最终截断误差 `<=1e-9`。
5. `abs(Sz0)<=1e-8` 且 `abs(Sz1-1)<=1e-8`。
6. 自旋隙 `>=-1e-8`；小负隙不能只用放宽方差解释。
7. 父 cell 的多初态能量一致性门通过，结构因子与主波矢均为有限值。
8. `q_peak`、dominant ratio 及完整 full-q 文件存在；失败记录不得携带伪 accepted 值进入边界拟合。

V1 的 `1e-8` 结果保留为 **strict subset**。V2 接纳必须写成 `accepted_under_practical_v2`，不能把旧 manifest 原地改成 `accepted=true`。

## 3. sweep 预算

| 用途 | 预算 | 规则 |
|---|---:|---|
| Stage B 粗扫 `L=40,60` | 保留原定 32/64 sweeps | 通过 V2 即可进入 coarse map；不因方差单独升级预算 |
| Stage C 边界 `L=60,80` | 64 sweeps | 只计算 bracket 端点和缺失中点 |
| 已存在 128-sweep 结果 | 保留 | 作为更高质量历史结果，但不作为新任务的默认预算 |

如果 64 sweeps 仍未通过 V2，则记为 `bounded/NotEvaluable`，不再用 128/256 sweeps 追逐单点。论文中报告该点及其对边界误差的影响。

## 4. 历史数据回放结论

本地对 Stage B 的 26 个父 manifest、18 个不同物理点进行了不改原文件的门槛回放：

| 方差门 | 可用物理点 | 仍不可用 | 解释 |
|---:|---:|---:|---|
| `1e-8` | 17 | 1 | 原严格标准 |
| `3e-8` | 17 | 1 | 没有增加物理点 |
| `5e-8` | 18 | 0 | 恰好释放 `alpha=-1,beta=.1,L=60` |
| `1e-7` | 18 | 0 | 不再增加物理点，只会优先选用更多低 sweep 版本 |
| `2e-7` | 18 | 0 | 同上，缺少额外收益 |

因此选择 `5e-8`，不使用更松的 `1e-7`。在已有 32/64 sweep 成对结果中，`q_peak/pi` 最大漂移为 0，但 dominant ratio 最大绝对漂移约 0.139。因此：

- 32 sweeps 足够做主波矢粗筛；
- ratio 不得仅凭 32 sweeps 定义最终边界；
- Stage C 的最终 ratio/尺寸流必须使用 64-sweep 的 `L=60,80` 数据。

回放证据：

- `results/research_progress/negative_variance_relaxation_audit_20260829.json`
- `results/research_progress/negative_variance_relaxation_audit_20260829.csv`

## 5. 最小动力学收敛

正区已经有三个代表点、六个单次 TEBD 和三组 `dt/dt/2` 生产验收，因此不再增加正区响应计算。

负区只在静态相区确定后计算：

1. 每个新增 bulk regime 选一个远离边界的代表点，`L=40`、full-q TEBD。
2. 所有代表点使用 `dt=0.025`；只选一个最困难的负区代表点补 `dt=0.0125`。
3. 时间步检查要求主峰漂移 `<=0.05 J1`、主要低频积分权变化 `<=10%`，并显示 raw 负谱权。
4. 该检查只证明论文图的主要分支稳健，不外推为整个负区的动力学相图。

## 6. 相界与相名

- 粗扫只负责产生 bracket，不负责相命名。
- 最终 bracket 仍要求两个独立诊断、`2 sigma` 区分、宽度 `<=0.025` 和最终 `L=60,80` 支持。
- 如果 64-sweep 上第二诊断仍不稳定，只写“momentum-reconstruction crossover/candidate boundary”，不写已确认 Lifshitz 相变。
- V2 放宽的是单 cell 方差门，不放宽相界的 `2 sigma`、宽度和最终尺寸对要求。

## 7. 数据治理

- V1 与 V2 结果使用不同 validator、不同 acceptance 标签和独立 summary。
- 原始目录、失败 manifest 和 checksum 永久保留，不覆盖、不重写。
- accepted-only 合并优先选最高质量的已有结果，而不是为了节省 sweep 用低预算结果替换高预算结果。
- 论文 Methods 同时报告 V1 严格门、V2 实用门、历史敏感性回放和最终边界的 64-sweep 规则。
