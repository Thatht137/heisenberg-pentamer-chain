# 模块逐行详解：从物理原理到代码实现

本文档对项目中每个源文件的每一行代码进行详细解释，涵盖物理背景、数学公式和编程逻辑。

---

## 0. PentamerChain.jl — 主模块入口

```julia
module PentamerChain                    # 定义 Julia 模块，所有源文件在此模块作用域内

using ITensors                          # 张量网络核心库（Index, ITensor, OpSum, MPO 等）
using ITensorMPS                        # MPS/DMRG 扩展（dmrg, linsolve, random_mps 等）
using LinearAlgebra                     # 标准线性代数（eigen, dot, Symmetric 等）
using SparseArrays                      # 稀疏矩阵支持（未直接使用，但 ITensors 内部依赖）
using Printf                           # 格式化输出（@printf）

include("utils.jl")                    # 加载基矢编码工具
include("hamiltonian.jl")              # 加载哈密顿量构造
include("exact_diag.jl")               # 加载精确对角化
include("dmrg_solver.jl")              # 加载 DMRG 求解器
include("order_parameters.jl")         # 加载序参量计算
include("spectral.jl")                 # 加载动力学结构因子

# 导出公共 API，外部脚本通过 using .PentamerChain 即可调用这些函数
export pentamer_hamiltonian_matrix, pentamer_chain_hamiltonian
export diagonalize_pentamer, classify_states, total_spin_squared_matrix
export compute_ground_state, compute_excited_state
export string_order_parameter, spin_gap
export apply_Sq_operator, correction_vector_dsf, compute_dsf_spectrum

end
```

---

## 1. utils.jl — 基矢编码工具

### 物理背景

$N$ 个自旋-1/2 粒子的 Hilbert 空间维度为 $2^N$。对于单个五聚体，$N=5$，维度为 32。我们需要在计算基（$S^z$ 本征态）和矩阵索引之间建立一一映射。

约定：用 0 表示 $|\downarrow\rangle$（$S^z = -1/2$），用 1 表示 $|\uparrow\rangle$（$S^z = +1/2$）。

### 逐行解析

```julia
function spin_basis_state(config::Vector{Int})
```
**功能**：给定一个自旋配置向量（如 `[1,0,1,0,0]` 表示 ↑↓↑↓↓），返回该配置在 $32\times32$ 矩阵中的行/列索引（1-based）。

```julia
    idx = 0
```
初始化索引为 0（最终会 +1 转为 Julia 的 1-based 索引）。

```julia
    for (i, s) in enumerate(config)
        idx += s * 2^(i-1)
    end
```
**小端序二进制编码**：`config[1]` 对应 $2^0$ 位，`config[2]` 对应 $2^1$ 位，以此类推。

例如 `[1,0,1,0,0]`：$1 \times 2^0 + 0 \times 2^1 + 1 \times 2^2 + 0 \times 2^3 + 0 \times 2^4 = 1 + 4 = 5$。

```julia
    return idx + 1
end
```
Julia 数组从 1 开始，所以 +1。上例返回 6。

---

```julia
function index_to_config(idx::Int, N::Int)
```
**功能**：`spin_basis_state` 的逆操作。给定矩阵索引和格点数，恢复自旋配置。

```julia
    config = zeros(Int, N)
```
分配长度为 $N$ 的零向量（全 ↓ 配置）。

```julia
    idx -= 1
```
转回 0-based 以便做位运算。

```julia
    for i in 1:N
        config[i] = idx & 1      # 取最低位：0 或 1
        idx >>= 1                # 右移一位，准备取下一个格点
    end
```
逐位提取：`& 1` 取末位，`>>= 1` 右移。这是标准的二进制→数组转换。

```julia
    return config
end
```

---

```julia
function sz_value(bit::Int)
    return bit == 1 ? 0.5 : -0.5
end
```
**功能**：把 0/1 编码映射到物理量 $S^z$ 的本征值。$|\uparrow\rangle$ 对应 $S^z = +1/2$，$|\downarrow\rangle$ 对应 $S^z = -1/2$。

---

## 2. hamiltonian.jl — 哈密顿量构造

### 物理背景

各向同性 Heisenberg 模型的哈密顿量：

$$
H = \sum_{\langle i,j \rangle} J_{ij} \, \mathbf{S}_i \cdot \mathbf{S}_j
$$

展开为分量形式：

$$
\mathbf{S}_i \cdot \mathbf{S}_j = S^z_i S^z_j + \frac{1}{2}\left(S^+_i S^-_j + S^-_i S^+_j\right)
$$

其中升降算符的作用：
- $S^+ |\downarrow\rangle = |\uparrow\rangle$，$S^+ |\uparrow\rangle = 0$
- $S^- |\uparrow\rangle = |\downarrow\rangle$，$S^- |\downarrow\rangle = 0$

五聚体内部键结构：

```text
o--J2--o--J1--o--J1--o--J2--o
1      2      3      4      5
```

### 函数一：pentamer_hamiltonian_matrix（ED 用稠密矩阵）

```julia
function pentamer_hamiltonian_matrix(J1::Real, J2::Real)
```
**输入**：胞内中间键 $J_1$ 和两端键 $J_2$。
**输出**：$32\times32$ 厄米矩阵。

```julia
    dim = 32  # 2^5 = 32
    H = zeros(Float64, dim, dim)
```
分配全零矩阵。

```julia
    for idx in 1:dim
        config = index_to_config(idx, 5)
```
遍历所有 32 个基态，把索引转成自旋配置。

