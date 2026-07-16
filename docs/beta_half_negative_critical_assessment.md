# `beta=0.5` 负 `alpha` 临界性复核

## 复核原因

`L=40,tmax=15` 的试验性 DSF 在 `alpha=-0.50`、`q≈3*pi/5`
发现近零频谱重。这与“负侧是普通有隙 Haldane-like 相”的解释存在张力。

直接从 Néel 产品态独立计算时，`alpha=-0.05` 的体区关联曾表现为快速衰减。
但该点能量在 40 sweeps 后仍持续下降，说明靠近 `alpha=0` 时存在严重的
DMRG 路径依赖。

## 双向参数连续方法

在总 `Sz=0` 扇区中，分别计算：

```text
forward:  alpha=-0.50 -> -0.025
backward: alpha=-0.025 -> -0.50
```

每个参数点使用前一点收敛 MPS 作为初态，并保存体区平均连接关联。
计算尺寸为 `L=40,60,80`。

输出：

- `data/negative_correlation_continuation/profiles_b0.50_L040.csv`
- `data/negative_correlation_continuation/profiles_b0.50_L060.csv`
- `data/negative_correlation_continuation/profiles_b0.50_L080.csv`
- `data/negative_correlation_continuation/summary_b0.5.csv`
- `figures/negative_correlation_continuation_b0.5.pdf`

## 能量分支

在深负区域，两方向能量一致。靠近零点时，从深负侧连续推进得到的 forward
分支具有更低能量：

```text
L=80, alpha=-0.050: E_forward-E_backward ≈ -2.8e-4
L=80, alpha=-0.025: E_forward-E_backward ≈ -2.5e-4
```

短程关联的 backward 分支是高能假收敛态，不能用于判定体能隙。

## 体区关联

对每五个格点取一次 `|C(r)|` 局域最大值作为五聚体包络。低能 forward
分支得到：

```text
L=60: eta ≈ 0.89-0.94
L=80: eta ≈ 0.89-0.93
```

指数在整个负 `alpha` 扫描中连续，并与正 `alpha` 已得到的
`eta≈0.95-0.98` 接近。负侧关联因此更符合代数衰减，而不是有限关联长度的
普通有隙体态。

## 低能分支上的弦关联

为避免独立产品态 DMRG 的假收敛，本轮直接在 deep-negative forward 分支的
MPS 上计算奇数位胞距离的交错弦包络：

```text
alpha = -0.50, -0.25, -0.10, -0.05
L = 40, 60, 80
```

拟合只使用 `3 <= d <= 2*N_units/3` 的体区距离，以排除 OBC 最长距离处的
边缘回升。对 `L=60,80`，幂律模型在全部四个参数点都优于常数和指数模型：

```text
L=60: eta_str ≈ 0.23-0.25
L=80: eta_str ≈ 0.27-0.28
```

指数模型的对数残差约为幂律模型的 `1.6-2.3` 倍。`L=40` 在排除短程点和
边缘距离后只剩两个拟合点，因此仅作为原始曲线对照，不提取指数。

这说明负侧弦关联不是普通短程指数衰减，而是在临界体关联背景上保持明显更慢的
代数衰减。当前尺寸还不足以区分“渐近代数衰减”与“更大尺度后趋向有限常数”，
因此不直接宣称严格长程弦序。该结果加强了“具有弦与边缘特征的临界区域”解释，
但 gapless SPT 的最终命名仍需虚空间投影对称表示。

输出：

- `data/negative_string_continuation/profiles_b0.50_L040.csv`
- `data/negative_string_continuation/profiles_b0.50_L060.csv`
- `data/negative_string_continuation/profiles_b0.50_L080.csv`
- `data/negative_string_continuation/fit_summary_b0.5.csv`
- `figures/negative_string_continuation_b0.5.pdf`

## 动量结构

负侧存在一个动量重分配尺度：

```text
alpha <= -0.35: q_peak ≈ 3*pi/5
alpha >= -0.25: q_peak = pi
```

该变化与五站点单胞的动量折叠一致。当前关联指数没有在同一位置发生突变，
双向能量也没有形成稳定滞后，因此暂时称为动量重分配或候选 Lifshitz
尺度，而不是独立相边界。

## 对相结构的修订

当前 `beta=0.5` 截面不再支持简单的

```text
负 alpha：普通有隙 SPT-like
正 alpha：无隙反铁磁
```

更符合现有证据的初步图像是：

1. 负 `alpha`：代数关联的临界体态，同时具有显著弦关联和边缘响应；
2. 正 `alpha`：以 `q=pi` 为主的常规无隙反铁磁体态；
3. `alpha=0`：单胞八重简并和低能自由度重组的特殊解耦点；
4. 负侧约 `alpha=-0.3`：低能动量从折叠的 `3*pi/5` 转向 `pi`，
   目前不足以定义新相。

“gapless SPT”“拓扑 Luttinger liquid”或“解禁闭临界态”等名称仍需要
投影对称表示和更高分辨率 DSF，当前不直接使用。

## OBC 自旋扇区隙的限制

负侧 `E(Sz=1)-E(Sz=0)` 在 `L=40,60,80` 均接近零，但负侧同时存在边缘
自由度，因此该量主要可能反映边缘态劈裂，不能单独作为体能隙。

后续若需要直接测体能隙，应优先使用：

1. 周期边界条件；
2. 排除边缘多重态后的激发能；
3. 体区局域算符 DSF 的尺寸和时间标度。

## 下一步

初步相结构分析已经可以继续写作，但正式确认负侧临界性还需要服务器级任务：

- `L=80,120`，`tmax>=30` 的 `alpha=-0.50,-0.10,-0.05` DSF；
- `L=120,160` 的负侧参数连续关联；
- `L=120,160` 的临界弦指数复核和虚空间对称表示。

这些任务不影响当前“普通有隙负侧解释不成立”的初步判断，但会决定最终相名。
