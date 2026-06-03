# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

自旋 1/2 Heisenberg 五聚体链数值研究：精确对角化、DMRG、弦序参量、动力学结构因子。Julia 项目，核心依赖 ITensors/ITensorMPS。

动力学结构因子有**两套独立实现**，互为交叉验证：
- **修正向量法**（频域）— `src/spectral.jl` + `scripts/04_dsf.jl`，直接对每个 (q, ω) 解线性方程。
- **TEBD 法**（时域）— `scripts/05_tebd_pentamer.jl` 算实空间-时间关联 C(n,t)，再由 `scripts/06_ft_tebd_pentamer_mapped.jl` 傅里叶变换得 S(q, ω)。TEBD 逻辑全在脚本里，不在 `src/`。

## 常用命令

```bash
# 运行测试（45 个断言）
julia --project=. test/runtests.jl

# 运行脚本
julia --project=. scripts/01_single_pentamer.jl
julia --project=. scripts/02_dmrg_chain.jl
julia --project=. scripts/03_phase_diagram.jl
julia -t 8 --project=. scripts/04_dsf.jl

# TEBD 动力学：先算关联函数，再傅里叶变换（必须按顺序）
julia --project=. scripts/05_tebd_pentamer.jl
julia --project=. scripts/06_ft_tebd_pentamer_mapped.jl
```

脚本 03 和 04 计算量大，试跑时应减小 `N_units`、`maxdim` 或网格点数。

`runtests.jl` 是单文件测试，无独立测试框架；没有运行单个测试的机制，整文件一起跑。

脚本编号约定：带 `b` 后缀的是变体（`01b` 导出能级 CSV、`03b` 是支持 SLURM array 的加密相图）；带 `_server` 后缀的（`05`/`06`）与本地版逻辑相同，只是把脚本内常量改为 `PENTAMER_*` 环境变量驱动，便于在集群上不改代码扫参数。

## 模型

```
o--J2--o--J1--o--J1--o--J2--o  ---J3---  o--J2--o--J1--o--J1--o--J2--o
1      2      3      4      5             6      7      8      9      10
```

- `J1 = 1`（能量单位）
- `alpha = J2/J1`（胞内两端键）
- `beta = J3/J1`（胞间耦合）

## 架构

模块 `PentamerChain`（src/PentamerChain.jl）加载所有源文件并导出公共 API。

哈密顿量构造分两层：
1. **ED 层**（hamiltonian.jl:pentamer_hamiltonian_matrix）— 用 utils.jl 的自旋基矢编码构造单个孤立五聚体的 32×32 稠密矩阵。供 exact_diag.jl 做全对角化和总自旋分类。
2. **MPO 层**（hamiltonian.jl:pentamer_chain_hamiltonian）— 用 ITensors OpSum 构造整链 MPO。供 DMRG（dmrg_solver.jl）、弦序参量（order_parameters.jl）和 DSF（spectral.jl）使用。

DMRG 使用几何递增的键维度调度（`_sweep_schedule`）和 Néel 初态。激发态用正交约束 DMRG。

DSF 计算（spectral.jl）对基态 MPS 施加 S^z_q 算符，再通过 `ITensorMPS.linsolve` 求解修正向量方程。按 q 点分块，用 `Threads.@spawn` 并行，每线程 deepcopy 独立副本。

TEBD 路线（scripts/05）独立于 `src/`：复用 `compute_ground_state` 拿基态后，用一阶 Trotter 门序列（`pentamer_bonds` 列出全部键，门序列正反各一遍）演化 `S^z_center|GS⟩`，逐步算 C(n,t) = ⟨GS|S^z_n e^{-i(H-E0)t} S^z_center|GS⟩，存为 5 行矩阵（time, site, distance, real, imag）。脚本 06 读该文件，对 (t, distance) 做带 sin² 时间窗的傅里叶变换得 S(q,ω)，并对高强度区做对数压缩（`map_intensity`，阈值 `MAP_U0`）。文件名按 `NDSF_pentamer_alpha=..._beta=..._L=....jld2` 约定，06 据此自动定位 05 的输出。

## Python 环境

Python 绘图脚本使用项目根目录下的虚拟环境，不要全局安装：

```bash
# 激活虚拟环境
source .venv/Scripts/activate   # Windows Git Bash
.venv\Scripts\activate          # Windows CMD

# 运行绘图脚本
.venv/Scripts/python scripts/plot_phase_diagram.py
.venv/Scripts/python scripts/plot_phase_diagram_smooth.py
```

已安装包：matplotlib, scipy, numpy, pypdf。需要新增包时用 `.venv/Scripts/pip install <pkg>`。

## 核心依赖

- ITensors 0.9.x / ITensorMPS 0.4.x — 张量网络核心
- KrylovKit — 迭代本征值求解器（ITensors DMRG 内部调用）
- JLD2 — 脚本中的检查点序列化

## 已验证基线

- 均匀开边界 5 格点链基态能量：−1.92789
- 5 自旋 S² 本征值：S=1/2（简并度 10）、S=3/2（简并度 16）、S=5/2（简并度 6）

## 参考文献与对标

参考：Li et al., npj Quantum Materials (2026), "Spin order and spin excitation spectra of spin-1/2 tetramer chains"

本项目是该文献从四聚体（4 格点/胞）到五聚体（5 格点/胞）的推广。关键物理差异：
- 四聚体单胞基态 S=0（singlet），五聚体单胞基态 S=1/2（doublet）
- α=0 退化：四聚体 → 二聚体+2自由自旋（2 个能量簇）；五聚体 → 三聚体+2自由自旋（4 个能量簇）
- 弦序参量定义相同（跨胞边界的多点 Sz 关联），周期从 4 改为 5

图表对应关系（文献 → 本项目）：
- Fig. 2a（单胞能级 vs α）→ `scripts/plot_energy_levels.py`
- Fig. 3a（O_str 热力图）→ `scripts/plot_phase_diagram_dense.py`
- Fig. 3b/c/d（1D 切片+导数）→ `scripts/plot_phase_slices.py`
- Fig. 6-8（DSF 谱）→ `scripts/04_dsf.jl`（修正向量法）或 `scripts/05`+`06`（TEBD 法）

完整的逐图计划、物理含义、计算量估算和优先级见 `docs/figure_plan.md`；模块逐行详解见 `docs/module_guide.md`；上服务器流程见 `docs/server_run_guide.md`。

## 绘图约定

- 相图坐标轴：横轴 β（胞间耦合），纵轴 α（胞内端键比）— 与文献一致
- 能级图纵轴应使用激发能 ω = E − E₀（相对基态），而非绝对能量
- 色图：signed 用 RdBu_r + TwoSlopeNorm，absolute 用 inferno
- 不加等高线（保持干净）
- 输出格式：PDF + PNG，dpi=300

## 加密相图 SLURM 任务

```bash
# 提交 40 个 array task（每个 task 一个 alpha 值，跑 20 个 beta 点）
sbatch scripts/submit_slurm_phase_dense.sh

# 完成后合并
julia --project=. scripts/merge_phase_dense.jl

# 绘图
.venv/Scripts/python scripts/plot_phase_diagram_dense.py
.venv/Scripts/python scripts/plot_phase_slices.py
```