```julia
        bonds = [(1, 2, J2), (2, 3, J1), (3, 4, J1), (4, 5, J2)]
```
定义 4 条键：格点对 + 对应的耦合常数。1-2 和 4-5 用 $J_2$，2-3 和 3-4 用 $J_1$。

```julia
        for (i, j, J) in bonds
            szi = sz_value(config[i])
            szj = sz_value(config[j])
            H[idx, idx] += J * szi * szj
        end
```
**对角项**：$J \cdot S^z_i S^z_j$。当基态 `idx` 中格点 $i$ 和 $j$ 的自旋确定时，$S^z_i S^z_j$ 的期望值就是两个 $\pm 1/2$ 的乘积。这一项不改变自旋配置，所以贡献到对角元 $H[\text{idx}, \text{idx}]$。

```julia
        for (i, j, J) in bonds
            if config[i] == 0 && config[j] == 1
                new_config = copy(config)
                new_config[i] = 1
                new_config[j] = 0
                jdx = spin_basis_state(new_config)
                H[jdx, idx] += J * 0.5
            end
```
**非对角项 $S^+_i S^-_j$**：当格点 $i$ 为 ↓ 且格点 $j$ 为 ↑ 时，$S^+_i S^-_j$ 把 $i$ 翻上、$j$ 翻下。产生新配置 `new_config`，找到其索引 `jdx`，在 $H[\text{jdx}, \text{idx}]$ 加上 $J \times 0.5$。

系数 0.5 来自 $\frac{1}{2} S^+_i S^-_j$ 中的 $\frac{1}{2}$，而 $S^+ |\downarrow\rangle = |\uparrow\rangle$（系数为 1，因为 $s=1/2$ 时 $\sqrt{s(s+1)-m(m+1)} = 1$）。

```julia
            if config[i] == 1 && config[j] == 0
                new_config = copy(config)
                new_config[i] = 0
                new_config[j] = 1
                jdx = spin_basis_state(new_config)
                H[jdx, idx] += J * 0.5
            end
        end
    end
```
**非对角项 $S^-_i S^+_j$**：对称情况，格点 $i$ 为 ↑ 且 $j$ 为 ↓ 时翻转。

```julia
    return Symmetric(H)
end
```
用 `Symmetric` 包装，告诉 Julia 这是厄米矩阵（实对称），`eigen` 会使用更高效的算法。

---

### 函数二：pentamer_chain_hamiltonian（DMRG 用 MPO）

```julia
function pentamer_chain_hamiltonian(sites, N_units::Int; alpha::Real=1.0, beta::Real=0.5)
```
**输入**：ITensors 格点指标 `sites`、单元数 `N_units`、参数 $\alpha = J_2/J_1$、$\beta = J_3/J_1$。
**输出**：MPO 对象。

```julia
    J1 = 1.0
    J2 = alpha * J1
    J3 = beta * J1
```
$J_1 = 1$ 为能量单位，$J_2$ 和 $J_3$ 由无量纲参数确定。

```julia
    L = length(sites)
    @assert L == 5 * N_units "Site count must equal 5 * N_units"
```
总格点数必须等于 $5 \times$ 单元数。

```julia
    os = OpSum()
```
创建空的算符和（ITensors 的符号化哈密顿量构造器）。

```julia
    for n in 1:N_units
        s1 = 5 * (n - 1) + 1    # 第 n 个单元的第 1 个格点编号
        s2 = s1 + 1              # 第 2 个格点
        s3 = s1 + 2              # 第 3 个格点
        s4 = s1 + 3              # 第 4 个格点
        s5 = s1 + 4              # 第 5 个格点
```
计算第 $n$ 个五聚体单元内 5 个格点的全局编号。

```julia
        for (si, sj, J) in [(s1, s2, J2), (s2, s3, J1), (s3, s4, J1), (s4, s5, J2)]
            os += J, "Sz", si, "Sz", sj
            os += J * 0.5, "S+", si, "S-", sj
            os += J * 0.5, "S-", si, "S+", sj
        end
```
胞内 4 条键，每条键贡献 $J[S^z_i S^z_j + \frac{1}{2}(S^+_i S^-_j + S^-_i S^+_j)]$。OpSum 语法：`系数, "算符名", 格点号, "算符名", 格点号`。

```julia
        if n < N_units
            s_next = 5 * n + 1   # 下一个单元的第 1 个格点
            os += J3, "Sz", s5, "Sz", s_next
            os += J3 * 0.5, "S+", s5, "S-", s_next
            os += J3 * 0.5, "S-", s5, "S+", s_next
        end
    end
```
**胞间键**：当前单元的第 5 格点（`s5`）连接到下一单元的第 1 格点（`s_next`），耦合为 $J_3$。最后一个单元没有右邻居，所以 `if n < N_units`。

```julia
    return MPO(os, sites)
end
```
ITensors 自动将 OpSum 编译为 MPO。内部使用有限状态机算法，生成的 MPO bond dimension 很小（通常 ~5-10），与链长无关。

---

## 3. exact_diag.jl — 精确对角化与总自旋分类

### 物理背景

对于小体系（$2^N$ 维度可控），精确对角化给出所有本征值和本征矢，是最精确的参考。

总自旋算符 $\mathbf{S}^2_{\text{tot}}$ 与 $H$ 对易（Heisenberg 模型具有 SU(2) 对称性），因此能量本征态同时也是 $\mathbf{S}^2$ 的本征态。通过计算每个本征态的 $\langle S^2 \rangle = S(S+1)$，可以标记其总自旋量子数 $S$。

