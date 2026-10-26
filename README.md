<p align="center">
  <h1 align="center">1x5 Heisenberg Pentamer Chain</h1>
</p>

<p align="center">
  自旋 1/2 五聚体 Heisenberg 链的数值计算项目
</p>

<p align="center">
  <a href="docs/validation_report.md">验证报告</a>
  ·
  <a href="docs/server_run_guide.md">服务器指南</a>
  ·
  <a href="docs/git_guide.md">Git 笔记</a>
  ·
  <a href="scripts">计算脚本</a>
  ·
  <a href="src">源码</a>
</p>

---

本项目用于研究 1x5 五聚体 Heisenberg 自旋链的基态性质、弦序参量、动力学结构因子和有限温 TEBD 谱函数。

2026-10-26 收尾归档：[资料入口与下载说明](docs/archive_20261026.md)。代码、稿件和文档可直接浏览；完整数据、图表与历史资料见 [GitHub Release](https://github.com/Thatht137/heisenberg-pentamer-chain/releases/tag/archive-2026-10-26)。

当前结果主要用于流程验证和论文图表准备。正式物理结论仍建议使用更大体系、更密网格和充分的有限尺寸分析。

## 模型

五聚体链的一个单元包含 5 个自旋 1/2 格点：

```text
o--J2--o--J1--o--J1--o--J2--o  --J3--  o--J2--o--J1--o--J1--o--J2--o
1      2      3      4      5            6      7      8      9      10
```

参数约定：

- `J1 = 1`：能量单位。
- `alpha = J2 / J1`：五聚体内部端键强度。
- `beta = J3 / J1`：相邻五聚体之间的耦合强度。

## 功能

- 精确对角化：单五聚体能谱、总自旋分类和能级导出。
- DMRG：有限长度五聚体链基态、激发态、弦序参量和自旋能隙。
- 相图扫描：粗网格、加密网格和 80×60 高精度网格的 `(alpha, beta)` 参数扫描。
- 动力学结构因子：修正向量法计算 `S(q, omega)`，TEBD 时域路线作为交叉验证。
- TEBD：五聚体链和映射模型的有限温动力学谱函数计算。
- 绘图：相图、能级、切片曲线和 DSF 可视化脚本。

## 安装

需要先安装 Julia。`Manifest.toml` 当前由 Julia 1.11.x 环境生成，服务器上优先使用 Julia 1.11.x。

在项目根目录运行：

```powershell
julia --project=. -e "using Pkg; Pkg.instantiate()"
```

## 快速检查

运行单元测试：

```powershell
julia --project=. test\runtests.jl
```

运行单五聚体精确对角化：

```powershell
julia --project=. scripts\01_single_pentamer.jl
```

当前本地检查结果：

- `test/runtests.jl`：45 个断言全部通过。
- `scripts/01_single_pentamer.jl`：已成功运行，并写出 `data/single_pentamer_energies.dat`。

## 脚本

```text
scripts/
  01_single_pentamer.jl              单五聚体能谱扫描
  01b_export_energy_levels.jl        导出单五聚体能级表
  02_dmrg_chain.jl                   DMRG 基态与极限验证
  03_phase_diagram.jl                弦序参量粗网格相图
  03b_phase_diagram_dense.jl         弦序参量加密相图
  03c_phase_diagram_80x60.jl         80×60 弦序相图（标准精度）
  03d_phase_diagram_80x60_hires.jl   80×60 弦序相图（高精度，maxdim=1000）
  04_dsf.jl                          修正向量法 DSF
  05_tebd_pentamer.jl                五聚体链 TEBD 谱函数
  05_tebd_pentamer_server.jl         05 的服务器版（环境变量驱动）
  06_ft_tebd_pentamer_mapped.jl      TEBD 关联函数到 S(q,omega) 的傅里叶变换
  06_ft_tebd_pentamer_mapped_server.jl 06 的服务器版（环境变量驱动）
  merge_phase_dense.jl               合并加密相图结果
  merge_phase_80x60.jl               合并 80×60 标准相图
  merge_phase_80x60_hires.jl         合并 80×60 高精度相图
  read_dsf_summary.jl                读取 DSF 结果摘要
  plot_*.py / plot_*.jl              绘图脚本
```

常用命令：

```powershell
julia --project=. scripts\03_phase_diagram.jl
julia -t 8 --project=. scripts\04_dsf.jl
python scripts\plot_phase_diagram.py
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

test/
  runtests.jl            基础单元测试
```

## 数据与图片

默认输出目录：

- `data/`：JLD2、CSV、DAT 等数值结果。
- `figures/`：相图、能级图和切片图。
- `data/figures/`：DSF 热图和切片 SVG。

当前已就位的代表性结果：

- `data/phase_diagram_80x60_hires.csv`：80×60 高精度弦序相图（N_units=12, maxdim=1000）。
- `data/Sqw_tebd_pentamer_alpha=*_beta=*.csv`：10 组 TEBD DSF 谱（α=±1.0 各配 5 个 β）。
- `figures/phase_diagram_derivative.{pdf,png}`：|dO_str/dα| 导数热力图，凸显 α≈±0.2 过渡区。
- `figures/Sqw_tebd_grid.{pdf,png}`：10 组 DSF 拼接 grid，对照文献 Fig. 6。

当前数据适合检查代码流程和物理趋势，不建议直接作为发表级结果使用。正式计算前建议备份旧结果，避免脚本覆盖。

## 文档

- [验证报告](docs/validation_report.md)：测试、DMRG 和 DSF 的验证结果。
- [服务器计算入门指南](docs/server_run_guide.md)：服务器安装、运行和提交任务建议。
- [模块逐行详解](docs/module_guide.md)：从物理原理到代码实现的详细说明。
- [精确对角化说明](docs/exact_diag_explained.md)：ED 方法说明。
- [论文图表计划](docs/figure_plan.md)：对照参考文献的图表任务拆分。
- [展示脚本](docs/presentation_script.md)：给老师汇报时可用的讲稿。
- [Git 手动操作笔记](docs/git_guide.md)：常用 Git 命令和提交流程。

## 正式计算建议

- 相图：`N_units >= 12`，`margin = 3`，检查有限尺寸收敛。
- DSF：先用 `N_units = 8` 或 `10`，再逐步加密 `q` 和 `omega` 网格。
- 展宽：先用 `eta = 0.1` 稳定流程，再尝试更小展宽。
- 长任务：加入日志、断点保存和结果备份，避免中断后丢失数据。

## 协议

本项目当前尚未添加正式开源协议文件。公开发布前建议根据需要添加 `LICENSE`。
