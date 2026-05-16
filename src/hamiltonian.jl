"""
自旋 1/2 五聚体链的哈密顿量构造。

耦合结构：
    o--J2--o--J1--o--J1--o--J2--o  ---J3---  o--J2--o--J1--o--J1--o--J2--o
    1      2      3      4      5             6      7      8      9      10

参数：alpha = J2/J1，beta = J3/J1。
"""

"""
    pentamer_hamiltonian_matrix(J1, J2)

构造单个孤立五聚体的 32x32 哈密顿量矩阵。
基矢采用 0/1 自旋编码。
"""
function pentamer_hamiltonian_matrix(J1::Real, J2::Real)
    dim = 32  # 五个自旋 1/2 的希尔伯特空间维数
    H = zeros(Float64, dim, dim)

    for idx in 1:dim
        config = index_to_config(idx, 5)

        # 对角项：Sz_i * Sz_j
        bonds = [(1, 2, J2), (2, 3, J1), (3, 4, J1), (4, 5, J2)]

        for (i, j, J) in bonds
            szi = sz_value(config[i])
            szj = sz_value(config[j])
            H[idx, idx] += J * szi * szj
        end

        # 非对角项：自旋翻转
        for (i, j, J) in bonds
            # S+_i S-_j
            if config[i] == 0 && config[j] == 1
                new_config = copy(config)
                new_config[i] = 1
                new_config[j] = 0
                jdx = spin_basis_state(new_config)
                H[jdx, idx] += J * 0.5
            end
            # S-_i S+_j
            if config[i] == 1 && config[j] == 0
                new_config = copy(config)
                new_config[i] = 0
                new_config[j] = 1
                jdx = spin_basis_state(new_config)
                H[jdx, idx] += J * 0.5
            end
        end
    end

    return Symmetric(H)
end

"""
    pentamer_chain_hamiltonian(sites, N_units; alpha=1.0, beta=0.5)

构造整条五聚体链的 ITensors MPO。
- N_units：五聚体单元数
- alpha：胞内 J2/J1
- beta：胞间 J3/J1
- J1 固定为能量单位
"""
function pentamer_chain_hamiltonian(sites, N_units::Int; alpha::Real=1.0, beta::Real=0.5)
    J1 = 1.0
    J2 = alpha * J1
    J3 = beta * J1
    L = length(sites)
    @assert L == 5 * N_units "Site count must equal 5 * N_units"

    os = OpSum()

    for n in 1:N_units
        s1 = 5 * (n - 1) + 1
        s2 = s1 + 1
        s3 = s1 + 2
        s4 = s1 + 3
        s5 = s1 + 4

        # 胞内键：两端 J2，中间 J1
        for (si, sj, J) in [(s1, s2, J2), (s2, s3, J1), (s3, s4, J1), (s4, s5, J2)]
            os += J, "Sz", si, "Sz", sj
            os += J * 0.5, "S+", si, "S-", sj
            os += J * 0.5, "S-", si, "S+", sj
        end

        # 胞间键：当前单元末端连到下一单元起点
        if n < N_units
            s_next = 5 * n + 1
            os += J3, "Sz", s5, "Sz", s_next
            os += J3 * 0.5, "S+", s5, "S-", s_next
            os += J3 * 0.5, "S-", s5, "S+", s_next
        end
    end

    return MPO(os, sites)
end