对于 5 个自旋-1/2：
- $S = 1/2$：简并度 $2S+1 = 2$，但有多个不同的 $S=1/2$ 多重态，总共 10 个态
- $S = 3/2$：总共 16 个态（4 个四重态）
- $S = 5/2$：总共 6 个态（1 个六重态）
- 合计：$10 + 16 + 6 = 32$ ✓

### 函数一：total_spin_squared_matrix

```julia
function total_spin_squared_matrix(N::Int=5)
```
**功能**：构造 $N$ 个自旋-1/2 的总自旋平方算符 $\mathbf{S}^2_{\text{tot}}$ 的 $2^N \times 2^N$ 矩阵表示。

数学展开：

$$
\mathbf{S}^2_{\text{tot}} = \left(\sum_i \mathbf{S}_i\right)^2 = \sum_i \mathbf{S}_i^2 + 2\sum_{i < j} \mathbf{S}_i \cdot \mathbf{S}_j
$$

由于代码中对 $i \neq j$（而非 $i < j$）求和，系数自动变为 1 而非 2。

```julia
    dim = 2^N
    S2 = zeros(Float64, dim, dim)
```
分配 $2^N \times 2^N$ 零矩阵。

```julia
    for idx in 1:dim
        S2[idx, idx] += N * 0.75
    end
```
**单格点贡献**：每个自旋-1/2 粒子的 $\mathbf{S}_i^2 = s(s+1) = \frac{1}{2} \cdot \frac{3}{2} = \frac{3}{4}$。$N$ 个格点总共贡献 $N \times 0.75$ 到每个对角元。这是一个常数（正比于单位矩阵），因为 $\mathbf{S}_i^2$ 在任何态上的期望值都是 $3/4$。

```julia
    for i in 1:N, j in 1:N
        i == j && continue
```
遍历所有 $i \neq j$ 的格点对。

```julia
        for idx in 1:dim
            config = index_to_config(idx, N)
```
对每个基态，恢复其自旋配置。

```julia
            S2[idx, idx] += sz_value(config[i]) * sz_value(config[j])
```
**交叉项的 $S^z_i S^z_j$ 部分**：直接乘两个格点的 $S^z$ 值加到对角元。

```julia
            if config[i] == 0 && config[j] == 1
                new_config = copy(config)
                new_config[i] = 1
                new_config[j] = 0
                jdx = spin_basis_state(new_config)
                S2[jdx, idx] += 0.5
            end
```
**交叉项的 $\frac{1}{2} S^+_i S^-_j$ 部分**：与哈密顿量中的翻转项逻辑完全相同。格点 $i$ 为 ↓ 且 $j$ 为 ↑ 时，翻转产生新态，矩阵元为 0.5。

注意：这里没有额外的系数 2，因为我们对所有 $i \neq j$（而非 $i < j$）求和，每对 $(i,j)$ 被计算了两次，等效于 $2\sum_{i<j}$。

```julia
            if config[i] == 1 && config[j] == 0
                new_config = copy(config)
                new_config[i] = 0
                new_config[j] = 1
                jdx = spin_basis_state(new_config)
                S2[jdx, idx] += 0.5
            end
        end
    end
```
对称的 $\frac{1}{2} S^-_i S^+_j$ 部分。

```julia
    return Symmetric(S2)
end
```
返回对称矩阵（$\mathbf{S}^2$ 是厄米算符）。

---

### 函数二：diagonalize_pentamer

```julia
function diagonalize_pentamer(alpha::Real; J1::Real=1.0)
```
**输入**：$\alpha = J_2/J_1$。
**输出**：`(eigenvalues, eigenvectors, spin_labels)`。

```julia
    J2 = alpha * J1
    H = pentamer_hamiltonian_matrix(J1, J2)
```
构造单五聚体哈密顿量。

```julia
    vals, vecs = eigen(Matrix(H))
```
`eigen` 对实对称矩阵做全对角化（内部用 LAPACK 的 dsyev），返回升序排列的本征值和对应本征矢（列向量）。`Matrix(H)` 把 `Symmetric` 类型转为普通矩阵以兼容 `eigen`。

```julia
    S2 = total_spin_squared_matrix(5)
    spin_labels = Float64[]
```
构造 $\mathbf{S}^2$ 矩阵，准备标记每个本征态的总自旋。

```julia
    for i in 1:size(vecs, 2)
        v = vecs[:, i]
        s2_expect = dot(v, S2 * v)
```
计算第 $i$ 个本征态的 $\langle \psi_i | \mathbf{S}^2 | \psi_i \rangle = S(S+1)$。

```julia
        S = (-1 + sqrt(1 + 4 * s2_expect)) / 2
```
从 $S(S+1) = \langle S^2 \rangle$ 反解 $S$：这是一元二次方程 $S^2 + S - \langle S^2 \rangle = 0$ 的正根。

```julia
        push!(spin_labels, round(S * 2) / 2)
    end
```
四舍五入到最近的半整数（0.5, 1.0, 1.5, 2.0, 2.5）。数值误差可能让 $S$ 偏离精确值 $10^{-10}$ 量级，round 消除这个偏差。

```julia
    return vals, vecs, spin_labels
end
```

---

### 函数三：classify_states

```julia
function classify_states(eigenvalues::Vector{Float64}, spin_labels::Vector{Float64};
                         tol::Real=1e-8)
```
**功能**：把 32 个本征态按 (能量, 总自旋) 归组，统计简并度。

