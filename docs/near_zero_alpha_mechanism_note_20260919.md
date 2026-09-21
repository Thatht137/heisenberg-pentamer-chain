# $\alpha\simeq0$ 的候选受控极限机制备忘录

> 日期：2026-09-19。状态：解析候选受控极限；8-spin oracle v2 已完成独立数值核对，但这不是完整链热力学验证，也不是全域结论。本轮不修改 `paper/`。

## 1. 适用域与零阶分解

以下取 $J_1=1$、$\beta>0$，并考虑

$$
|\alpha|\ll\min(1,\beta).
$$

在 $\alpha=0$ 时，体内每个五聚体的 $(2,3,4)$ 三个自旋组成 $J_1$ trimer；相邻胞之间的 $(5_n,1_{n+1})$ 组成 $\beta$ dimer singlet。因而这是一个 trimer--dimer 的候选受控起点，而不是已经对完整有限链作出的相判断。

设 trimer 的低能双重态投影为 $P_n$，有效自旋为 $\mathbf T_n$。逐分量投影为

$$
P_n\mathbf S_{n,2}P_n=\frac23\mathbf T_n,\qquad
P_n\mathbf S_{n,3}P_n=-\frac13\mathbf T_n,\qquad
P_n\mathbf S_{n,4}P_n=\frac23\mathbf T_n.
$$

