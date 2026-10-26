# 投稿收尾：来源恢复与历史 CV 显式残差复核

日期：2026-10-04。范围仅为本地原始资料恢复、哈希核查和现存 correction-vector (CV) 保存解的残差重验；没有重新求解 L=40 CV，没有远程操作，没有修改原始谱值或选定热图。

## 收尾结论

1. 先前缺失的六份 k=12 终态凭证和对应原始运行目录已经从项目归档恢复。全部文件逐项匹配此前登记的 SHA-256；该来源缺口已关闭。
2. 当前历史十一点 CV 数据的源目录中，只有 omega/J1=0 和 0.35 两份完整保存解可直接重验。两点显式相对残差分别为 1.3168951e-6 和 5.0793971e-6，均小于旧验收线 1e-5；不能把这一结果外推到其余九点。
3. omega=0 旧记录中的 residual=0 不能作为精确为零的证据。现在直接构造残差，得到非零值，但该点没有因此被判为不合格。强度保持不变。
4. 建议旧 CV 对照不再承担主文的核心验证：它属于 alpha=0.23、beta=0.5、q=pi、eta=0.1 的历史中心源 TEBD 对照，与新 alpha=+/-0.5 的完整动量谱不是同一协议。可以保留资料和本审计，不必为保留旧图继续扩大 CV 补算。

## k=12 恢复凭证

恢复位置：`results/submission_20261002/provenance/recovered/`。原始归档未改动，未覆盖回旧原始路径。

| 内容 | 数量与大小 | 核查结果 |
|---|---|---|
| fetch/finalize 终态凭证 | 6 文件，215,942 bytes | 匹配 `closeout_mechanism_source_data_audit_20260920.json` 中的历史大小和哈希 |
| alpha=-0.10、beta=0.25、L=80、k=12 原始运行 | 42 文件，12,868,637 bytes | 全部匹配历史 finalize/summary.json 的文件集合、大小和哈希 |
| 原始运行内部校验表 | 39 个数据/日志文件，另有 3 个校验表文件 | 39 个文件通过内部校验；3 个校验表自身也匹配历史终态记录 |
| 原 run_spec 与计算脚本 | 1 个 run_spec 和 5 个脚本 | 当前原路径文件全部匹配运行时历史哈希 |

原始 run 包含两种初态的 Sz=0 保存态、熵剖面、结构因子、键关联、字符串关联、Schmidt 谱、两个自旋扇区的 sweep 历史以及日志和配置。该集合与历史终态清单一致；不额外声称原运行保存了清单之外的态或环境文件。

六份终态文件是 `fetch.preview.json`、`fetch.receipt.json`、`validator.pass.json`、`summary.json`、`comparison.json` 和 finalize 的 `checksums.sha256`。原 run_spec 仍位于 `results/autoresearch_v5_20260920/static_krylov_k12_r1/parameter-scan.run_spec.json`。

恢复证据的意义是确认来源、原始观测量与历史比较可复核，不是新增物理结论。原 finalize 明确标记 `audit_only`、`claim=none`。单个 L=80 参数点的 k=8 到 k=12 稳定性，不能代替整个负耦合区或混合求解器尺寸序列的收敛性。

机器可读总清单：`results/submission_20261002/provenance/audit.json`，schema 为 `submission_provenance_audit/v2`。审计脚本现在会拒绝原始集合缺失、历史哈希不符、恢复副本内容不同或 CV 复验输入被更改的情况。

## CV 核验方法

完全沿用保存解对应的模型、开放边界、能量和源归一化：

\[
b=\frac{1}{\sqrt L}\sum_j e^{iqj}S_j^z|\psi_0\rangle,
\qquad
r=(\omega+E_0+i\eta)x-Hx-b,
\qquad
\epsilon=\|r\|/\|b\|.
\]

这里使用原始保存的 b，不重新构造或重新归一化源，也不把旧非连通源改称新连通源。站点索引、动量、参数和链长均核对；复验 Hamiltonian 源码哈希与历史版本相同。

先不截断地应用 H，再用 direct-sum 相加构造 r，将其正交中心移至第一个张量，以中心张量的 Frobenius 范数求残差。此方法不使用若干大数相减再截零的 residual-squared 展开式。所谓“不截断”参考仍是双精度张量计算，不是严格区间算术证明。

随后分别用 cutoff=1e-12 和 1e-16 计算 Hx，并截断相加后的残差，单独测量 MPO 应用误差、MPS 相加误差和总偏差。总偏差与两项范数之和相容。粗 cutoff 的偏差远大于待检验残差，因此最终判定使用不截断参考值，不能只凭两条带截断结果看起来接近就宣布收敛。