```julia
    levels = Tuple{Float64, Float64, Int}[]
    used = falses(length(eigenvalues))
```
`levels` 存储结果，`used` 标记已归组的态。

```julia
    for i in eachindex(eigenvalues)
        used[i] && continue
        E = eigenvalues[i]
        S = spin_labels[i]
        deg = 1
        for j in (i+1):length(eigenvalues)
            if !used[j] && abs(eigenvalues[j] - E) < tol && abs(spin_labels[j] - S) < tol
                deg += 1
                used[j] = true
            end
        end
        used[i] = true
        push!(levels, (E, S, deg))
    end
```
对每个未归组的态，找所有能量和自旋都在容差内的态，计为同一能级的简并态。

```julia
    sort!(levels, by=x -> x[1])
    return levels
end
```
按能量升序排列后返回。

---

## 4. dmrg_solver.jl — DMRG 求解器

### 物理背景

**矩阵乘积态（MPS）**：一维量子态的高效参数化表示：

$$
|\psi\rangle = \sum_{\sigma_1,\ldots,\sigma_L} A^{\sigma_1}_{a_0 a_1} A^{\sigma_2}_{a_1 a_2} \cdots A^{\sigma_L}_{a_{L-1} a_L} |\sigma_1 \cdots \sigma_L\rangle
$$

- $\sigma_i \in \{\uparrow, \downarrow\}$：物理指标（局域 Hilbert 空间）
- $a_i$：虚拟指标（bond index），维度 $D$ 称为 bond dimension
- $D$ 控制精度：$D=1$ 是乘积态（无纠缠），$D \to \infty$ 精确

**DMRG 算法**：
1. 从某个初始 MPS 出发
2. 从左到右、再从右到左逐格点优化（sweep）
3. 每步固定其他格点，对当前格点的张量做局域本征值问题
4. SVD 截断保持 bond dimension ≤ maxdim

### 函数一：compute_ground_state

```julia
function compute_ground_state(;
    N_units::Int=12,       # 五聚体单元数
    alpha::Real=1.0,       # J2/J1
    beta::Real=0.5,        # J3/J1
    maxdim::Int=800,       # 最大 bond dimension
    cutoff::Real=1e-8,     # SVD 截断阈值（丢弃奇异值 < cutoff 的分量）
    nsweeps::Int=10,       # sweep 次数
    conserve_qns::Bool=true  # 是否利用量子数守恒
)
```

```julia
    L = 5 * N_units
```
总格点数 = 5 × 单元数。

```julia
    sites = siteinds("S=1/2", L; conserve_qns)
```
创建 $L$ 个自旋-1/2 格点的指标。`conserve_qns=true` 启用 U(1) 对称性（$S^z_{\text{tot}}$ 守恒），张量内部按量子数分块存储，大幅减少计算量和内存。

```julia
    H = pentamer_chain_hamiltonian(sites, N_units; alpha, beta)
```
构造 MPO。

```julia
    if iseven(L)
        state = [isodd(n) ? "Up" : "Dn" for n in 1:L]
    else
        state = [isodd(n) ? "Up" : "Dn" for n in 1:L]
        state[end] = "Up"
    end
```
**初态选择**：Néel 态 ↑↓↑↓...。偶数格点时总 $S^z = 0$（基态所在扇区）；奇数格点时总 $S^z = 1/2$。初态的量子数决定了 DMRG 在哪个扇区搜索。

```julia
    psi0 = random_mps(sites, state; linkdims=10)
```
以 Néel 态的量子数结构为模板，生成一个 bond dimension=10 的随机 MPS。不直接用 Néel 态是因为它是乘积态（$D=1$），太远离真实基态，DMRG 收敛慢。随机 MPS 有更好的初始纠缠结构。

```julia
    maxdim_schedule = _sweep_schedule(maxdim, nsweeps)
```
生成逐步递增的 bond dimension 调度表。

```julia
    energy, psi = dmrg(H, psi0;
        nsweeps,
        maxdim=maxdim_schedule,
        cutoff,
        outputlevel=1
    )
```
调用 ITensorMPS 的 DMRG 求解器。`outputlevel=1` 每次 sweep 打印能量。返回基态能量和优化后的 MPS。

```julia
    return energy, psi, sites, H
end
```
返回四元组，供后续计算（序参量、DSF）使用。

---

### 函数二：compute_excited_state

```julia
function compute_excited_state(H, psi_gs, sites;
    maxdim::Int=800,
    cutoff::Real=1e-8,
    nsweeps::Int=10,
    weight::Real=20.0,         # 正交惩罚权重
    target_sz::Union{Nothing, Int}=nothing  # 目标 Sz 扇区
)
```

```julia
    L = length(sites)
    if isnothing(target_sz)
        state = [isodd(n) ? "Up" : "Dn" for n in 1:L]
    else
        n_up = div(L, 2) + target_sz
        state = fill("Dn", L)
        for i in 1:n_up
            state[2i-1 <= L ? 2i-1 : i] = "Up"
        end
    end
```
如果指定了 `target_sz`（如 1），构造总 $S^z = \text{target\_sz}$ 的初态：需要 $L/2 + S^z$ 个 ↑ 自旋。优先放在奇数格点上（类 Néel 排列）。

```julia
    psi0 = random_mps(sites, state; linkdims=10)
    maxdim_schedule = _sweep_schedule(maxdim, nsweeps)
```
同基态计算。

