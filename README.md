# 1×5 Heisenberg Pentamer Chain

自旋 1/2 五聚体 Heisenberg 链的数值研究代码与数据，涵盖局域能谱、有限链基态、弦序参量和动力学结构因子。

[完整资料下载](https://github.com/Thatht137/heisenberg-pentamer-chain/releases/tag/archive-2026-10-26) · [归档源码](https://github.com/Thatht137/heisenberg-pentamer-chain/tree/codex/archive-20261026)

## 模型

每个五聚体单元包含 5 个自旋 1/2 格点，相邻单元通过端点耦合连接：

```text
o--J2--o--J1--o--J1--o--J2--o  --J3--  o--J2--o--J1--o--J1--o--J2--o
1      2      3      4      5            6      7      8      9      10
```

| 参数 | 定义 |
|---|---|
| `J1 = 1` | 能量单位 |
| `alpha = J2 / J1` | 五聚体内部端键耦合 |
| `beta = J3 / J1` | 相邻五聚体之间的耦合 |

## 数值方法

- **精确对角化**：单五聚体能谱、总自旋分类与能级导出。
- **DMRG**：有限链基态、激发态、自旋能隙、关联函数与弦序参量。
- **参数扫描**：`(alpha, beta)` 网格计算、相图数据整理与切片分析。
- **动力学结构因子**：修正向量法及 TEBD 时域关联函数计算 `S(q, omega)`。
- **数据处理与绘图**：结果合并、傅里叶变换、能谱和相图可视化。

## 快速开始

归档环境使用 Julia 1.11.5，主要依赖包括 ITensors、ITensorMPS、KrylovKit 和 JLD2。依赖配置与版本记录位于 `Project.toml` 和 `Manifest.toml`。

在项目根目录安装依赖：

```sh
julia --project=. -e "using Pkg; Pkg.instantiate()"
```

运行单五聚体能谱计算：

```sh
julia --project=. scripts/01_single_pentamer.jl
```

运行基础测试：

```sh
julia --project=. test/runtests.jl
```

## 目录结构

| 目录 | 内容 |
|---|---|
| [src/](src/) | 哈密顿量、精确对角化、DMRG、序参量与谱函数实现 |
| [scripts/](scripts/) | 计算、参数扫描、数据处理与绘图脚本 |
| [data/](data/) | CSV、DAT、JLD2 等数值数据 |
| [figures/](figures/) | 图表与导出文件 |
| [test/](test/) | 单元测试 |

## 数据与论文材料

[2026-10-26 归档版本](https://github.com/Thatht137/heisenberg-pentamer-chain/releases/tag/archive-2026-10-26)提供完整研究资料，包括代码、数值结果、计算检查点、图表、论文源文件与 PDF、历史版本和参考资料。

完整资料分为 7 个 `pentamer-*-20261026.zip` 文件，保留项目相对路径。论文 PDF 可单独下载，`manifest.csv` 提供逐文件索引，`SHA256SUMS.txt` 提供附件校验值。完整下载与目录恢复步骤见 Release 说明。
