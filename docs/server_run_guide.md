# 服务器计算入门指南

本文档用于第一次把本项目放到服务器上计算。默认你使用 Linux 服务器，并且服务器上可以运行 Julia。

## 当前结论

这个项目可以在服务器上计算。理由：

- 项目是标准 Julia 工程，根目录有 `Project.toml` 和 `Manifest.toml`。
- 本地单元测试已通过：`54/54`。
- 小规模脚本 `scripts/01_single_pentamer.jl` 已成功运行并写出数据。
- 主要依赖是 `ITensors`、`ITensorMPS`、`JLD2`、`KrylovKit`，适合在 CPU 服务器上跑 DMRG 和谱函数计算。

### 当前实际服务器配置（2026-08-03）

- SSH：`wangjieren@39.96.207.180`，端口 `6000`；实际节点 `c104-ysu`。
- Julia：服务器 `1.12.3`，已通过 ITensor smoke；本地 `1.11.5` 不作为服务器生产环境依据。
- 依赖：`Project.toml`/`Manifest.toml` 哈希已核对；服务器断网时只使用既有 depot，不执行 `Pkg.add`、`Pkg.update` 或 `Pkg.instantiate`。
- 运行纪律：一次只运行一个重任务；结果必须保存 `run_config.json`、`manifest.json`、`status.json` 和 `checksums.sha256`。
- 当前项目脚本使用直连服务器和离线环境变量，不依赖本指南后文的 SLURM 示例。
- 本地 Windows Julia 的 `Pkg.activate`/预编译可能受用户目录 ACL 阻断；这类权限错误不作为模型失败，生产验收以服务器 Julia `1.12.3` 的 `54/54` 测试和 smoke 为准。

### SSH 中断时的恢复纪律

当 `:6000` 返回 `Connection refused` 时，只能说明专用 SSH 服务或端口转发暂不可用，不能据此判断 Julia 任务成功或失败。恢复后先读取 `status.json`、`progress.json` 和 `manifest.json`，确认终态后再做远端 checksum、回传和本地 validator。

客户端必须使用私钥 `~/.ssh/id_ed25519`；`.pub` 文件是公钥，不能作为 `-i` 参数。推荐只读诊断命令：

```bash
ssh -o BatchMode=yes -o ConnectTimeout=15 -p 6000 -i ~/.ssh/id_ed25519 wangjieren@39.96.207.180 'date; pgrep -af "julia|run_cv_dsf_cell" || true'
```

若 6000 端口拒绝连接，不重启、不取消、不并行启动新 Julia；保留最后可信快照，并等待端口恢复或由管理员修复转发/认证。默认 22 端口即使可达，也不能绕过专用端口的任务状态保护。

正式上服务器前，不建议直接把最大规模任务一次性提交。先跑小任务，确认环境、路径、输出和耗时。

## 你需要知道的基本概念

服务器计算通常分两种：

- 登录节点：用来传文件、装环境、提交任务。不要在这里跑长计算。
- 计算节点：真正跑长任务的机器。通常通过 SLURM、PBS 等调度系统申请。

常见命令：

```bash
ssh 用户名@服务器地址
```

```bash
sbatch scripts/submit_slurm_phase_diagram.sh
```

```bash
squeue -u $USER
```

```bash
tail -f logs/phase_diagram_%j.out
```

## Julia 版本

本项目的 `Manifest.toml` 虽在本地 Julia `1.11.5` 环境生成，但当前服务器已审计通过 Julia `1.12.3`。生产任务必须固定使用已审计的服务器版本，不在断网服务器上切换版本或重新解析依赖。

检查版本：

```bash
julia --version
```

如果服务器使用 module 系统：

```bash
module avail julia
module load julia/1.11.5
```

如果没有 Julia，需要请管理员安装，或在自己目录安装官方二进制版本。

## 上传项目

推荐用 git：

```bash
git clone <你的仓库地址> 1x5_Heisenberg_Pentamer
cd 1x5_Heisenberg_Pentamer
```

如果没有远程仓库，可以用 `scp` 或 `rsync` 上传整个目录。不要上传 `.venv`，它不是 Julia 计算需要的目录。

## 安装 Julia 依赖

进入项目根目录：

```bash
cd 1x5_Heisenberg_Pentamer
julia --project=. -e 'using Pkg; Pkg.instantiate()'
```

这一步会根据 `Manifest.toml` 安装固定版本依赖。第一次可能比较慢。

如果服务器不能联网，需要在本地或可联网机器准备 Julia depot 缓存，再复制到服务器。这个情况需要单独处理。

## 先做最小验证

先跑单元测试：

```bash
julia --project=. test/runtests.jl
```

成功时应看到类似：

```text
Test Summary: | Pass  Total
PentamerChain |   54     54
```

再跑一个小脚本：

```bash
julia --project=. scripts/01_single_pentamer.jl
```

它会写出：

```text
data/single_pentamer_energies.dat
```

## 计算顺序建议

建议按这个顺序推进：

1. `test/runtests.jl`
2. `scripts/01_single_pentamer.jl`
3. `scripts/02_dmrg_chain.jl`
4. `scripts/03_phase_diagram.jl`
5. `scripts/04_dsf.jl`

