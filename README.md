<p align="center">
  <h1 align="center">1x5 Heisenberg Pentamer Chain</h1>
</p>

<p align="center">
  自旋 1/2 五聚体 Heisenberg 链的数值计算项目
</p>

<p align="center">
  <a href="docs/validation_report.md">验证报告</a>
  ·
  <a href="scripts">计算脚本</a>
  ·
  <a href="src">源码</a>
</p>

---

> 本项目用于研究 1x5 五聚体 Heisenberg 自旋链的基态性质、弦序参量和动力学结构因子。
> 当前小体系结果主要用于流程验证；正式物理结论建议使用更大体系、更密网格和充分的有限尺寸分析。

## 这是什么

这是一个 Julia 数值计算项目，用来构造和研究如下五聚体链模型：

```text
o--J2--o--J1--o--J1--o--J2--o  --J3--  o--J2--o--J1--o--J1--o--J2--o
1      2      3      4      5            6      7      8      9      10
```

参数约定：

- `J1 = 1`：能量单位。
- `alpha = J2 / J1`：五聚体内部端键强度。
- `beta = J3 / J1`：相邻五聚体之间的耦合强度。

本项目目前实现了以下功能：

- 精确对角化：计算单个五聚体能谱和总自旋分类。
- DMRG：计算有限长度五聚体链基态和激发态。
- 弦序参量：扫描 `(alpha, beta)` 参数空间。
- 自旋能隙：比较不同总 `Sz` 扇区能量。
- 动力学结构因子：用修正向量法计算 `S(q, omega)`。
- 结果保存：使用 JLD2 保存相图和谱函数数据。

## 数据来源与物理说明

项目参考了 tetramer chain 相关文献的模型思路，并推广到 1x5 五聚体链。代码中的模型、参数扫描和物理量定义均在本仓库内实现。

当前 `data/` 目录中的结果文件是小体系试算结果：

- `phase_diagram.jld2`：弦序参量流程验证数据。
- `dsf_spectrum.jld2`：动力学结构因子流程验证数据。
- `single_pentamer_energies.dat`：单五聚体能级数据。

这些文件适合检查代码流程和物理趋势，不建议直接作为发表级结果使用。

## 安装

需要先安装 Julia，并确保版本满足 `Project.toml` 中的兼容要求。

在项目根目录运行：

```powershell
julia --project=. -e "using Pkg; Pkg.instantiate()"
```

## 运行

运行基础测试：

```powershell
julia --project=. test\runtests.jl
```

运行单五聚体精确对角化：

```powershell
julia --project=. scripts\01_single_pentamer.jl
```

运行 DMRG 链计算：

```powershell
julia --project=. scripts\02_dmrg_chain.jl
```

运行弦序参量相图扫描：

```powershell
julia --project=. scripts\03_phase_diagram.jl
```

运行动力学结构因子计算：

```powershell
julia -t 8 --project=. scripts\04_dsf.jl
```

## 代码结构

```text
src/
  PentamerChain.jl       主模块
  utils.jl               自旋基矢编码和解码
  hamiltonian.jl         哈密顿量矩阵和 MPO 构造
  exact_diag.jl          精确对角化和总自旋分类
  dmrg_solver.jl         DMRG 基态和激发态计算
  order_parameters.jl    弦序参量和自旋能隙
  spectral.jl            修正向量法计算 S(q, omega)

scripts/
  01_single_pentamer.jl  单五聚体能谱扫描
  02_dmrg_chain.jl       DMRG 基态验证
  03_phase_diagram.jl    相图扫描
  04_dsf.jl              动力学结构因子计算

test/
  runtests.jl            基础单元测试
```

## 验证状态

目前已经完成以下小体系检查：

- 基矢编码和解码互为逆操作。
- 单五聚体哈密顿量维度、厄米性和迹满足预期。
- 均匀五站点开链基态能量与精确对角化基准一致。
- 总自旋分类的简并数符合 `S=1/2, 3/2, 5/2` 结构。
- DMRG 在孤立极限和均匀链极限下给出合理能量。
- DSF 小网格结果满足非负性、`q=0` / `2pi` 零权重和反演对称性。

详细说明见：

- [验证报告](docs/validation_report.md)

## 正式计算建议

正式上服务器计算前，建议先做中等规模预跑：

- 相图：`N_units >= 12`，`margin = 3`，检查有限尺寸收敛。
- DSF：先用 `N_units = 8` 或 `10`，再逐步加密 `q` 和 `omega` 网格。
- 展宽：先用 `eta = 0.1` 稳定流程，再尝试更小展宽。
- 保存：大网格扫描建议加入断点保存，避免长任务中断后丢失结果。

## 相关文档

- [验证报告](docs/validation_report.md)
- [计算脚本](scripts)
- [源码目录](src)

## 协议

本项目当前尚未添加正式开源协议文件。公开发布前建议根据需要添加 `LICENSE`。
