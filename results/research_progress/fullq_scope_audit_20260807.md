# Full-q 重规划范围核对

结论：当前 eta=0.20 批次没有越出论文的模型和正耦合研究范围；它是同一 Hamiltonian 上的 TEBD 独立动力学交叉分支，不冒充论文主 Krylov 谱。

## 核对项

- 模型：五站点单胞 Heisenberg 链，`J1=1`，`alpha=J2/J1`，`beta=J3/J1`；与 `paper/sections/model_methods.tex` 的 Hamiltonian 一致。
- 参数范围：本批次 `alpha=1.0`、`beta=0.1`，均为非负；全项目固定排除负 alpha。
- 尺寸：`L=40=5×8`，开放边界；属于论文有限链范围。
- 动量：`q=0..2π` 的 121 点，是对论文重点 `q=π` 的 full-q 扩展；不涉及参考 Fig.9。
- 频率：`0<=omega/J1<=3`，与论文方法段的频率窗口一致。
- 方法定位：论文主动力学方法是 Krylov 修正向量 DMRG、展宽 `eta=0.1J1`；本批次是实时 TEBD 的独立交叉检查。
- eta=0.20：只改变 TEBD 后处理时间窗的数值稳定性，不改变 Hamiltonian、alpha/beta、L、q/omega 范围；结果必须在报告中标为 robustness branch，不能替代主 Krylov 结果。
- 验收：raw negative-weight fraction 仍严格要求 `<=0.15`，不裁零、不放宽门槛。

证据：

- 论文方法：[paper/sections/model_methods.tex](../../paper/sections/model_methods.tex)
- 本批次启动脚本：[launch_weak_eta020_dt025.sh](fullq_replan_eta020_20260807/launch_weak_eta020_dt025.sh)
- 当前状态：[minimal_fullq_campaign_status_20260807.json](minimal_fullq_campaign_status_20260807.json)

