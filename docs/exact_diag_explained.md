# 精确对角化模块详解

本文档面向初学者，详细讲解 `src/exact_diag.jl`（及其依赖的 `utils.jl` 和 `hamiltonian.jl` 中 ED 相关部分）的物理原理和代码实现。

---

## 1. 物理问题：我们在算什么？

我们有 5 个自旋 1/2 粒子排成一条线，相邻粒子之间通过 Heisenberg 交换相互作用耦合：

```
o--J2--o--J1--o--J1--o--J2--o
1      2      3      4      5
```

哈密顿量为：

$$H = J_2 \, \mathbf{S}_1 \cdot \mathbf{S}_2 + J_1 \, \mathbf{S}_2 \cdot \mathbf{S}_3 + J_1 \, \mathbf{S}_3 \cdot \mathbf{S}_4 + J_2 \, \mathbf{S}_4 \cdot \mathbf{S}_5$$

其中 $\mathbf{S}_i \cdot \mathbf{S}_j = S_i^x S_j^x + S_i^y S_j^y + S_i^z S_j^z$。

"精确对角化"的意思是：把 H 写成一个矩阵，然后用线性代数方法求出它的全部本征值（能量）和本征态。对于 5 个自旋 1/2，希尔伯特空间维度是 $2^5 = 32$，所以 H 是一个 32×32 的矩阵，完全可以精确处理。

---

## 2. 希尔伯特空间的基矢编码

### 2.1 每个自旋的状态

单个自旋 1/2 粒子有两个状态：
- 自旋向上 $|\uparrow\rangle$：$S^z = +1/2$，用 bit = 1 表示
- 自旋向下 $|\downarrow\rangle$：$S^z = -1/2$，用 bit = 0 表示

### 2.2 多粒子基矢

5 个自旋的一个基矢就是每个格点自旋取向的组合，例如 $|\downarrow\uparrow\uparrow\downarrow\uparrow\rangle$ 对应 config = [0, 1, 1, 0, 1]。

总共有 $2^5 = 32$ 个这样的基矢，它们构成希尔伯特空间的一组完备正交基。

### 2.3 编码方案（utils.jl）

代码用一个整数 idx（1 到 32）来标记每个基矢。转换规则是把 config 看作一个二进制数（小端序）：

```julia
function spin_basis_state(config::Vector{Int})
    idx = 0
    for (i, s) in enumerate(config)
        idx += s * 2^(i-1)
    end
    return idx + 1  # Julia 数组从 1 开始
end
```

例如 config = [0, 1, 1, 0, 1]：
- idx = 0×1 + 1×2 + 1×4 + 0×8 + 1×16 = 22
- 返回 22 + 1 = 23（因为 Julia 索引从 1 开始，而全 0 的 config 对应 idx=1）

等等，这里要注意：全下自旋 [0,0,0,0,0] 对应 idx = 0 + 1 = 1。

逆变换 `index_to_config` 做的是反过来的事：从整数恢复 config 数组。

`sz_value(bit)` 把 0/1 编码转换为物理的 $S^z$ 值：bit=1 → +0.5，bit=0 → −0.5。

---

## 3. 构造哈密顿量矩阵（hamiltonian.jl）

### 3.1 Heisenberg 相互作用的分解

$\mathbf{S}_i \cdot \mathbf{S}_j$ 可以改写为：

$$\mathbf{S}_i \cdot \mathbf{S}_j = S_i^z S_j^z + \frac{1}{2}(S_i^+ S_j^- + S_i^- S_j^+)$$

其中升降算符定义为 $S^\pm = S^x \pm i S^y$。这个分解的物理意义：
- $S_i^z S_j^z$ 项：不改变任何自旋的取向，只贡献对角矩阵元
- $S_i^+ S_j^-$ 项：把格点 j 的自旋从上翻到下，同时把格点 i 的自旋从下翻到上（"交换"两个自旋）
- $S_i^- S_j^+$ 项：反过来

### 3.2 升降算符的作用

对自旋 1/2：
- $S^+ |\downarrow\rangle = |\uparrow\rangle$，$S^+ |\uparrow\rangle = 0$
- $S^- |\uparrow\rangle = |\downarrow\rangle$，$S^- |\downarrow\rangle = 0$

在代码的 0/1 编码中：
- $S^+$ 把 bit=0 变成 bit=1（前提是原来是 0，否则结果为零）
- $S^-$ 把 bit=1 变成 bit=0（前提是原来是 1，否则结果为零）

### 3.3 代码逻辑

```julia
function pentamer_hamiltonian_matrix(J1::Real, J2::Real)
    dim = 32
    H = zeros(Float64, dim, dim)

    for idx in 1:dim
        config = index_to_config(idx, 5)
        bonds = [(1, 2, J2), (2, 3, J1), (3, 4, J1), (4, 5, J2)]

        # 对角项
        for (i, j, J) in bonds
            H[idx, idx] += J * sz_value(config[i]) * sz_value(config[j])
        end

        # 非对角项
        for (i, j, J) in bonds
            if config[i] == 0 && config[j] == 1   # S+_i S-_j 可以作用
                new_config = copy(config)
                new_config[i] = 1; new_config[j] = 0
                jdx = spin_basis_state(new_config)
                H[jdx, idx] += J * 0.5
            end
            if config[i] == 1 && config[j] == 0   # S-_i S+_j 可以作用
                new_config = copy(config)
                new_config[i] = 0; new_config[j] = 1
                jdx = spin_basis_state(new_config)
                H[jdx, idx] += J * 0.5
            end
        end
    end
    return Symmetric(H)
end
```

