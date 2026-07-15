# Li 等（2026）参考范围审计

参考文献：

`references/Li 等 - 2026 - Spin order and spin excitation spectra of spin-12 tetramer chains.pdf`

## 审计结论

当前项目没有脱离 Li 等的总体研究范畴。两者都研究团簇化自旋
`1/2` Heisenberg 链，并使用单胞能级、弦关联、纠缠结构、能隙、
边缘响应和动力学结构因子组织相与激发的证据。

但五聚体单胞含有奇数个自旋 `1/2`，不能直接继承四聚体链的相名称、
弦算符端点、有效自由度或激发命名。当前 `beta=0.5` 结果只支持：

1. 负 `alpha` 的 SPT-like/边缘响应区域；
2. 正 `alpha` 的无隙反铁磁区域；
3. 两者在特殊解耦点 `alpha=0` 分开；
4. `alpha≈0.17` 和 `0.30` 是观测量依赖的响应尺度，不支持独立第四相。

## 逐项对照

| Li 等的研究内容 | 当前五聚体工作 | 审计状态 |
|---|---|---|
| 用 `alpha=J2/J1`、`beta=J3/J1` 描述团簇链 | 使用相同类型的无量纲耦合比 | 对齐 |
| 单四聚体能级与多重态 | 单五聚体精确对角化 | 对齐，但多重态结构不同 |
| 弦序区分平庸与 Haldane-like 区域 | 五聚体弦关联的距离和尺寸标度 | 方法对齐，端点为五聚体专用 |
| Schmidt 权重简并支持 Haldane 判定 | 切割分辨纠缠低能簇与 `Sz` 扇区 | 对齐，但尚非完整拓扑不变量 |
| 中间区域为无隙解禁闭态 | 正 `alpha` 自旋隙趋零且关联幂律衰减 | 只证明无隙，未证明解禁闭 |
| 边界或低能自由度的物理图像 | `Sz=1` 扇区边缘磁化与尺寸标度 | 对齐并更严格 |
| DSF 识别 spinon、triplon、quinton | 仅有稀疏 TEBD DSF | 尚未完成 |
| QRG/微扰理论解释色散 | 尚无五聚体有效模型色散 | 尚未完成 |

## 原文支持的范围

- PDF p.1 的摘要给出四聚体链的平庸四聚体相、Haldane 相和中间
  解禁闭临界态，并把后者解释为自由自旋与三站点 doublet。
- PDF p.3–4、Fig. 3 用四聚体专用弦算符讨论三类区域；临界区域的
  弦序可取中间值，因此弦序本身不足以证明无隙或解禁闭。
- PDF p.4–5、Fig. 4 用 Schmidt 权重的简并变化支持 Haldane 判定。
- PDF p.5 之后的激发分析通过 DSF 和单胞多重态讨论
  `spinon/triplon/quinton`，这些名称依赖四聚体的具体低能结构。

因此，可以继承的是证据链和分析顺序，不能继承的是最终相名与激发名。

## 当前允许使用的表述

### 可以直接写

- `gapless antiferromagnetic regime`
- `SPT-like regime`
- `localized edge degrees of freedom`
- `response or crossover scale`
- `special decoupled point alpha=0`
- `consistent with the type of critical regime discussed by Li et al.`

### 暂时不能直接写

- `deconfined critical state III`
- `deconfined spinon phase`
- `trivial pentamer phase`
- `topologically proven Haldane phase`
- `pentamer triplon/quinton`
- 完整的全局三相图

若要使用这些强表述，必须增加五聚体专用的有效低能图像、选择定则、
低能 DSF 连续谱和跨尺寸稳定性证据。

## 下一轮分析优先级

1. 从单五聚体精确对角化结果提取最低 `S=1/2`、`S=3/2`、`S=5/2`
   多重态及其随 `alpha` 的交叉，建立五聚体专用低能基底。
2. 计算代表点 `alpha=-0.50,-0.05,0.14,0.23,0.33`、`beta=0.5`
   的低能 DSF，先报告能隙、峰位、线宽和连续谱边界。
3. 检查正 `alpha` 连续谱是否随系统尺寸稳定，并与单胞有效自由度对应；
   只有证据闭合后再讨论 spinon 或解禁闭。
4. 用低成本扫描检查 `beta≈0.2,0.7,1.0`，判断
   `beta=0.5` 的两区结构是否延续；不要预设第三个平庸相必然出现。

## 写作边界

`docs/beta_half_results_draft.md` 当前使用 `SPT-like`、
`gapless antiferromagnetic regime` 和 `response scales`，没有提前宣称
完整三相图，表述符合本审计。早期图表计划中的四聚体术语只能作为参考论文
说明，不能作为五聚体结果直接引用。
