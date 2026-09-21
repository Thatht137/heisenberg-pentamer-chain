# 补充材料与复现包清单

范围：只含 `0 <= alpha,beta <= 1`；负 `alpha` 与参考 Fig.9 不进入补充材料。

## Supplementary Methods

- 五聚体 Hamiltonian、边界条件、单位和动量约定。
- 单胞 ED 的总自旋、反射宇称和谱权计算。
- 一阶投影与二阶 Schrieffer–Wolff 有效耦合。
- 有限 DMRG 的双初态、尺寸晋级、方差和截断门槛。
- correction-vector DMRG 的频点恢复、residual 和 accepted-only 规则。
- TEBD 的 `dt/tmax/maxdim`、`t=0`、原始时域数据、raw 负谱权和 trapezoid Fourier 审计。

## Supplementary Results

- 100 点正 `alpha` 局域扫描与全部多重态表。
- 两/三单胞有效理论误差阶验证。
- 105 条正区静态记录、crossing guard 与最弱控制点审计。
- 五类切口纠缠谱与 matched-size `c=1` oracle。
- CV exact oracle、L=40 七点 bounded 锚点、失败 low-005 隔离表，以及 round43 accepted11 production 组装。
- `q=pi` TEBD 收敛表、round43 CV–TEBD Agreement，以及三代表点 full-q `dt/dt2` 交接表（数据终态后加入）。

## 必须保留的验收与失败记录

- residual 超过 `1e-5` 的 low-frequency CV run。
- high-150 的 checksum、非覆盖回传与 validator 通过记录。
- 缺少 production provenance 的旧 TEBD 热图。
- high-budget 初始化半差超过预注册门槛的控制点。
- 旧 full-q exploratory 数据约 49.3% 的负绝对谱权；不得通过裁零升级为 production。

这些记录用于说明止损与证据边界，不进入主结论或生产图。

## 每个 run 的最小文件

`run_config`、`manifest.json`、原始数值数据、stdout/stderr、资源日志、checkpoint（如有）、`checksums.sha256`、validator 输出和回传 receipt。任何缺项必须在 inventory 中标为 incomplete。

full-q 每点另需 `spectrum_raw.csv`、`t0_included=true`、`variance_per_site<=1e-8`、`Sz=0`、raw 负谱权占比 `<=0.15`。同一物理点还必须有 `dt=0.025/0.0125`、相同 `tmax=30` 的交叉验收；任一门失败不得进入多面板论文图。