该 trimer 双重态投影可与三聚体链文献的低能有效自旋构造对照，但下述五聚体的系数、dimer 消去和 $J_{\mathrm{eff}}$ 仍是本项目的推导，未由该文献直接证明。参见 [trimer primary](https://www.nature.com/articles/s41535-021-00416-4)。

## 2. dimer 单态的二阶消去

取一个胞间 dimer 的左、右自旋为

$$
\mathbf S_L=\mathbf S_{n,5},\qquad \mathbf S_R=\mathbf S_{n+1,1},
$$

则零阶 dimer 哈密顿量为

$$
H_0=\beta\,\mathbf S_L\cdot\mathbf S_R.
$$

其 singlet 能量为 $-3\beta/4$，triplet 能量为 $\beta/4$，所以 singlet--triplet 分母为 $\beta$。将两侧的 $\alpha$ 键投影到相邻 trimer 双重态后，得到

$$
g=\frac{2\alpha}{3},\qquad
V=g\left(\mathbf T_n\cdot\mathbf S_L+\mathbf S_R\cdot\mathbf T_{n+1}\right).
$$

记 singlet 投影为 $P_s=|s\rangle\langle s|$、triplet 投影为 $Q_t$。因为单自旋把 singlet 送到 triplet，二阶项为

$$
H_{\mathrm{eff}}^{(2)}
=-P_sVQ_t\frac{1}{H_0-E_s}Q_tVP_s
=-\frac1\beta P_sVQ_tVP_s.
$$

singlet 的交叉矩阵元是

$$
P_sS_L^aQ_tS_R^bP_s
=\langle s|S_L^aS_R^b|s\rangle P_s
=-\frac{\delta_{ab}}4P_s,
$$

并且反向次序同样给出

$$
P_sS_R^bQ_tS_L^aP_s=-\frac{\delta_{ab}}4P_s.
$$

因此，先由左侧耦合激发 dimer、再由右侧耦合退激发，以及先右后左的两种次序共同给出

$$
\begin{aligned}
H_{\mathrm{cross}}^{(2)}
&=-\frac{g^2}{\beta}\sum_{ab}
\left[-\frac{\delta_{ab}}4T_n^aT_{n+1}^b
-\frac{\delta_{ab}}4T_{n+1}^bT_n^a\right]\\
&=\frac{g^2}{2\beta}\,\mathbf T_n\cdot\mathbf T_{n+1}.
\end{aligned}
$$

故候选的 bulk 有效交换为

$$
J_{\mathrm{eff}}=\frac{g^2}{2\beta}
=\frac{2\alpha^2}{9\beta}>0.
$$

同一 dimer 的左右自能项只给常数：

$$
P_sS_L^aQ_tS_L^bP_s=P_sS_R^aQ_tS_R^bP_s
=\frac{\delta_{ab}}4P_s,
$$

从而

$$
H_{\mathrm{self}}^{(2)}
=-\frac{g^2}{4\beta}
\left(\mathbf T_n^2+\mathbf T_{n+1}^2\right),
$$

对固定的 $T=1/2$ 双重态，这只是先投影 trimer 双重态后的 dimer 自能常数（每个 dimer 为 $-3g^2/(8\beta)$）。完整 8-spin 问题的二阶能量还可包含 trimer 激发虚过程的其他常数贡献，因此不能把此项等同于完整总能量的二阶修正；这些纯自能常数不改变跨两个 trimer 的交换系数。

## 3. 胞内形状因子与动量折叠

在这个零阶投影中，五个物理位置的 leading 胞内系数为

$$
(c_1,c_2,c_3,c_4,c_5)=\left(0,\frac23,-\frac13,\frac23,0\right).
$$

取胞内坐标 $a-1$，形状因子为

$$
\begin{aligned}
F(q)&=\sum_{a=1}^5c_a e^{iq(a-1)}\\
&=\frac23e^{iq}-\frac13e^{2iq}+\frac23e^{3iq}
=e^{2iq}\frac{4\cos q-1}{3}.
\end{aligned}
$$

手算得到

$$
|F(\pi)|^2=\frac{25}{9},
\qquad
|F(0.2\pi)|^2=|F(0.6\pi)|^2=\frac59.
$$

这里的 $|F(q)|^2$ 只是 leading 低能投影的胞内因子，不是全频谱或绝对归一化的谱重。比较“每物理站点归一化”的 $S(q,\omega)$ 与“每个 trimer 归一化”的 $S_{\mathrm{eff}}$ 时，还需保留相应的 $1/5$ 归一化因子，并计入有限 $\alpha$ 修正。

若把物理动量折叠到五站点胞的晶胞动量，$K=5q\pmod{2\pi}$；因此 $q=0.2\pi,0.6\pi,\pi$ 都给 $K=\pi$。这只是运动学形状因子和折叠关系，不能单独证明观测到的 crossover、相边界或新相。

## 4. 不可交换的极限与开边界限制

上面的推导先取 $\alpha\to0$、固定 $\beta>0$，再消去胞间 dimer 的 triplet。另一条路径是 $\beta$ 小于孤立五聚体的相关激发隙，在孤立五聚体多重态（包括 $S=3/2$ quartet 投影）上做低能展开。两种路径的基本投影空间不同，不能交换两个极限，也不能用其中一条路径替代另一条路径。

开边界条件下，$\alpha=0$ 还留下两端的孤立 spin-$1/2$。当 $\alpha<0$ 时，边界耦合的一阶尺度为 $O(\alpha)$（边界倾向 ferromagnetic），而上述 bulk 介导交换为 $O(\alpha^2/\beta)$。因此有限 OBC 的 $S^z$ gap 可能由边界态主导，不能直接当作 bulk gap；这也是为什么本推导不对已有 OBC gap 作热力学结论。

## 5. 8-spin ED oracle：受控极限的独立数值核对

建议的最小 oracle 是开链键序列

$$
[1,1,\alpha,\beta,\alpha,1,1],
$$

即 trimer--dimer--trimer 的 8 个 spin-$1/2$，而不是两个完整五聚体。这样可以去除完整 $L=10$ 链两端未配对自旋对 bulk mediator 的混入。其组合基块维数为

$$
\dim(S^z=0)=\binom84=70,
\qquad
\dim(S^z=1)=\binom85=56.
$$

这项核对已由 NumPy 自定义 bit-sector 与独立 full-Kronecker Hamiltonian 构造完成，结果位于 `results/autoresearch_v5_20260919/near_zero_alpha_oracle_v2/`。共 42 个非零预注册网格点、3 个 $\alpha=0$ 点和 2 个有限-$\alpha$ 对照点，共 47 点；11 项单元测试通过。两种构造是同一 Hamiltonian 的独立实现核对，不是第二种多体方法。

所有 validation gates 和 6 组渐近 gates 均通过。最小 $|\alpha|$ 的 6 组相对误差为 $0.143\%$--$0.649\%$，并相对下一档至少改善 25%；两个有限-$\alpha$ 对照 $(\alpha,\beta)=(-0.10,0.25),(-0.175,0.25)$ 的预测偏差分别为 $-36.1351\%$ 和 $-53.8550\%$，不套用渐近门。最大构造差为 $0$，最大总 $S^z$ 误差为 $3.55\times10^{-15}$，最大本征残差为 $3.69\times10^{-15}$。

该 oracle 核对的是 8-spin 中 $E_0(S^z=1)-E_0(S^z=0)$ 的受控极限交换，不把它等同于完整 OBC 链的 $S^z$ gap。它支持上述局部解析系数在小 $|\alpha|$ 下的数值一致性，但不验证完整链热力学极限，也不验证有限-$\alpha$ 全频或绝对归一化谱权重。

## 6. 证据边界与参考

- 上述 $J_{\mathrm{eff}}$、交叉项、自能常数和 $F(q)$ 是候选解析推导；oracle 只核对局部小系统交换系数，不把它升级为全域机制。
- [trimer primary](https://www.nature.com/articles/s41535-021-00416-4) 只用于 trimer 双重态到有效 spin-$1/2$ 的一般投影背景，不支撑本项目的具体系数或二阶交换。
- [LSM reference](https://arxiv.org/abs/1808.08740) 只用于“唯一对称有隙基态的约束”这一逻辑边界，不支撑全域 gapless、$c=1$ 或本文的微扰系数。
- 本 note 不把候选受控极限命名为 crossover 的证明，也不把它写成论文已确认的新相机制；局部 ED 已通过；完整链和有限 α 外推仍待验证。