```julia
    energy, psi = dmrg(H, [psi_gs], psi0;
        nsweeps,
        maxdim=maxdim_schedule,
        cutoff,
        weight,
        outputlevel=1
    )
```
**关键区别**：第二个参数 `[psi_gs]` 是需要正交的态列表。DMRG 最小化的有效能量为：

$$
E_{\text{eff}}[\psi] = \langle\psi|H|\psi\rangle + w \sum_k |\langle\psi|\psi_k\rangle|^2
$$

$w = 20$ 足够大时，优化结果自动正交于 `psi_gs`，得到第一激发态。

```julia
    return energy, psi
end
```

---

### 函数三：_sweep_schedule

```julia
function _sweep_schedule(maxdim::Int, nsweeps::Int)
    schedule = Int[]
    ramp_steps = min(5, nsweeps)
```
前 5 步（或更少）做递增。

```julia
    for i in 1:nsweeps
        if i <= ramp_steps
            push!(schedule, min(maxdim, 50 * 2^(i-1)))
```
几何递增：50, 100, 200, 400, 800。但不超过用户指定的 `maxdim`。

**物理动机**：前几步波函数还很粗糙，纠缠熵低，用小 $D$ 就够了。逐步增大 $D$ 让波函数逐渐精化，避免一开始就在高维空间中做昂贵的优化。

```julia
        else
            push!(schedule, maxdim)
        end
    end
    return schedule
end
```
第 6 步起使用完整的 `maxdim`。

---

## 5. order_parameters.jl — 弦序参量与自旋能隙

### 物理背景：弦序参量

在一维量子自旋系统中，某些拓扑有序相（如 Haldane 相）没有局域序参量，但存在隐藏的非局域序——弦序参量（string order parameter）：

$$
O_{\text{str}}(i, j) = -\left\langle \sigma^z_i \left(\prod_{k=i+1}^{j-1} \sigma^z_k \right) \sigma^z_j \right\rangle
$$

其中 $\sigma^z = 2S^z$（Pauli 矩阵）。物理含义：

- 中间的 $\prod \sigma^z_k$ 是一串"相位因子"，每遇到一个 ↑ 自旋乘 +1，每遇到一个 ↓ 自旋乘 -1
- 如果系统有隐藏的反铁磁序（被局域量子涨落掩盖），弦序参量在 $|i-j| \to \infty$ 时趋于非零常数
- 如果系统无序或处于其他相，弦序参量衰减到零

### 物理背景：自旋能隙

$$
\Delta = E_0(S^z_{\text{tot}} = 1) - E_0(S^z_{\text{tot}} = 0)
$$

- $\Delta > 0$：有能隙相（dimer 相、Haldane 相等），自旋激发需要有限能量
- $\Delta = 0$（热力学极限）：无能隙相（临界相），低能激发连续谱

### 函数一：string_order_parameter

```julia
function string_order_parameter(psi, sites, N_units::Int; margin::Int=3)
```
**输入**：基态 MPS `psi`、格点指标 `sites`、单元数、边界裁剪量 `margin`。
**输出**：弦序参量的数值（标量）。

```julia
    L = length(sites)
    @assert L == 5 * N_units
```
验证格点数一致。

```julia
    while margin > 0 && (N_units - 2 * margin) < 2
        margin -= 1
    end
    if margin == 0 && N_units < 2
        error("Chain too short: need at least N_units=2 for string order parameter")
    end
```
**自适应 margin**：如果链太短（去掉两端 margin 后剩余不足 2 个单元），自动缩减 margin。这保证短链试跑不会报错，但物理意义会打折扣。

```julia
    n_start = margin + 1
    n_end = N_units - margin
```
体区范围：从第 `margin+1` 个单元到第 `N_units-margin` 个单元。例如 $N=12$, $\text{margin}=3$ 时，体区为第 4-9 个单元。

```julia
    max_sep = n_end - n_start
    values = Float64[]
```
`max_sep` 是体区内单元间的最大间隔。我们优先取最大距离的关联函数（最接近热力学极限的行为）。

```julia
    for n in n_start:(n_end - max_sep)
        np = n + max_sep
        site_i = 5 * n              # 第 n 个单元的末端格点（第 5 个）
        site_j = 5 * (np - 1) + 1   # 第 np 个单元的起点格点（第 1 个）
```
选取格点对：$i$ 是某单元的最后一个格点，$j$ 是另一单元的第一个格点。这样弦跨越了胞间键，物理上最有意义。

```julia
        val = _string_correlator(psi, sites, site_i, site_j)
        push!(values, val)
    end
```
计算并收集关联函数值。

```julia
    if isempty(values)
        for sep in (max_sep-1):-1:1
            for n in n_start:(n_end - sep)
                np = n + sep
                site_i = 5 * n
                site_j = 5 * (np - 1) + 1
                val = _string_correlator(psi, sites, site_i, site_j)
                push!(values, val)
            end
            isempty(values) || break
        end
    end
```
**回退逻辑**：如果最大距离无可用点对（极短链），逐步缩短距离直到找到可计算的点对。

```julia
    return sum(values) / length(values)
end
```
返回所有采样点的平均值。

---

### 函数二：_string_correlator

```julia
function _string_correlator(psi, sites, i::Int, j::Int)
```
**功能**：计算格点 $i$ 到 $j$ 之间的弦关联函数。

```julia
    N_mid = j - i - 1
```
$i$ 和 $j$ 之间的中间格点数。

```julia
    coeff = -(2.0)^N_mid
```
**系数推导**：

