# 图表与计算入口

参考文献：Li et al., npj Quantum Materials (2026), “Spin order and spin excitation spectra of spin-1/2 tetramer chains”。

下表列出参考文献的图表主题与本仓库中的相关计算入口。

| 图表主题 | 参考图号 | 本仓库入口 |
|---|---|---|
| 模型与单胞能谱 | Fig. 1–2 | `src/hamiltonian.jl`、`scripts/01_single_pentamer.jl`、`scripts/plot_energy_levels.py` |
| 弦关联及参数切片 | Fig. 3 | `src/order_parameters.jl`、`scripts/03_phase_diagram.jl`、`scripts/plot_phase_diagram_dense.py`、`scripts/plot_phase_slices.py` |
| 动力学结构因子 | Fig. 6–8 | `src/spectral.jl`、`scripts/04_dsf.jl`，或 `scripts/05_tebd_pentamer.jl` 与 `scripts/06_ft_tebd_pentamer_mapped.jl` |

参考文献的 Fig. 4、Fig. 5 和 Fig. 9 分别讨论纠缠谱、激发示意及材料响应。

## 单胞结构

五聚体含 5 个自旋 1/2，Hilbert 空间维度为 32。总自旋分解为：

- S=1/2：5 个二重态，共 10 态。
- S=3/2：4 个四重态，共 16 态。
- S=5/2：1 个六重态，共 6 态。

在 α=0 时，五聚体分解为中间三聚体与两端自由自旋；均匀反铁磁单五聚体的基态属于 S=1/2 扇区。

## 数据流程

单胞能谱由精确对角化脚本生成。链的弦关联由 DMRG 基态计算后取得。动力学结构因子包含修正向量法和 TEBD 两条路线；TEBD 先保存实空间—时间关联，再作傅里叶变换。
