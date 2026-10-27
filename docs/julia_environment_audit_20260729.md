# Julia 环境审计记录

> 审计日期：2026-07-29  
> 本地项目：`D:\research\1x5_Heisenberg_Pentamer`  
> 服务器项目：`USER@server.example.org:6000:/home/USER/code/1x5_Heisenberg_Pentamer`  
> 结论：锁定项目环境可离线计算；服务器不具备可靠的离线包管理能力，禁止远端安装或更新包。

## 1. 总体结论

服务器 Julia 1.12.3 能在强制断网代理下直接加载项目模块和生产依赖，项目源码与本地使用同一份 `Project.toml` 和 `Manifest.toml`。本地 Julia 1.11.5 也能加载相同依赖版本，因此当前环境满足五轮计算要求。

需要保留三个限制：

1. 非交互 SSH 的 `PATH` 中没有 `julia` 和 `juliaup`，任务必须使用 `~/.juliaup/bin/julia` 绝对路径。
2. `Manifest.toml` 由 Julia 1.11.5 生成，服务器实际运行 Julia 1.12.3。关键小尺寸结果必须与本地 1.11.5 交叉验证。
3. 服务器在断网设置下执行 `Pkg.status()` 时曾尝试访问 General registry。生产任务不得调用 `Pkg.add`、`Pkg.update`、`Pkg.instantiate` 或 `Pkg.status`，只允许按现有 Manifest 直接加载包。

## 2. 版本与哈希

| 项目 | 本地 | 服务器 | 结论 |
|---|---:|---:|---|
| Julia | 1.11.5 | 1.12.3 | 接受；关键小尺寸跨版本检查 |
| juliaup release | 不在 PATH | 1.12.3 | 固定当前版本，不升级到提示的 1.12.6 |
| ITensors | 0.9.27 | 0.9.27 | 一致 |
| ITensorMPS | 0.4.1 | 0.4.1 | 一致 |
| JLD2 | 0.6.4 | 0.6.4 | 一致 |
| KrylovKit | 0.10.3 | 0.10.3 | Manifest 一致 |
| `Project.toml` SHA-256 | `39e917d3...dd7e` | `39e917d3...dd7e` | 一致 |
| `Manifest.toml` SHA-256 | `37a53ffd...12c` | `37a53ffd...12c` | 一致 |
| Manifest 生成版本 | 1.11.5 | 1.11.5 | 文件一致，运行版本不同 |

完整哈希：

```text
Project.toml  39e917d3ca9615132999b4ae6a9731e8b592454267e38b5779423e76a8d2dd7e
Manifest.toml 37a53ffd73db57b9db9c4ce11f6265a9a41ac2035dc421b01f9a633d893ba12c
```

## 3. 服务器 Julia 状态

服务器默认 juliaup 渠道为 `release`，实际版本为 `1.12.3+0.x64.linux.gnu`。`~/.juliaup/bin/julia` 是指向 `julialauncher` 的符号链接，生产运行器使用：

```text
/home/USER/.juliaup/bin/julia +release --startup-file=no --project=.
```

服务器 depot 状态：

| 目录 | 占用 |
|---|---:|
| `~/.julia/packages` | 123 MiB |
| `~/.julia/artifacts` | 894 MiB |
| `~/.julia/compiled` | 381 MiB |
| `~/.julia/registries` | 9.5 MiB |

General registry 文件时间为 2025-12-23。当前计算所需包和 artifact 已在 depot 中，无需下载。

## 4. 强制断网验证

验证时同时设置：

```text
JULIA_PKG_OFFLINE=true
JULIA_PKG_SERVER=
HTTP_PROXY=http://127.0.0.1:9
HTTPS_PROXY=http://127.0.0.1:9
```

在该条件下，服务器成功加载：

```text
PentamerChain
ITensors 0.9.27
ITensorMPS 0.4.1
JLD2 0.6.4
```

本地 Julia 1.11.5 也成功加载同一组锁定依赖。2026-07-29 的既有证据显示，本地与服务器测试均为 `54/54`；本轮没有重复运行相同测试。

`Pkg.status()` 探针在服务器上尝试连接 registry，并被无效代理阻断。该现象不影响按 Manifest 加载已安装依赖，但说明不能把 Pkg 操作视为离线安全操作。

## 5. 生产运行规则

1. 使用 Julia 绝对路径和 `+release`，并检查实际版本必须为 1.12.3。
2. 每个 cell 开始前核对 `Manifest.toml` SHA-256。
3. 强制设置离线变量和无效代理，不读取用户 `startup.jl`。
4. 不在服务器执行任何 Pkg 安装、解析、更新或 registry 操作。
5. 缺包或 artifact 时停止任务；在本地 Linux 兼容环境准备、生成 SHA-256、上传并验证，完成后删除临时传输文件。
6. 默认最多 16 Julia 线程，共享直连服务器一次只运行一个重任务。
7. 每个 cell 保存 Julia 版本、包环境哈希、源码哈希、日志、资源记录和输出校验和。

## 6. 当前验收状态

- [x] 本地和服务器项目文件哈希一致。
- [x] 服务器 Julia 1.12.3 绝对路径可用。
- [x] 三个生产依赖在强制断网条件下可加载。
- [x] 本地 Julia 1.11.5 可加载相同锁定依赖。
- [x] 生产运行器拒绝负 `alpha`、超过 16 线程和 Manifest 哈希漂移。
- [x] 第二轮修复版 Smoke 在服务器完成 3/3，并回传本地校验。
- [ ] 第三至五轮结果完成后补充最终跨版本数值差异。

本次没有下载或上传 Julia 包，因此没有需要删除的本地包传输残留。
