# 1x5 Heisenberg Pentamer Chain 项目说明

## 项目背景

本项目参考 Li 等人在 2026 年关于 spin-1/2 tetramer chains 的工作，把四聚体链思路推广到 1x5 五聚体链。代码主要用于构造自旋 1/2 Heisenberg 五聚体链模型，并通过精确对角化、DMRG、弦序参量和动力学结构因子来做数值探索。

## 模型

单个五聚体内部的耦合为：

```text
o--J2--o--J1--o--J1--o--J2--o
1      2      3      4      5
```

相邻五聚体之间通过 `J3` 连接：

```text
...--5 --J3-- 6--...
```

参数约定：

- `J1`：能量单位，默认设为 1。
- `alpha = J2/J1`：五聚体内部两端键与中间键的比值。
- `beta = J3/J1`：相邻五聚体之间的耦合比值。

## 代码结构

```text
src/
  PentamerChain.jl       主模块，加载并导出核心函数
  utils.jl               自旋基矢编码、解码和 Sz 取值
  hamiltonian.jl         单五聚体 ED 矩阵和整链 MPO 构造
  exact_diag.jl          单五聚体精确对角化和总自旋分类
  dmrg_solver.jl         DMRG 基态和激发态计算
  order_parameters.jl    弦序参量和自旋能隙
  spectral.jl            修正向量法计算 S(q, omega)

scripts/
  01_single_pentamer.jl  单五聚体 ED 能级扫描
  02_dmrg_chain.jl       DMRG 基态计算和基本验证
  03_phase_diagram.jl    扫描 alpha、beta 参数空间
  04_dsf.jl              动力学结构因子计算

test/
  runtests.jl            基础单元测试
```

## 运行方式

```powershell
julia --project=. test\runtests.jl
julia --project=. scripts\01_single_pentamer.jl
julia --project=. scripts\02_dmrg_chain.jl
julia --project=. scripts\03_phase_diagram.jl
julia -t 8 --project=. scripts\04_dsf.jl
```

`03_phase_diagram.jl` 和 `04_dsf.jl` 计算量较大，建议先减小 `N_units`、`maxdim`、网格点数或线程数做试跑。

## 已验证内容

- 基础测试通过 45 个断言。
- 单五聚体均匀开边界链的基态能量约为 `-1.92789`。
- `scripts/01_single_pentamer.jl` 可正常运行并输出 `data/single_pentamer_energies.dat`。

## 注意事项

- 项目不是 Git 仓库，无法用 `git diff` 直接查看变更。
- 全尺寸 DMRG、相图和 DSF 计算需要较长时间和更多内存。
- 修正向量法部分属于较重的数值计算，建议先用小体系确认参数后再扩大规模。
