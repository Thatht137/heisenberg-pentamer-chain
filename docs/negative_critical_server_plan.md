# 负侧临界性服务器验证计划

## 当前状态

本地计算已经足以给出 `beta=0.5` 的初步判断：

- 负 `alpha` 的低能参数连续分支具有代数体关联；
- `L=60,80` 的五格点关联包络指数约为 `0.89–0.94`；
- 负侧同时保留弦关联、边缘响应和特殊纠缠结构；
- 正侧也是无隙反铁磁区域；
- `alpha=0` 是两类临界行为之间的特殊解耦点。

因此服务器任务不是为了决定“是否可以开始初步分析”，而是为了确定最终相名、
连续谱结构和热力学极限。

## 第一优先级：DSF 尺寸与时间验证

参数点：

```text
alpha = -0.50, -0.10, -0.05, 0.23
beta = 0.5
L = 80
dt = 0.05
tmax = 30
```

用途：

- `-0.50`：验证折叠软模 `q≈3*pi/5`；
- `-0.10,-0.05`：验证靠近解耦点的 `q=pi` 软模；
- `0.23`：作为正侧常规无隙参照。

服务器命令：

```bash
bash scripts/run_negative_dsf_validation_server.sh 4
```

建议资源：

```text
4 个并行任务
每任务 8–16 CPU 线程
每任务至少 16–32 GB 内存
预计数小时，具体取决于 TEBD 键维增长
```

## 第二优先级：更大尺寸关联

使用：

```text
scripts/24_negative_correlation_continuation.jl
```

建议尺寸：

```text
N_units=24  -> L=120, maxdim≈2500
N_units=32  -> L=160, maxdim≈3500
```

这一步用于确认 `eta≈0.9` 是否稳定，并检查 `alpha≈-0.3` 的动量重分配
是否随尺寸漂移。

## 第三优先级：临界弦关联

现有弦序曾用有限截距解释为长程序，但体关联已经证明为代数衰减。因此需要：

1. 在低能 continuation MPS 上计算 `O_str(r,L)`；
2. 比较常数、幂律和指数三种拟合；
3. 提取负侧临界弦指数；
4. 结合虚空间对称表示判断是否属于 gapless SPT-like 状态。

在完成这一步前，论文中使用：

```text
critical regime with string and edge signatures
```

而不使用已经确定的 `Haldane phase` 或 `gapless SPT phase`。
