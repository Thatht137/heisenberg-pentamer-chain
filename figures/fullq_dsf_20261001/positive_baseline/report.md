# L=40 完整动量谱复算

使用完整连通动量算符，自相关包含 t=0；三角时间窗，不做高斯平滑、镜像平均或数据裁剪。

色标为共同线性范围 0 至 3；超过 vmax 的数值仅显示饱和，原始谱值不变。

## J2=0.5, J3=0.5
状态：symmetry_checked_draft。L=40，dt=0.05，T=60.0，TEBD χ=192。
反演相对 RMS：2.875e-06；最大范数漂移：0.001399；负谱绝对权重比例：-0。
基态方差/格点：5.551e-12；时间窗 FWHM≈0.09277 J1。
低于此分辨率的峰间距不能仅凭图认定已分开。
[全能段 PNG](https://github.com/Thatht137/heisenberg-pentamer-chain/blob/codex/archive-20261026/figures/fullq_dsf_20261001/positive_baseline/Sqw_L40_J2%3D0.5_J3%3D0.5_symmetry_checked_draft_full.png) | [低能 PNG](https://github.com/Thatht137/heisenberg-pentamer-chain/blob/codex/archive-20261026/figures/fullq_dsf_20261001/positive_baseline/Sqw_L40_J2%3D0.5_J3%3D0.5_symmetry_checked_draft_low.png)；同名 PDF/SVG 可编辑文字。

开放有限链自旋隙 E(Sz=1)-E(Sz=0)：0.055622441 J1；χ=512/768 与 cutoff=1e-12/1e-13 联合预算差异 6.441e-12 J1。
这是有限链能级差，可能受边界态影响；不是热力学极限体相能隙，预算差异也不是严格误差界。
该能隙小于当前时间窗的 FWHM，不宣称热图已将其与零频区分。
