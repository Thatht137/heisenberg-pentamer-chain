# 论文完善评估与最小补证据计划

日期：2026-10-02。对象为当前 `paper_prb` 稿件及已选定的两张 L=40 完整谱图。本轮按 physics-autoresearch 做证据审计和图文整合；以下新增计算均为建议，尚未启动。

## 当前能支持什么

- 孤立五聚体的多重态、单胞反演选择规则和弱胞间耦合下的有效链投影已有解析与数值支撑。正耦合有限尺寸诊断与有效反铁磁链相容；负耦合目前支持有限尺寸主导动量重构，未确定热力学相界。
- 新完整谱对应 J1=1、J2=±0.5、J3=0.5、L=40 开放链，41 个独立动量，T=60、dt=0.05、TEBD chi=192，使用完整连通动量自相关和三角时间窗。两组均未经镜像平均、插值或图像平滑。
- 正负参数的反演相对 RMS 分别为 2.87e-6、4.49e-6；L=10 同离散积分 ED 对照的谱误差分别为 7.46e-5、3.59e-5。五个动量的 dt/2 与 chi 增大联合探针误差约为 0.79%、0.45%。这支持有限条件下的实现与稳定性，内部 accepted 不等于投稿所需的全部收敛。
- 当前 FWHM 为 0.09277 J1，大于正负有限链自旋隙 0.05562 J1、0.001092 J1。两张图可以比较整体谱权分布，不能据此认定极低能峰已分开，也不能把有限链隙当作体相隙。

来源：[完整谱协议](D:/Project/1x5_Heisenberg_Pentamer/docs/fullq_dsf_protocol_20261001.md)、[验收数据](D:/Project/1x5_Heisenberg_Pentamer/figures/fullq_dsf_20261001/qa.json)、[既有主张边界](D:/Project/1x5_Heisenberg_Pentamer/docs/manuscript_claim_evidence_map_20260919.md)。

## 五项优先补强

### 1. 先修复图文对应与复现凭证

旧 Fig7 实际为七点图，正文却写十一点。本轮已改用现存的 `round43_fig8_final_20260806_v2.png` 十一点图，并核对哈希和 PDF 页面。Fig9 仍显示旧 k=3 数据，下一步应加入受控 k=8 端点并明确标记求解器设置；不得把旧尺寸与新端点拼作统一收敛的 scaling。旧 Fig8 图内“finite-size crossover”标题也应在后续重绘时改为中性的有限尺寸动量重构，避免被误读为已确定热力学性质。

本轮按既有来源清单复核：positive 20/20、dynamics 36/36、negative 12/12、closeout 42/48 文件存在且哈希匹配。缺失的是 k=12 控制的六个 fetch/finalize 终态原始文件，目前可见 closeout 状态摘要。这不等于计算没有完成，但投稿前需恢复原始文件、验证哈希并重做关键数值比对；恢复前不能把状态摘要当成完整独立复现。

来源：[正区来源审计](D:/Project/1x5_Heisenberg_Pentamer/results/research_progress/positive_local_source_data_audit_20260920.json)、[动力学来源审计](D:/Project/1x5_Heisenberg_Pentamer/results/research_progress/dynamics_source_data_audit_20260920.json)、[负区来源审计](D:/Project/1x5_Heisenberg_Pentamer/results/research_progress/negative_phase_source_data_audit_20260920.json)、[收尾来源清单](D:/Project/1x5_Heisenberg_Pentamer/results/research_progress/closeout_mechanism_source_data_audit_20260920.json)、[状态摘要](D:/Project/1x5_Heisenberg_Pentamer/results/research_progress/project_closeout_status_20260919.json)。

### 2. 复核历史 CV 的真实残差

低频五点的 residual=0 是原始报告值，但实现先由大项相减得到 residual²，再截到非负，因此可能受相消影响。先使用保存的 correction-vector 解直接构造 Ax-b，检查其范数及 MPO/MPS 截断敏感性。若只存有最新频点的解，只能复核该点，其余需恢复或重算。历史十一点曲线仍可作有限协议下的比较，不应宣称它已严格认证新完整动量方案。

来源：[残差缺口](D:/Project/1x5_Heisenberg_Pentamer/docs/dynamics_source_data_readme_20260920.md:22)、[残差实现](D:/Project/1x5_Heisenberg_Pentamer/scripts/autoresearch_v5/cv_dsf_resumable.jl:67)。

### 3. 对核心谱结构补时间、截断和尺寸证据

现有探针 q/pi=0.4、0.7、1、1.3、1.6 仅覆盖三个不等价反演位置，未直接覆盖负区关键的 0.2pi、0.6pi；dt 与 chi 同时变化，不能分别归因。优先补关键动量的一变量控制，再做较长时间及少量更长链切片。T=120 的理论 FWHM 约 0.04639 J1，仍不能分辨 0.001092 J1 的负区有限链隙。

可先用已有 C(q,t) 和静态源范数核对谱积分、谱矩与截窗敏感性。正频 0 至 4 J1 的有限区间积分不是完整和规则，必须说明负频泄漏、高频尾及离散积分范围。

