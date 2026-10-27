# 负侧 DSF 服务器上传与运行步骤

本说明对应当前优先服务器任务：

```text
alpha = -0.50, -0.10, -0.05, 0.23
beta = 0.5
L = 80
dt = 0.05
tmax = 30
```

运行入口：

```bash
bash scripts/run_negative_dsf_validation_server.sh 4
```

## 一、优先使用 Git 上传

### 本地推送

在 Windows 项目目录运行：

```powershell
cd D:\research\1x5_Heisenberg_Pentamer
git status
git push origin analysis/string-distance
```

如果还没有远程仓库，先在 GitHub、GitLab 或 Gitee 创建一个私有仓库，然后：

```powershell
git remote add origin 你的仓库地址
git push -u origin analysis/string-distance
```

### 服务器克隆

```bash
cd /home/$USER
git clone 你的仓库地址 1x5_Heisenberg_Pentamer
cd 1x5_Heisenberg_Pentamer
git switch analysis/string-distance
```

以后同步更新：

```bash
git pull --rebase
```

## 二、没有远程仓库时使用 SCP

如果 SSH 端口为 `6000`，在本地 PowerShell 运行：

```powershell
scp -P 6000 -C -r `
  D:\research\1x5_Heisenberg_Pentamer `
  用户名@服务器地址:/home/用户名/
```

这种方式会上传很多不需要的图片和本地文件。更推荐先打包必要内容：

```powershell
tar -czf D:\tmp\pentamer_server.tar.gz `
  --exclude=.git `
  --exclude=.venv `
  --exclude=paper `
  --exclude=figures `
  --exclude=references `
  -C D:\Project 1x5_Heisenberg_Pentamer

scp -P 6000 -C D:\tmp\pentamer_server.tar.gz `
  用户名@服务器地址:/home/用户名/
```

服务器解压：

```bash
cd /home/$USER
tar -xzf pentamer_server.tar.gz
cd 1x5_Heisenberg_Pentamer
```

## 三、服务器环境初始化

登录：

```bash
ssh -p 6000 用户名@服务器地址
```

检查调度器和 Julia：

```bash
which sbatch
which julia
julia --version
```

如果服务器使用 module：

```bash
module avail julia
module load julia/1.11.5
```

进入项目并安装依赖：

```bash
cd /home/$USER/1x5_Heisenberg_Pentamer
julia --project=. -e 'using Pkg; Pkg.instantiate(); Pkg.precompile()'
```

第一次安装和预编译可能需要较长时间。

## 四、运行前验证

先运行测试：

```bash
julia --project=. test/runtests.jl
```

当前预期结果为：

```text
54 passed
```

检查脚本语法和输出目录：

```bash
bash -n scripts/run_negative_dsf_validation_server.sh
mkdir -p logs/negative_dsf_validation
```

先只运行一个参数点进行试算：

```bash
PENTAMER_ALPHA=-0.50 \
PENTAMER_BETA=0.5 \
PENTAMER_N_UNITS=16 \
PENTAMER_TSTEP=0.05 \
PENTAMER_N_STEPS=20 \
PENTAMER_OUTPUT_TAG=smoke \
julia --project=. scripts/05_tebd_pentamer_server.jl
```

试算只用于确认环境和输出，不用于物理分析。

## 五、正式运行

### 有 SLURM

不要直接在登录节点执行长任务。申请一个交互计算节点：

```bash
srun --pty \
  --cpus-per-task=16 \
  --mem=32G \
  --time=12:00:00 \
  bash
```

进入计算节点后：

```bash
cd /home/$USER/1x5_Heisenberg_Pentamer
bash scripts/run_negative_dsf_validation_server.sh 4
```

更正式的方式是为脚本编写 `sbatch` 文件。服务器的分区名、账号和时间限制未知，
因此提交头需要根据服务器实际规则填写。

### 没有调度器

确认管理员允许后台计算后：

```bash
cd /home/$USER/1x5_Heisenberg_Pentamer
mkdir -p logs
nohup bash scripts/run_negative_dsf_validation_server.sh 4 \
  > logs/negative_dsf_master.log 2>&1 &
echo $!
```

## 六、查看运行状态

查看四个参数点日志：

```bash
tail -n 40 logs/negative_dsf_validation/*.log
```

持续查看某个点：

```bash
tail -f logs/negative_dsf_validation/a-0.5_b0.5_L80_t30.log
```

检查进程：

```bash
ps -u $USER -o pid,etime,%cpu,%mem,cmd | grep julia
```

检查输出：

```bash
ls -lh data/*L80_t30*.jld2
```

当前脚本具有文件级断点保护。已经存在对应 `NDSF` 或 `Sqw` 文件时会跳过该阶段。

## 七、下载结果

在本地 PowerShell 创建目录：

```powershell
New-Item -ItemType Directory -Force `
  D:\research\1x5_Heisenberg_Pentamer\data\server_negative_dsf
```

下载结果：

```powershell
scp -P 6000 -C `
  用户名@服务器地址:/home/用户名/1x5_Heisenberg_Pentamer/data/*L80_t30*.jld2 `
  D:\research\1x5_Heisenberg_Pentamer\data\server_negative_dsf\
```

下载日志：

```powershell
scp -P 6000 -C -r `
  用户名@服务器地址:/home/用户名/1x5_Heisenberg_Pentamer/logs/negative_dsf_validation `
  D:\research\1x5_Heisenberg_Pentamer\logs\
```

## 八、服务器运行记录

每次正式任务至少记录：

```text
Git commit:
服务器名称:
Julia 版本:
CPU/内存:
开始时间:
结束时间:
脚本:
参数:
输出文件:
异常:
```

最关键的是 Git commit。以后发现数据异常时，只有知道生成数据所使用的代码版本，
才能可靠复现。
