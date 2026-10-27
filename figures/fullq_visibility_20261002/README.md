# 完整谱图弱信号可见性

保留 q=0 至 2pi、omega=0 至 4J1 的完整单幅谱图和线性坐标；无插图、断轴或低能区单独放大。
弱谱权图使用两组共用的 asinh 非线性色标，范围 0 至 6，linear_width=0.02。
颜色归一化为 asinh(S/0.02)/asinh(6/0.02)，应用于全部频率和动量，不针对低能区局部修图。
色条刻度仍是原始 J1*Szz。零值仍为零，真实峰值未饱和；不按 q 分别归一化。
无高斯平滑、空间/频率插值或镜像平均，之前的线性色标全谱保留不动。
这是显示动态范围的改进，不是新增能量分辨率，也不能把增强可见的时间窗旁瓣当作新的激发支。

## J2=0.5
0 至 0.6J1 占已采样 0 至 4J1 谱积分的 41.76%。
该比例为等权动量网格加总后的有限频率区间积分，不是完整频率求和规则。
[完整谱图](https://github.com/Thatht137/heisenberg-pentamer-chain/blob/codex/archive-20261026/figures/fullq_visibility_20261002/Sqw_L40_J2%3D0.5_J3%3D0.5_full_asinh.png)

[完整谱图附色条](https://github.com/Thatht137/heisenberg-pentamer-chain/blob/codex/archive-20261026/figures/fullq_visibility_20261002/Sqw_L40_J2%3D0.5_J3%3D0.5_full_asinh_colorbar.png)

## J2=-0.5
0 至 0.6J1 占已采样 0 至 4J1 谱积分的 43.47%。
该比例为等权动量网格加总后的有限频率区间积分，不是完整频率求和规则。
[完整谱图](https://github.com/Thatht137/heisenberg-pentamer-chain/blob/codex/archive-20261026/figures/fullq_visibility_20261002/Sqw_L40_J2%3D-0.5_J3%3D0.5_full_asinh.png)

[完整谱图附色条](https://github.com/Thatht137/heisenberg-pentamer-chain/blob/codex/archive-20261026/figures/fullq_visibility_20261002/Sqw_L40_J2%3D-0.5_J3%3D0.5_full_asinh_colorbar.png)

当前 T=60 的三角时间窗 FWHM=0.09277J1。若需分辨更近的激发，应延长真实演化时间并检查截断与步长收敛。
T=120 的理论窗口 FWHM 约为 0.04639J1，但本目录没有新增该计算，也不宣称已有该分辨率。