来源：[探针与误差](D:/Project/1x5_Heisenberg_Pentamer/figures/fullq_dsf_20261001/qa.json:54)、[色标与分辨率说明](D:/Project/1x5_Heisenberg_Pentamer/figures/fullq_visibility_clean_20261002/README.md)。

### 4. 补局域多重态与完整链谱支的定量连接

目前新谱使用总连通 Sz 算符，没有分多重态通道。孤立胞暗态和局域谱权不能直接证明有限胞间耦合下的完整链谱支归属。若将归属作为论文核心，需从弱耦合连续跟踪，或计算投影通道的谱权与混合；否则将其保持为与局域层级相容的解释。

定义上应显式区分物理动量 q 与胞动量 Q=5q mod 2pi。采用当前归一化时，一阶投影为 Sphys(q,omega)≈F(q)Seff(5q,omega)/5。负区 0.6pi 的形状因子只是在折叠反铁磁动量之间最大，不是整个布里渊区的 F(q) 最大值。有效反铁磁耦合的正号来自 beta>0 与相等端点系数，不能归因于偶宇称本身。

已有三聚体研究用扰动理论、截断子空间谱与数值 DSF 对照识别局域支；四聚体研究也将 QRG/扰动色散与 DSF 进行定量比较。这给出本项目补强归属的可借鉴路线，不要求借用其准粒子名称或相标签。[三聚体原文](https://www.nature.com/articles/s41535-021-00416-4)、[四聚体原文](https://www.nature.com/articles/s41535-026-00855-x)。

来源：[新谱算符](D:/Project/1x5_Heisenberg_Pentamer/scripts/compute_fullq_dsf.jl:47)、[折叠动量实际比较](D:/Project/1x5_Heisenberg_Pentamer/scripts/autoresearch_v5/analyze_negative_phase_independent_observables.py:332)。

### 5. 统一负区有限尺寸协议，收窄相与中央荷表述

L=40、60 仍有旧 k=3 数据，受控 L=80 使用 k=8/12；k 是 Krylov 维度，不是 MPS chi。敏感点曾出现明显的求解器依赖，故不能由一个端点通过就排除全负区数值影响。若讨论相界或中央荷，先补统一协议尺寸序列及实际生效的 cutoff/chi 检查；若只保留有限尺寸动量重构，可保守写作，不必继续全域扫相。

正区“无内部边界”须限已采样正耦合内域，alpha=0、beta=0 解耦轴不能归入同一临界有效链结论；负区两个诊断不重合也不能证明热力学上必为 crossover。

来源：[求解器影响与尺寸限制](D:/Project/1x5_Heisenberg_Pentamer/docs/manuscript_claim_evidence_map_20260919.md:39)、[旧与新设置审计](D:/Project/1x5_Heisenberg_Pentamer/docs/post_krylov_claim_audit_20260920.md)。

## 最小建议计算清单：均未启动

| 顺序 | 建议范围 | 要回答的问题与停止条件 |
|---|---|---|
| A | 先恢复 k=12 原始凭证；从现有 CV 解复核低频残差 | 先区分缺文件与缺验证。能用存档完成的检查不重跑；无法重验的频点明确列缺口。 |
| B | 新 DSF 两组参数，优先 q/pi=0.2、0.6、1；T=60 下分别固定 dt 改 chi、固定 chi 改 dt | 直接检验本文使用的峰位和频段谱权。预先固定容差，未稳定前不扩大动量扫描。 |
| C | B 稳定后，仅关键切片延长至 T=120；再选 L=60 作同窗口对照 | 分开判断时间展宽和尺寸影响。只有主张确需体相趋势时才加 L=80；不承诺解析超小负区隙。 |
| D | alpha=-0.10、beta=0.25 优先补统一求解器的 L=40、60，并利用已有受控 L=80 | 纠正被 k 敏感性污染的尺寸趋势；若主张扩大到重构区，再补一个相邻参数作对照。 |
| E | 仅在保留“确定谱支归属”时，增加少量弱 beta 点或局域通道投影 | 检查谱峰如何连接孤立胞激发并量化混合。若归属不稳定，保留描述性谱结构结论。 |

计算前应依据现有小任务计时冻结资源和容差；本清单不代表已提交任务或无限算力授权。

## 无新计算即可完成的交付

- 使用用户选定的两张无页脚整图，保留坐标和图内 J2/J3；asinh 映射、链长、时间窗与误差放在论文图注或独立 README，不加回图内。
- 将旧中心源谱与新完整动量谱分清；保留旧历史资料，不把旧验收指标挪用到新图。
- 用现有数据整理主张、参数、归一化、误差、来源路径与哈希表，并完成整篇 PDF 的图号、引用和页面核对。
- 作者、单位、通讯信息、资助、真实仓库/归档 DOI 及代码和数据 license 尚缺。须由真实记录补齐，不能制造公开存档或作者信息。

论文的稳妥主线是“局域多重态和选择规则如何组织有限链响应，并伴随正负耦合下的动量谱权重构”。若坚持进一步宣称确定准粒子支、热力学相界或精确低能隙，应先完成相应补证据项；漂亮热图与内部验收不能代替这些检验。