其中 `03_phase_diagram.jl` 和 `04_dsf.jl` 是正式消耗资源的脚本。特别是 `04_dsf.jl` 会对多个 `(q, omega)` 点求修正向量，耗时明显更长。

## 资源估计

目前脚本中的默认规模：

| 脚本 | 默认规模 | 建议资源 |
|---|---:|---|
| `01_single_pentamer.jl` | 32 维精确对角化 | 1 核，几分钟以内 |
| `02_dmrg_chain.jl` | 最多 `N_units=12`, `maxdim=400` | 1-4 核，4-16 GB |
| `03_phase_diagram.jl` | 11 x 10 参数网格 | 1-4 核，16-32 GB，数小时起 |
| `04_dsf.jl` | 17 x 31 谱函数网格 | 8 核，32 GB 起，可能很久 |

实际耗时取决于服务器 CPU、ITensor 编译缓存、`maxdim`、`nsweeps` 和网格密度。

## 直接在交互终端试跑

只适合短任务：

```bash
julia --project=. scripts/01_single_pentamer.jl
```

长任务不要直接在登录节点跑。

## 用 nohup 后台运行

如果服务器没有调度系统，并且允许在当前机器后台跑：

```bash
mkdir -p logs
nohup julia --project=. scripts/03_phase_diagram.jl > logs/phase_diagram.out 2>&1 &
```

查看日志：

```bash
tail -f logs/phase_diagram.out
```

## 用 SLURM 提交任务

相图计算：

```bash
sbatch scripts/submit_slurm_phase_diagram.sh
```

谱函数计算：

```bash
sbatch scripts/submit_slurm_dsf.sh
```

查看队列：

```bash
squeue -u $USER
```

取消任务：

```bash
scancel 任务号
```

## 结果文件

默认写入 `data/`：

- `single_pentamer_energies.dat`
- `phase_diagram.jld2`
- `dsf_spectrum.jld2`

新生产入口还必须在每个 run 目录原子更新 `progress.json`（默认每 30 秒）：

- DMRG/CV：当前阶段、sweep 或已完成频点、最近日志时间；
- TEBD/Fourier：step、百分比、ETA 和当前 Fourier 动量；
- 终态：`completed`、`failed` 或 `stopped`，并与 `status.json`、checksum 一起留档。

该文件只用于运行可观测性，不替代方差、残差、非负性和 checksum 验收。

如果服务器通过 FRP 转接，SSH/SCP 端口是 6000，可以在本地 Windows PowerShell 下载结果：

```powershell
New-Item -ItemType Directory -Force D:/Project/1x5_Heisenberg_Pentamer/data
scp -P 6000 -C wangjieren@中转服务器地址:/home/wangjieren/1x5/1x5_Heisenberg_Pentamer/data/dsf_spectrum.jld2 D:/Project/1x5_Heisenberg_Pentamer/data/
Get-Item D:/Project/1x5_Heisenberg_Pentamer/data/dsf_spectrum.jld2
```

这里的 `-P 6000` 是指定 SSH 端口，`-C` 是压缩传输。把 `中转服务器地址` 换成平时登录用的公网 IP 或域名。

建议每次正式计算前备份旧结果，避免覆盖：

```bash
mkdir -p data/archive
cp data/phase_diagram.jld2 data/archive/phase_diagram_$(date +%Y%m%d_%H%M%S).jld2
```

## 第一次正式计算建议

不要一上来跑最大任务。建议：

- 相图先跑较粗网格，例如少量 `alpha`、`beta` 点。
- DSF 先用 `N_units=6` 或 `8`，`eta=0.1`，少量 `q` 和 `omega` 点。
- 确认输出正常后，再增加 `N_units`、`maxdim`、`nsweeps` 和网格密度。

目前 `03_phase_diagram.jl` 和 `04_dsf.jl` 的参数写在脚本内部。正式大量扫描前，建议再把参数改成命令行参数或环境变量，并加入断点保存，避免任务中断后丢失全部结果。

## 常见问题

### `Pkg.instantiate()` 很慢

第一次安装依赖和预编译会慢，这是正常的。后续会使用缓存。

### 找不到 Julia

先运行：

```bash
which julia
module avail julia
```

如果都没有，需要安装 Julia 或联系管理员。

### 任务被杀掉

常见原因是内存不够或超过时间限制。降低 `maxdim`、减少网格点，或在提交脚本里申请更多内存和时间。

### 日志里有大量 DMRG 输出

这是正常的。`compute_ground_state` 里 `outputlevel=1` 会输出 sweep 过程。正式大批量跑时可以改成 `outputlevel=0` 减少日志。

## 上服务器前检查清单

- `julia --version` 是已审计的 1.12.3。
- 断网服务器不执行 `Pkg.add`、`Pkg.update` 或 `Pkg.instantiate`；只使用已核对的 Manifest 和 depot。
- `julia --project=. test/runtests.jl` 通过。
- `logs/` 目录存在。
- `data/` 目录有写权限。
- 小任务能正常输出结果。
- 长任务通过受控后台脚本或调度系统提交，不在登录节点前台运行。
- 新生产任务目录能生成并持续更新 `progress.json`。