逐步解读：

1. 遍历每个基矢 idx（即矩阵的每一列）
2. 对每条键 (i, j, J)：
   - **对角项**：计算 $J \cdot S_i^z \cdot S_j^z$ 的值，加到 H[idx, idx]。这不改变基矢，所以是对角元。
   - **非对角项**：检查 $S_i^+ S_j^-$ 能否作用（需要格点 i 为下、格点 j 为上）。如果能，翻转后得到新基矢 jdx，在 H[jdx, idx] 加上 $J/2$。$S_i^- S_j^+$ 同理。

3. 最后用 `Symmetric(H)` 包装，告诉 Julia 这是对称矩阵（Heisenberg 哈密顿量是厄米的，且在这组实基矢下矩阵元全为实数，所以厄米等价于对称）。

### 3.4 为什么系数是 0.5？

因为 $\mathbf{S}_i \cdot \mathbf{S}_j = S_i^z S_j^z + \frac{1}{2} S_i^+ S_j^- + \frac{1}{2} S_i^- S_j^+$

前面的 1/2 来自 $S^x = (S^+ + S^-)/2$, $S^y = (S^+ - S^-)/(2i)$ 的定义。展开 $S_i^x S_j^x + S_i^y S_j^y$ 后自然得到 $(S_i^+ S_j^- + S_i^- S_j^+)/2$。

---

## 4. 总自旋平方算符（exact_diag.jl）

### 4.1 物理意义

总自旋算符 $\mathbf{S}_{\text{tot}} = \sum_{i=1}^N \mathbf{S}_i$，其平方为：

$$\mathbf{S}_{\text{tot}}^2 = \left(\sum_i \mathbf{S}_i\right)^2 = \sum_i \mathbf{S}_i^2 + 2\sum_{i<j} \mathbf{S}_i \cdot \mathbf{S}_j$$

等价地写成（代码中用的形式，对所有 i≠j 求和，系数变为 1）：

$$\mathbf{S}_{\text{tot}}^2 = \sum_i \mathbf{S}_i^2 + \sum_{i \neq j} \mathbf{S}_i \cdot \mathbf{S}_j$$

对自旋 1/2，$\mathbf{S}_i^2 = S(S+1) = \frac{1}{2} \cdot \frac{3}{2} = \frac{3}{4}$，所以 N 个格点的单点贡献总共是 $N \times 3/4$。

### 4.2 为什么要算它？

$\mathbf{S}_{\text{tot}}^2$ 的本征值为 $S_{\text{tot}}(S_{\text{tot}}+1)$，其中 $S_{\text{tot}}$ 是总自旋量子数。对 5 个自旋 1/2 的耦合，可能的总自旋为：
- $S_{\text{tot}} = 1/2$（简并度 = 2×1/2+1 = 2，但考虑内部自由度后实际有多个这样的多重态）
- $S_{\text{tot}} = 3/2$
- $S_{\text{tot}} = 5/2$

通过群论计算（或直接对角化验证），32 维空间分解为：
- $S = 1/2$：10 个态（5 个二重态）
- $S = 3/2$：16 个态（4 个四重态）
- $S = 5/2$：6 个态（1 个六重态）

验证：10 + 16 + 6 = 32。

### 4.3 代码实现

```julia
function total_spin_squared_matrix(N::Int=5)
    dim = 2^N
    S2 = zeros(Float64, dim, dim)

    # 单点贡献：每个格点 S_i^2 = 3/4
    for idx in 1:dim
        S2[idx, idx] += N * 0.75
    end

    # 交叉项：对所有 i≠j 计算 S_i · S_j
    for i in 1:N, j in 1:N
        i == j && continue
        for idx in 1:dim
            config = index_to_config(idx, N)
            S2[idx, idx] += sz_value(config[i]) * sz_value(config[j])
            # 自旋翻转项（与哈密顿量中的逻辑完全相同）
            ...
        end
    end
    return Symmetric(S2)
end
```

注意这里对 **所有** i≠j 对求和（不只是最近邻），因为总自旋是全局量。而哈密顿量只对有键连接的近邻对求和。

---

## 5. 对角化与自旋标记（exact_diag.jl）

### 5.1 diagonalize_pentamer

```julia
function diagonalize_pentamer(alpha::Real; J1::Real=1.0)
    J2 = alpha * J1
    H = pentamer_hamiltonian_matrix(J1, J2)
    vals, vecs = eigen(Matrix(H))       # 全对角化

    S2 = total_spin_squared_matrix(5)
    spin_labels = Float64[]
    for i in 1:size(vecs, 2)
        v = vecs[:, i]
        s2_expect = dot(v, S2 * v)      # 计算 <ψ|S²|ψ>
        S = (-1 + sqrt(1 + 4*s2_expect)) / 2   # 从 S(S+1) 反解 S
        push!(spin_labels, round(S*2)/2)        # 四舍五入到半整数
    end
    return vals, vecs, spin_labels
end
```

