# 服务器运行说明

本文档说明 Linux 服务器上的环境配置、计算入口和结果传输。

## 运行环境

服务器计算通常分两种：

- 登录节点：用来传文件、装环境、提交任务。不要在这里跑长计算。
- 计算节点：真正跑长任务的机器。通常通过 SLURM、PBS 等调度系统申请。

常见命令：

```bash
ssh 用户名@服务器地址
```

```bash
sbatch phase_diagram.sbatch
```

```bash
squeue -u $USER
```

```bash
tail -f logs/phase_diagram_%j.out
```

## 推荐 Julia 版本

本项目的 `Manifest.toml` 是用 Julia `1.11.5` 生成的，服务器上优先使用 Julia 1.11.x。

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
git clone https://github.com/Thatht137/heisenberg-pentamer-chain.git
cd heisenberg-pentamer-chain
```

通过 `scp` 或 `rsync` 传输项目时，可排除本机 `.venv` 目录。

## 安装 Julia 依赖

进入项目根目录：

```bash
cd heisenberg-pentamer-chain
julia --project=. -e 'using Pkg; Pkg.instantiate()'
```

这一步会根据 `Manifest.toml` 安装固定版本依赖。第一次可能比较慢。

离线服务器需要先在可联网机器准备 Julia depot 缓存，再复制到服务器。

## 先做最小验证

先跑单元测试：

```bash
julia --project=. test/runtests.jl
```

再跑一个小脚本：

```bash
julia --project=. scripts/01_single_pentamer.jl
```

它会写出：

```text
data/single_pentamer_energies.dat
```

## 计算入口

计算与检查入口：

1. `test/runtests.jl`
2. `scripts/01_single_pentamer.jl`
3. `scripts/02_dmrg_chain.jl`
4. `scripts/03_phase_diagram.jl`
5. `scripts/04_dsf.jl`

其中 `03_phase_diagram.jl` 和 `04_dsf.jl` 是主要计算脚本。特别是 `04_dsf.jl` 会对多个 `(q, omega)` 点求修正向量，耗时明显更长。

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

将下例保存为 phase_diagram.sbatch，并按计算规模与服务器配置调整资源请求。谱函数作业可保存为 dsf.sbatch，将最后一行入口换为 scripts/04_dsf.jl。

```bash
#!/bin/bash
#SBATCH --job-name=pentamer
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=04:00:00
julia --project=. scripts/03_phase_diagram.jl
```


相图计算：

```bash
sbatch phase_diagram.sbatch
```

谱函数计算：

```bash
sbatch dsf.sbatch
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

结果传输示例：

```bash
mkdir -p data
scp -C username@server:/path/to/project/data/dsf_spectrum.jld2 ./data/
```

将 `username`、`server` 和 `/path/to/project` 替换为实际连接参数。使用自定义 SSH 端口时，给 `scp` 添加 `-P` 选项。

运行前可备份旧结果，避免覆盖：

```bash
mkdir -p data/archive
cp data/phase_diagram.jld2 data/archive/phase_diagram_$(date +%Y%m%d_%H%M%S).jld2
```

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

这是正常的。`compute_ground_state` 里 `outputlevel=1` 会输出 sweep 过程。批量计算时可设置 `outputlevel=0` 减少日志。

## 运行前检查

- `julia --version` 是 1.11.x。
- `julia --project=. -e 'using Pkg; Pkg.instantiate()'` 成功。
- `julia --project=. test/runtests.jl` 通过。
- `logs/` 目录存在。
- `data/` 目录有写权限。
- 小任务能正常输出结果。
- 长任务通过调度系统提交，而不是在登录节点硬跑。