## 小系统基准

L=10、alpha=0.23、beta=0.5 的稠密 Hamiltonian 与 MPS 对照：

- 稠密线性代数残差：4.0200e-15。
- 不截断 MPS 显式残差：3.6889e-14。
- 强度复数内积相对偏差：3.1305e-15。
- `smoke_pass=true`。此基准新解的是小系统稠密方程，不是重算 L=40 历史谱。

完整记录：`results/submission_20261002/provenance/cv_smoke_20261004/verification.toml`。

## L=40 实际结果

共同参数：alpha=0.23、beta=0.5、q/pi=1、eta=0.1，单线程 Julia 1.11.5 和单线程 BLAS。两次复验从同一个项目 Hamiltonian 构造模型，但分别使用各自历史运行的基态能量、源和保存解。

| omega/J1 | 原报告相对残差 | 不截断显式相对残差 | 重算强度 | 原强度 |
|---|---:|---:|---:|---:|
| 0 | 0 | 1.3168950955e-6 | 1.8189085796516546 | 1.8189085796516546 |
| 0.35 | 5.2922021893e-6 | 5.0793970706e-6 | 0.3680495733571375 | 0.3680495733571379 |

| omega/J1 | cutoff | 检验 maxdim | 带截断相对残差 | 与不截断残差向量的相对偏差 | 应用与相加误差范数之和 |
|---|---:|---:|---:|---:|---:|
| 0 | 1e-12 | 1200 | 4.3669e-4 | 4.3669e-4 | 4.3669e-4 |
| 0 | 1e-16 | 1200 | 4.2015e-6 | 4.1904e-6 | 4.1904e-6 |
| 0.35 | 1e-12 | 600 | 1.9124e-4 | 1.9120e-4 | 1.9122e-4 |
| 0.35 | 1e-16 | 600 | 4.7241e-6 | 1.9294e-6 | 2.1302e-6 |

保存解实际最大键维分别为 301、305；不截断应用 H 后为 1505、1525，不截断残差为 1970、1989。记录中的计算耗时分别为 165.43 s 和 219.82 s，峰值 RSS 分别约 3.12 GB 和 3.81 GB，均在单次十分钟预算内。完整数值、输入哈希、脚本哈希和运行环境见：

- `results/submission_20261002/provenance/cv_w000_20261004/verification.toml`
- `results/submission_20261002/provenance/cv_w035_20261004/verification.toml`

当前十一点源目录中未得到完整保存解直接核验的九个 omega/J1 是 0.05、0.10、0.15、0.20、0.25、0.30、0.55、1.00、1.50。前六点的解曾被同一 run 的最新 checkpoint 覆盖；后三个源目录只有谱结果文件而没有所需基态、源和解的完整组合。本轮未对所有其他历史目录作穷尽搜索，也没有重新求解这些点，不能把缺少复验误写成已证实数值错误。

即使整个旧十一点曲线都得到残差复验，它也不自动验证新 J2=+/-0.5 的整图。重写论文时更有价值的验证是新完整动量协议自身的小系统 ED 对照、关键动量独立精度控制及明确的有限时间分辨率，而不是保留一张协议不同的旧比较图。

## 重现方式

在项目根目录执行以下现有脚本。首次两类调用都无需下载包；复验输出目录必须是新的或空的，脚本拒绝覆盖非空结果目录。

```powershell
& .venv/Scripts/python.exe scripts/submission_20261002/audit_provenance.py

& D:/program/Julia-1.11.5/bin/julia.exe --threads=1 --startup-file=no --project=. scripts/submission_20261002/check_cv_residual.jl --smoke results/submission_20261002/provenance/cv_smoke_repeat

& D:/program/Julia-1.11.5/bin/julia.exe --threads=1 --startup-file=no --project=. scripts/submission_20261002/check_cv_residual.jl results/autoresearch_v5_20260806/round43_qpi_cv_lowfreq_desc_fetch_20260806_1815/cell-l40-qpi-lowfreq-desc results/submission_20261002/provenance/cv_w000_repeat 0.1 1200

& D:/program/Julia-1.11.5/bin/julia.exe --threads=1 --startup-file=no --project=. scripts/submission_20261002/check_cv_residual.jl results/autoresearch_v5_20260802/round21_cv_triplet_warmstart/cell-0002-L40-qpi-w025-w035 results/submission_20261002/provenance/cv_w035_repeat 0.1 600
```

重新运行来源审计会只登记实际已生成且输入哈希仍一致的复验记录，并显式列出尚未覆盖的频点。不得用空日志、旧进程登记或脚本存在代替已完成的 `verification.toml` 结果。