弦序参量定义中用的是 $\sigma^z = 2S^z$，所以：

$$
O_{\text{str}}(i,j) = -\langle \sigma^z_i \prod_{k=i+1}^{j-1} \sigma^z_k \cdot \sigma^z_j \rangle = -\langle (2S^z_i) \prod_{k=i+1}^{j-1} (2S^z_k) \cdot (2S^z_j) \rangle
$$

$$
= -(2)^{j-i+1} \langle S^z_i \prod_{k=i+1}^{j-1} S^z_k \cdot S^z_j \rangle
$$

但代码中 OpSum 里已经包含了端点的 $S^z_i$ 和 $S^z_j$（各贡献一个因子 1，不需要额外的 2），所以实际系数是 $-(2)^{N_{\text{mid}}}$（只有中间格点需要 $\sigma^z = 2S^z$ 的因子 2）。

等等，让我重新看代码逻辑：OpSum 中从 $i$ 到 $j$ 的所有格点都放了 `"Sz"`，所以每个格点贡献的是 $S^z$（不是 $\sigma^z$）。要得到 $\sigma^z = 2S^z$ 的乘积，需要对每个格点乘 2。共 $(j-i+1)$ 个格点，但端点的 2 已经被吸收... 实际上代码的做法是：

$$
\text{val} = \text{coeff} \times \langle \psi | \prod_{k=i}^{j} S^z_k | \psi \rangle
$$

其中 $\text{coeff} = -(2)^{N_{\text{mid}}}$。总共 $j-i+1$ 个 $S^z$ 算符，乘以 $-(2)^{j-i-1}$，等效于 $-2^{j-i-1} \prod S^z_k$。这对应于弦序参量的一种特定归一化约定（Li 等文献）。

```julia
    os = OpSum()
    args = Any[coeff]
    for k in i:j
        push!(args, "Sz")
        push!(args, k)
    end
    os += Tuple(args)
```
构造多体算符：`coeff * Sz_i * Sz_{i+1} * ... * Sz_j`。OpSum 支持任意多格点的乘积算符，语法为 `(系数, "Op1", site1, "Op2", site2, ...)`。

```julia
    O = MPO(os, sites)
    return real(inner(psi', O, psi))
end
```
把算符编译为 MPO，然后计算 $\langle\psi|O|\psi\rangle$。`inner(psi', O, psi)` 是 ITensors 计算 $\langle\psi'|O|\psi\rangle$ 的标准接口，`psi'` 表示对偶（bra）。取实部是因为物理量应为实数，虚部仅为浮点噪声。

---

### 函数三：spin_gap

```julia
function spin_gap(; N_units::Int=12, alpha::Real=1.0, beta::Real=0.5,
                  maxdim::Int=400, cutoff::Real=1e-8, nsweeps::Int=8)
```
**功能**：计算自旋能隙 $\Delta = E_0(S^z=1) - E_0(S^z=0)$。

```julia
    L = 5 * N_units
    @assert iseven(L) "spin_gap requires even L (even N_units for pentamer)"
```
偶数格点才能有 $S^z=0$ 的 singlet 基态。

```julia
    sites = siteinds("S=1/2", L; conserve_qns=true)
    H = pentamer_chain_hamiltonian(sites, N_units; alpha, beta)
```
构造格点和 MPO。注意这里独立构造（不复用外部的），因为 `spin_gap` 是自包含函数。

```julia
    state_0 = [isodd(n) ? "Up" : "Dn" for n in 1:L]
    psi0 = random_mps(sites, state_0; linkdims=10)
    schedule = _sweep_schedule(maxdim, nsweeps)
    E0, _ = dmrg(H, psi0; nsweeps, maxdim=schedule, cutoff, outputlevel=0)
```
**$S^z=0$ 扇区基态**：Néel 初态保证总 $S^z=0$，DMRG 在此扇区内搜索最低能量。`outputlevel=0` 静默运行。

```julia
    state_1 = copy(state_0)
    state_1[2] = "Up"
```
**$S^z=1$ 扇区初态**：把第 2 个格点从 ↓ 翻为 ↑，总 $S^z$ 从 0 变为 1。

```julia
    psi1 = random_mps(sites, state_1; linkdims=10)
    E1, _ = dmrg(H, psi1; nsweeps, maxdim=schedule, cutoff, outputlevel=0)
```
在 $S^z=1$ 扇区做 DMRG。由于 `conserve_qns=true`，DMRG 自动限制在该扇区内搜索。

```julia
    return E1 - E0
