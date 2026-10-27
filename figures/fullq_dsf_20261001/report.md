# L=40 完整动量谱复算

使用完整连通动量算符，自相关包含 t=0；三角时间窗，不做高斯平滑、镜像平均或数据裁剪。

色标为共同线性范围 0 至 3；超过 vmax 的数值仅显示饱和，原始谱值不变。

## J2=0.5, J3=0.5
状态：accepted。L=40，dt=0.05，T=60.0，TEBD χ=192。
反演相对 RMS：2.875e-06；最大范数漂移：0.001399；负谱绝对权重比例：-0。
基态方差/格点：5.551e-12；时间窗 FWHM≈0.09277 J1。
低于此分辨率的峰间距不能仅凭图认定已分开。
[全能段 PNG](https://github.com/Thatht137/heisenberg-pentamer-chain/blob/codex/archive-20261026/figures/fullq_dsf_20261001/Sqw_L40_J2%3D0.5_J3%3D0.5_accepted_full.png) | [低能 PNG](https://github.com/Thatht137/heisenberg-pentamer-chain/blob/codex/archive-20261026/figures/fullq_dsf_20261001/Sqw_L40_J2%3D0.5_J3%3D0.5_accepted_low.png)
[全能段 PDF](https://github.com/Thatht137/heisenberg-pentamer-chain/blob/codex/archive-20261026/figures/fullq_dsf_20261001/Sqw_L40_J2%3D0.5_J3%3D0.5_accepted_full.pdf) | [全能段 SVG](https://github.com/Thatht137/heisenberg-pentamer-chain/blob/codex/archive-20261026/figures/fullq_dsf_20261001/Sqw_L40_J2%3D0.5_J3%3D0.5_accepted_full.svg)；低能图同样提供 PDF/SVG。
[原始谱 CSV](https://github.com/Thatht137/heisenberg-pentamer-chain/blob/codex/archive-20261026/results/fullq_dsf_20261001/L40_positive/spectrum.csv) | [计算元数据](https://github.com/Thatht137/heisenberg-pentamer-chain/blob/codex/archive-20261026/results/fullq_dsf_20261001/L40_positive/run_metadata.toml)

dt/2 与 χ 增大的联合对照：谱 RMS 差异 0.007924；低能权重差异 0.001047；最大主峰漂移 0 J1。

开放有限链自旋隙 E(Sz=1)-E(Sz=0)：0.055622441 J1；χ=512/768 与 cutoff=1e-12/1e-13 联合预算差异 6.441e-12 J1。
这是有限链能级差，可能受边界态影响；不是热力学极限体相能隙，预算差异也不是严格误差界。
该能隙小于当前时间窗的 FWHM，不宣称热图已将其与零频区分。

## J2=-0.5, J3=0.5
状态：accepted。L=40，dt=0.05，T=60.0，TEBD χ=192。
反演相对 RMS：4.492e-06；最大范数漂移：0.003771；负谱绝对权重比例：-0。
基态方差/格点：5.36e-12；时间窗 FWHM≈0.09277 J1。
低于此分辨率的峰间距不能仅凭图认定已分开。
[全能段 PNG](https://github.com/Thatht137/heisenberg-pentamer-chain/blob/codex/archive-20261026/figures/fullq_dsf_20261001/Sqw_L40_J2%3D-0.5_J3%3D0.5_accepted_full.png) | [低能 PNG](https://github.com/Thatht137/heisenberg-pentamer-chain/blob/codex/archive-20261026/figures/fullq_dsf_20261001/Sqw_L40_J2%3D-0.5_J3%3D0.5_accepted_low.png)
[全能段 PDF](https://github.com/Thatht137/heisenberg-pentamer-chain/blob/codex/archive-20261026/figures/fullq_dsf_20261001/Sqw_L40_J2%3D-0.5_J3%3D0.5_accepted_full.pdf) | [全能段 SVG](https://github.com/Thatht137/heisenberg-pentamer-chain/blob/codex/archive-20261026/figures/fullq_dsf_20261001/Sqw_L40_J2%3D-0.5_J3%3D0.5_accepted_full.svg)；低能图同样提供 PDF/SVG。
[原始谱 CSV](https://github.com/Thatht137/heisenberg-pentamer-chain/blob/codex/archive-20261026/results/fullq_dsf_20261001/L40_negative_local/spectrum.csv) | [计算元数据](https://github.com/Thatht137/heisenberg-pentamer-chain/blob/codex/archive-20261026/results/fullq_dsf_20261001/L40_negative_local/run_metadata.toml)

dt/2 与 χ 增大的联合对照：谱 RMS 差异 0.004499；低能权重差异 0.0007918；最大主峰漂移 0 J1。

开放有限链自旋隙 E(Sz=1)-E(Sz=0)：0.0010924445 J1；χ=512/768 与 cutoff=1e-12/1e-13 联合预算差异 2.025e-13 J1。
这是有限链能级差，可能受边界态影响；不是热力学极限体相能隙，预算差异也不是严格误差界。
该能隙小于当前时间窗的 FWHM，不宣称热图已将其与零频区分。

服务器部分时间段独立核验：17 个动量单元；最大关联函数相对差异 1.104e-11。
服务器部分关联仅用于核验，没有拼接或补入最终谱。

## 复算与核查
[详细验收数据](https://github.com/Thatht137/heisenberg-pentamer-chain/blob/codex/archive-20261026/figures/fullq_dsf_20261001/qa.json) | [计算协议](https://github.com/Thatht137/heisenberg-pentamer-chain/blob/codex/archive-20261026/docs/fullq_dsf_protocol_20261001.md) | [最终源码快照](https://github.com/Thatht137/heisenberg-pentamer-chain/blob/codex/archive-20261026/results/fullq_dsf_20261001/source_final_20261001.tar)
accepted 表示通过本次内部数值标准，不代表热力学极限或所有低能峰已可分辨。