关键步骤：
1. 构造 H 并调用 `eigen` 得到全部 32 个本征值和本征矢量
2. 对每个本征态 $|ψ_i\rangle$，计算期望值 $\langle ψ_i | \mathbf{S}_{\text{tot}}^2 | ψ_i \rangle$
3. 由 $S(S+1) = \text{期望值}$ 反解 $S = \frac{-1 + \sqrt{1 + 4 \cdot \text{期望值}}}{2}$
4. 四舍五入到最近的半整数（0.5, 1.5, 2.5）

**为什么这样做有效？** 因为 $[H, \mathbf{S}_{\text{tot}}^2] = 0$（Heisenberg 哈密顿量具有 SU(2) 对称性），所以 H 的本征态同时也是 $\mathbf{S}_{\text{tot}}^2$ 的本征态。对本征态求期望值就直接给出本征值。

**注意**：如果存在简并（同一能量有多个态），`eigen` 返回的本征矢量不一定是 $\mathbf{S}_{\text{tot}}^2$ 的本征态（它们可能是同一本征子空间中的任意线性组合）。但由于 $[H, S^2]=0$，简并子空间内 $S^2$ 也是对角的，所以实际上 `eigen` 的数值结果通常仍然给出好的量子数。代码中的 `round` 处理了微小的数值误差。

### 5.2 classify_states

这个函数把 32 个本征态按能量和总自旋分组：

```julia
function classify_states(eigenvalues, spin_labels; tol=1e-8)
    ...
end
```

它遍历所有态，把能量差小于 tol 且总自旋相同的态归为同一能级，记录简并度。最终返回按能量排序的能级列表 (E, S, degeneracy)。

---

## 6. 物理结果的意义

对均匀情形 $\alpha = J_2/J_1 = 1$（即所有键相同的 5 格点开边界 Heisenberg 链）：

- 基态能量 $E_0 \approx -1.92789$（以 $J_1$ 为单位）
- 基态在 $S = 1/2$ 扇区（反铁磁基态总自旋最小）

当 $\alpha$ 变化时，能级结构会改变。$\alpha = 0$ 是一个特殊极限：格点 1 和 5 与中间三聚体解耦，基态能量变为三聚体的基态能量 $-1.0$。

---

## 7. 整体流程总结

```
参数 (J1, alpha)
       │
       ▼
pentamer_hamiltonian_matrix(J1, J2)  ← 构造 32×32 矩阵
       │
       ▼
eigen(H)  ← 求全部本征值和本征矢量
       │
       ▼
total_spin_squared_matrix(5)  ← 构造 S² 矩阵
       │
       ▼
对每个本征态计算 <ψ|S²|ψ>  ← 标记总自旋量子数
       │
       ▼
classify_states  ← 按 (E, S) 分组，得到能级图
```

---

## 思考题

以下问题难度递增，建议按顺序思考。

**Q1（基础）**：为什么 5 个自旋 1/2 的希尔伯特空间维度是 32？如果是 N 个自旋 1/2，维度是多少？

**Q2（概念）**：代码中对角项 `H[idx, idx] += J * szi * szj` 的物理含义是什么？为什么 $S^z_i S^z_j$ 不改变基矢？

**Q3（推导）**：请验证 $S^x_i S^x_j + S^y_i S^y_j = \frac{1}{2}(S^+_i S^-_j + S^-_i S^+_j)$。提示：用 $S^x = (S^+ + S^-)/2$ 和 $S^y = (S^+ - S^-)/(2i)$ 代入展开。

**Q4（对称性）**：为什么 $[H, \mathbf{S}_{\text{tot}}^2] = 0$？这个对易关系在代码中有什么实际用途？如果哈密顿量加上一个外磁场项 $h \sum_i S_i^z$，这个对易关系还成立吗？

**Q5（进阶）**：5 个自旋 1/2 耦合后，总自旋的可能取值为 S=1/2, 3/2, 5/2，对应的态数分别是 10, 16, 6。请用角动量耦合规则推导这些数字。提示：先耦合两个自旋得到 S=0 和 S=1，再逐步加入第三、第四、第五个自旋。

**Q6（数值）**：如果 `eigen` 返回的某个简并子空间中的本征矢量不是 $S^2$ 的本征态（而是它们的线性组合），`dot(v, S2 * v)` 还能给出正确的 $S$ 值吗？在什么条件下会出问题？代码中的 `round` 能否总是修正这个问题？

**Q7（物理直觉）**：当 $\alpha \to 0$ 时，五聚体退化为"孤立格点 1 + 三聚体(2,3,4) + 孤立格点 5"。三聚体的基态能量为 $-1.0$，总自旋为 $S=1/2$。请解释：为什么整个五聚体在这个极限下基态仍然是 $S=1/2$（而不是更高的自旋）？基态简并度是多少？