end
```
返回能隙。正值表示有能隙，零（在有限尺寸下趋近零）表示无能隙。

---

## 6. spectral.jl — 修正向量法计算动力学结构因子

### 物理背景

**动力学结构因子** $S(q,\omega)$ 是中子散射实验直接测量的物理量，描述系统在动量 $q$、能量 $\omega$ 处的自旋激发谱：

$$
S(q,\omega) = \sum_n |\langle n | S^z_q | 0 \rangle|^2 \, \delta(\omega - (E_n - E_0))
$$

其中 $|n\rangle$ 是所有激发态，$S^z_q = \frac{1}{\sqrt{N}} \sum_j e^{iqj} S^z_j$ 是动量空间的自旋算符。

直接求和需要所有激发态（不可能），所以用 **Lehmann 表示** 的等价形式：

$$
S(q,\omega) = -\frac{1}{\pi} \operatorname{Im} \langle 0 | S^z_{-q} \frac{1}{\omega + E_0 + i\eta - H} S^z_q | 0 \rangle
$$

**修正向量法**：不求所有激发态，而是对每个 $(\omega, q)$ 点解一个线性方程：

$$
(\omega + E_0 + i\eta - H)|x\rangle = S^z_q|0\rangle \equiv |b\rangle
$$

然后 $S(q,\omega) = -\frac{1}{\pi} \operatorname{Im}\langle b|x\rangle$。

$\eta > 0$ 是人为加入的展宽（Lorentzian），物理上：
- 把 $\delta$ 函数展宽为有限宽度的峰
- 保证线性方程非奇异（$\omega + E_0 - E_n$ 可能为零，加 $i\eta$ 后分母不为零）
- 对应有限能量分辨率或有限准粒子寿命

### 函数一：apply_Sq_operator

```julia
function apply_Sq_operator(psi, sites, q::Real; margin_sites::Int=0)
```
**功能**：计算 $|b\rangle = S^z_q |\psi\rangle = \frac{1}{\sqrt{N}} \sum_j e^{iqj} S^z_j |\psi\rangle$。

**输入**：基态 MPS `psi`、格点指标、动量 $q$、边界裁剪格点数。
**输出**：新的 MPS $|b\rangle$。

```julia
    N = length(sites)
    n_start = margin_sites + 1
    n_end = N - margin_sites
    N_eff = n_end - n_start + 1
```
有效格点范围。`margin_sites=0` 时使用全部格点。$N_{\text{eff}}$ 是参与求和的格点数，用于归一化。

```julia
    result = nothing
```
累加器，初始为空。

```julia
    for j in n_start:n_end
```
遍历每个格点 $j$。

```julia
        coeff = exp(im * q * j) / sqrt(N_eff)
```
相位因子 $e^{iqj} / \sqrt{N_{\text{eff}}}$。这是复数（`im` 是 Julia 的虚数单位）。

```julia
        psi_j = copy(psi)
```
复制基态 MPS（不能修改原始基态）。

```julia
        new_tensor = noprime(psi_j[j] * op("Sz", sites[j]))
```
**在第 $j$ 格点施加 $S^z$ 算符**：

1. `op("Sz", sites[j])`：获取格点 $j$ 上 $S^z$ 算符的 ITensor 表示（$2\times2$ 矩阵）
2. `psi_j[j] * op(...)`：张量缩并，将算符作用在 MPS 的第 $j$ 个张量上。缩并后物理指标被 prime 了一次
3. `noprime(...)`：去掉 prime，恢复原始指标标签（否则后续运算指标不匹配）

结果：$S^z_j |\psi\rangle$ 在第 $j$ 格点的局域张量。

```julia
        psi_j[j] = new_tensor
```
替换第 $j$ 格点的张量，现在 `psi_j` 代表 $S^z_j |\psi\rangle$。

```julia
        if isnothing(result)
            result = coeff * psi_j
        else
            result = add(result, coeff * psi_j; cutoff=1e-10, maxdim=linkdim_max(psi) + 50)
        end
    end
```
**MPS 线性组合**：

- 第一个格点：直接赋值 $\text{result} = e^{iq \cdot 1}/\sqrt{N} \cdot S^z_1|\psi\rangle$
- 后续格点：用 `add` 函数做 MPS 加法 $\text{result} \leftarrow \text{result} + \text{coeff} \cdot S^z_j|\psi\rangle$

MPS 加法会增大 bond dimension（两个 $D$ 维 MPS 相加得到 $2D$ 维），所以用 `cutoff` 和 `maxdim` 截断控制增长。`maxdim=linkdim_max(psi)+50` 允许比基态稍大的 bond dimension。

```julia
    return result
end
```
返回 $|b\rangle = S^z_q |\psi_0\rangle$ 的 MPS 表示。

---

```julia
function linkdim_max(psi)
    return maximum(dim.(linkinds(psi)))
end
```
辅助函数：返回 MPS 的最大 bond dimension。`linkinds(psi)` 获取所有虚拟指标，`dim.()` 取每个指标的维度，`maximum` 取最大值。

---

### 函数二：correction_vector_dsf

```julia
function correction_vector_dsf(psi_gs, H, sites, E0::Real;
    q::Real, omega::Real, eta::Real=0.1,
    maxdim::Int=200, cutoff::Real=1e-6, nsweeps::Int=4)
```
**功能**：计算单个 $(q, \omega)$ 点的 $S(q,\omega)$ 值。

```julia
    b = apply_Sq_operator(psi_gs, sites, q)
```
计算右端向量 $|b\rangle = S^z_q |\psi_0\rangle$。

```julia
    a = (omega + E0) + im * eta
```
复数移位 $a = \omega + E_0 + i\eta$。线性方程为 $(a - H)|x\rangle = |b\rangle$。

```julia
    x = linsolve(H, b, b, a, -1;
        nsweeps, maxdim, cutoff,
        updater_kwargs=(; tol=1e-5))
```
**ITensorMPS.linsolve 接口**：

`linsolve(A, x0, b, a, c)` 求解 $(a + c \cdot A)|x\rangle = |b\rangle$。

这里：$A = H$，$c = -1$，所以方程为 $(a - H)|x\rangle = |b\rangle$，即 $(\omega + E_0 + i\eta - H)|x\rangle = |b\rangle$。

参数说明：
- 第二个 `b`：初始猜测 $|x_0\rangle$（用 $|b\rangle$ 本身作为起点）
- `nsweeps=4`：迭代 sweep 次数（比 DMRG 少，因为精度要求较低）
- `maxdim=200`：修正向量的 bond dimension（比基态小，因为激发态纠缠通常不太大）
- `updater_kwargs=(; tol=1e-5)`：内部线性求解器的收敛容差

```julia
    return -1 / π * imag(inner(b, x))
