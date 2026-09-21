# 作者修改说明

## 本稿的中心论点

五聚体的奇数自旋单元保留低能自旋-1/2 双重态，正耦合区因此形成反铁磁有效链并呈现与 $c=1$ 有效链一致的有限尺寸行为；局域反射宇称决定 $q=\pi$ 可见通道；负 $\alpha$ 区确认的是有限尺寸主导动量重构，而不是已经命名的新热力学相。

## 已锁定的术语

- `Krylov dimension k` 与 MPS 键维数 `chi` 严格区分。
- `finite-size momentum reconstruction` 是负区主结论。
- `crossover` 只作 working interpretation。
- `effective entropy coefficient c_eff` 不直接称为中央荷。
- 双初态差异称为 initialization sensitivity，不称置信区间。
- 正区写成 “one resolved effective-chain regime”，不写“全域只有一个相”。

## 关键 claim--evidence 对应

| 论文主张 | 核心证据 | 允许的表述 | 禁止外推 |
|---|---|---|---|
| 正区局域基态为偶宇称自旋-1/2 双重态 | 100 个孤立五聚体采样点；完整多重态分辨 | sampled positive-alpha region | 全参数空间定理 |
| 正 $\beta$ 产生反铁磁有效链 | $J_{\rm eff}=\beta c_1c_5>0$；两五聚体与完整链误差近二次 | tested positive-coupling points | 全域严格 $c=1$ |
| $q=\pi$ 最低激发双重态为暗模 | 投影谱重低于 $4.6\times10^{-27}$；宇称相反 | symmetry-selected local channel | 有限 $\beta$ 下必为锐利准粒子 |
| 动力学结果达到 production 级 | CV 的 11 频点；三组 full-q 的 dt/dt2 门 | pointwise validated spectra | 动力学相图 |
| 负区发生主导动量重构 | Stage B 89 accepted/7 bounded；Stage C 29/29 accepted | finite-size momentum reconstruction | 新相、Lifshitz 相界、连续二维相界 |
| $(-0.10,0.25,L80)$ 数值稳定 | k8→k12 的 172 项比较；q_peak 不变，三类差异极小 | Krylov stability at one finite-size point | chi 收敛、热力学极限、中央荷 |

## 当前仍需作者填写

1. 作者、单位、通讯作者。
2. 目标期刊格式与字数限制。
3. 基金、计算资源和 CRediT 作者贡献。
4. 公开代码/数据仓库 DOI 或链接。
5. 作者本人对模型定义、图中符号和全部数值做最后科学复核。

## 投稿前建议

当前稿件已经可以进入作者审读和排版。若维持现有主张，不需要为了“看起来有多个相”继续扩大同类网格。若要提高论文档次，最有效的补强不是盲目加点，而是提供能够与 $q_{\rm peak}$ 联合定位的独立热力学诊断，或在最敏感点完成实际生效的 $\chi$ 序列和更大尺寸。任何新增计算都应先写明它区分哪两个物理解释。

