"""
单个五聚体单元的精确对角化。
"""

"""
    total_spin_squared_matrix(N=5)

构造 N 个自旋 1/2 格点的总自旋平方算符矩阵。
"""
function total_spin_squared_matrix(N::Int=5)
    dim = 2^N
    S2 = zeros(Float64, dim, dim)

    # 单点 S_i^2 贡献
    for idx in 1:dim
        S2[idx, idx] += N * 0.75
    end

    # 不同格点之间的交叉项
    for i in 1:N, j in 1:N
        i == j && continue
        for idx in 1:dim
            config = index_to_config(idx, N)

            # Sz_i * Sz_j
            S2[idx, idx] += sz_value(config[i]) * sz_value(config[j])

            # 自旋翻转项
            if config[i] == 0 && config[j] == 1
                new_config = copy(config)
                new_config[i] = 1
                new_config[j] = 0
                jdx = spin_basis_state(new_config)
                S2[jdx, idx] += 0.5
            end
            if config[i] == 1 && config[j] == 0
                new_config = copy(config)
                new_config[i] = 0
                new_config[j] = 1
                jdx = spin_basis_state(new_config)
                S2[jdx, idx] += 0.5
            end
        end
    end

    return Symmetric(S2)
end

"""
    diagonalize_pentamer(alpha; J1=1.0)

对 J2/J1=alpha 的单个五聚体做精确对角化。
返回能量、本征矢和总自旋标记。
"""
function diagonalize_pentamer(alpha::Real; J1::Real=1.0)
    J2 = alpha * J1
    H = pentamer_hamiltonian_matrix(J1, J2)
    vals, vecs = eigen(Matrix(H))

    S2 = Matrix(total_spin_squared_matrix(5))
    spin_labels = zeros(Float64, length(vals))
    energy_tol = 1e-9

    group_start = 1
    while group_start <= length(vals)
        group_end = group_start
        while group_end < length(vals) &&
              abs(vals[group_end + 1] - vals[group_start]) < energy_tol
            group_end += 1
        end

        inds = group_start:group_end
        subspace = vecs[:, inds]
        s2_vals, rotation = eigen(Hermitian(subspace' * S2 * subspace))
        vecs[:, inds] = subspace * rotation

        for (offset, s2_value) in enumerate(s2_vals)
            S = (-1 + sqrt(1 + 4 * max(s2_value, 0.0))) / 2
            spin_labels[group_start + offset - 1] = round(S * 2) / 2
        end

        group_start = group_end + 1
    end

    return vals, vecs, spin_labels
end

"""
    classify_states(eigenvalues, spin_labels)

按能量和总自旋合并能级，返回能量、总自旋和简并度。
"""
function classify_states(eigenvalues::Vector{Float64}, spin_labels::Vector{Float64};
                         tol::Real=1e-8)
    levels = Tuple{Float64, Float64, Int}[]  # 能量、总自旋、简并度
    used = falses(length(eigenvalues))

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

    sort!(levels, by=x -> x[1])
    return levels
end