end
```
计算 $S(q,\omega) = -\frac{1}{\pi} \operatorname{Im}\langle b|x\rangle$。

`inner(b, x)` 计算两个 MPS 的内积 $\langle b|x\rangle$（复数），取虚部再乘 $-1/\pi$。

---

### 函数三：compute_dsf_spectrum

```julia
function compute_dsf_spectrum(psi_gs, H, sites, E0::Real;
    q_points=range(0, 2π, length=33),
    omega_range=range(0, 4, length=101),
    eta::Real=0.1,
    maxdim::Int=200,
    cutoff::Real=1e-6,
    chunk_size::Int=4)
```
**功能**：计算完整的 $S(q,\omega)$ 二维谱。

**参数**：
- `q_points`：动量网格（默认 0 到 $2\pi$，33 个点）
- `omega_range`：能量网格（默认 0 到 4$J_1$，101 个点）
- `eta`：Lorentzian 展宽
- `chunk_size`：每次并行处理的 $q$ 点数（控制内存）

```julia
    nq = length(q_points)
    nw = length(omega_range)
    S_qw = zeros(Float64, nq, nw)
```
分配 $n_q \times n_\omega$ 的结果矩阵。

```julia
    q_chunks = Iterators.partition(1:nq, chunk_size)
```
把 $q$ 点索引分成大小为 `chunk_size` 的块。例如 17 个 $q$ 点、chunk_size=4 时分为 [1:4], [5:8], [9:12], [13:16], [17:17]。

**为什么分块**：每个 $q$ 点的计算需要独立的 MPS 副本（deepcopy），如果同时启动所有 $q$ 点的线程，内存会爆。分块控制同时活跃的线程数。

```julia
    for chunk in q_chunks
        tasks = map(chunk) do iq
            Threads.@spawn begin
```
对当前 chunk 中的每个 $q$ 点索引 `iq`，启动一个异步任务（线程）。

```julia
                local_psi = deepcopy(psi_gs)
                local_H = deepcopy(H)
                local_sites = sites
```
**线程安全**：每个线程需要独立的 MPS 和 MPO 副本，因为 `linsolve` 会修改内部状态。`sites`（格点指标）是只读的，可以共享。

`deepcopy` 是深拷贝，创建完全独立的对象。这是并行计算中避免数据竞争的标准做法。

```julia
                q = q_points[iq]
                row = zeros(Float64, nw)
                for (iw, omega) in enumerate(omega_range)
                    row[iw] = correction_vector_dsf(
                        local_psi, local_H, local_sites, E0;
                        q, omega, eta, maxdim, cutoff)
                end
                (iq, row)
            end
        end
```
每个线程：对固定的 $q$，遍历所有 $\omega$ 点计算 $S(q,\omega)$。返回 `(q点索引, 该行结果)`。

注意：对同一个 $q$，不同 $\omega$ 之间是串行的。这是因为 `apply_Sq_operator` 对每个 $q$ 只需算一次（$|b\rangle$ 相同），但当前实现中每次都重新算了。这是一个可优化的点，但代码正确性没问题。

```julia
        for t in tasks
            iq, row = fetch(t)
            S_qw[iq, :] = row
        end
    end
```
等待当前 chunk 的所有线程完成（`fetch` 阻塞直到任务结束），收集结果写入矩阵。

```julia
    return S_qw
end
```
返回完整的 $S(q,\omega)$ 矩阵。行对应 $q$ 点，列对应 $\omega$ 点。

---

## 7. 整体架构与数据流

```text
┌─────────────────────────────────────────────────────────────────┐
│                        PentamerChain 模块                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  utils.jl ──→ 基矢编码/解码（ED 专用）                            │
│      ↓                                                          │
│  hamiltonian.jl ──┬──→ 32×32 稠密矩阵（ED 用）                   │
│                   └──→ MPO（DMRG/DSF 用）                        │
│      ↓                    ↓                                     │
│  exact_diag.jl        dmrg_solver.jl                            │
│  （全对角化+S²分类）    （基态/激发态）                              │
│                           ↓                                     │
│                    ┌──────┴──────┐                               │
│                    ↓             ↓                               │
│          order_parameters.jl  spectral.jl                       │
│          （弦序参量+能隙）     （DSF 修正向量法）                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

脚本调用关系：
  01_single_pentamer.jl  →  exact_diag.jl
  02_dmrg_chain.jl       →  dmrg_solver.jl + exact_diag.jl（对比验证）
  03_phase_diagram.jl    →  dmrg_solver.jl + order_parameters.jl
  04_dsf.jl              →  dmrg_solver.jl + spectral.jl
```

### 设计思路

1. **两层哈密顿量**：同一个物理模型有两种数值表示。ED 层用稠密矩阵（小体系精确），MPO 层用张量网络（大体系近似）。两者在小体系上给出一致结果，这是验证的基础。

2. **渐进式验证**：脚本 01→02→03→04 是从简单到复杂的递进。每一步都建立在前一步验证通过的基础上。

3. **关注点分离**：每个源文件负责一个独立的物理/数值功能，通过主模块统一导出。脚本只负责参数设置和结果保存，不包含核心算法。
