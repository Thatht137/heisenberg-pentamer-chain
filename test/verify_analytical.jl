"""
验证 references/ 中的解析推导与 src/ 数值 ED 的一致性。

对比内容：
1. 能级（α=1 均匀链）：10 个解析能级 vs 数值 ED
2. S² 分类：S=1/2(10), 3/2(16), 5/2(6)
3. 各 (S, r) 扇区的解析哈密顿矩阵公式 vs 数值
4. 本征矢：解析给出的乘积基展开 vs 数值本征矢（最大重叠）
"""

using Pkg
Pkg.activate(joinpath(@__DIR__, ".."))
include(joinpath(@__DIR__, "..", "src", "PentamerChain.jl"))
using .PentamerChain
using LinearAlgebra
using Printf

const φ = (1 + sqrt(5)) / 2

# ---------- 解析能级表（references 给出，α=1） ----------
# (#, E_exact, S, r, mult)
analytical_levels = [
    (-1.9278862533, 1//2, +1, 2),
    (-sqrt(2)/2 - 1//2, 1//2, -1, 2),
    (-sqrt(5)/4 - 1//4, 3//2, +1, 4),
    (-0.6608185871, 1//2, +1, 2),
    (1//4 - sqrt(5)/4, 3//2, -1, 4),
    (-1//2 + sqrt(2)/2, 1//2, -1, 2),
    (-1//4 + sqrt(5)/4, 3//2, +1, 4),
    (0.5887048404, 1//2, +1, 2),
    (1//4 + sqrt(5)/4, 3//2, -1, 4),
    (1, 5//2, +1, 6),
]

# ---------- 各扇区解析哈密顿矩阵 (α=1 → α=1) ----------
# H_{5/2,+} = [1/2 + α/2]
# H_{3/2,-} = [0  α/2; α/2  1/2]
# H_{3/2,+} = [-1+α/3  -α√5/6; -α√5/6  1/2-α/3]
# H_{1/2,-} = [0  -α/2; -α/2  -1]
# H_{1/2,+} = 3x3 (见推导)

function analytic_block(S, r, α)
    if S == 5//2 && r == +1
        return fill(1/2 + α/2, 1, 1)
    elseif S == 3//2 && r == -1
        return [0 α/2; α/2 1/2]
    elseif S == 3//2 && r == +1
        return [-1+α/3  -α*sqrt(5)/6; -α*sqrt(5)/6  1/2-α/3]
    elseif S == 1//2 && r == -1
        return [0 -α/2; -α/2 -1]
    elseif S == 1//2 && r == +1
        return [0      -α/2      -α/sqrt(2);
                -α/2   -1-2α/3   -α/sqrt(18);
                -α/sqrt(2) -α/sqrt(18)  1/2-5α/6]
    else
        error("Unknown sector S=$S r=$r")
    end
end

# ---------- 镜像算符 R: 1↔5, 2↔4, 3↔3 ----------
# 在乘积基下构造 R 矩阵
function mirror_matrix(N=5)
    dim = 2^N
    R = zeros(Int, dim, dim)
    for idx in 1:dim
        cfg = PentamerChain.index_to_config(idx, N)
        # 翻转：位置 1<->N, 2<->N-1, ...
        rcfg = reverse(cfg)
        jdx = PentamerChain.spin_basis_state(rcfg)
        R[jdx, idx] = 1
    end
    return R
end

# ---------- 验证 1：能级 ----------
function verify_energies()
    println("\n" * "="^80)
    println("验证 1：能级对比（α=1 均匀链）")
    println("="^80)
    H = Matrix(pentamer_hamiltonian_matrix(1.0, 1.0))
    vals = eigvals(H)
    sort!(vals)

    # 解析能级（展开简并）
    analytic_expanded = Float64[]
    for (E, S, r, m) in analytical_levels
        for _ in 1:m
            push!(analytic_expanded, Float64(E))
        end
    end
    sort!(analytic_expanded)

    @printf("%-4s  %-22s  %-22s  %-12s\n", "#", "E 解析", "E 数值", "|Δ|")
    println("-"^80)
    max_err = 0.0
    for i in eachindex(vals)
        err = abs(vals[i] - analytic_expanded[i])
        max_err = max(max_err, err)
        @printf("%-4d  %22.12f  %22.12f  %.2e\n", i, analytic_expanded[i], vals[i], err)
    end
    println("-"^80)
    @printf("最大误差：%.2e  %s\n", max_err, max_err < 1e-8 ? "PASS ✓" : "FAIL ✗")
    return max_err < 1e-8
end

# ---------- 验证 2：S² 分类 ----------
function verify_spin_classification()
    println("\n" * "="^80)
    println("验证 2：总自旋 S² 分类")
    println("="^80)
    S2 = Matrix(total_spin_squared_matrix(5))
    s2_vals = eigvals(S2)
    sort!(s2_vals)

    # 期望：S=1/2 (×10, S²=0.75), S=3/2 (×16, S²=3.75), S=5/2 (×6, S²=8.75)
    expected = vcat(fill(0.75, 10), fill(3.75, 16), fill(8.75, 6))
    sort!(expected)

    max_err = 0.0
    for i in eachindex(s2_vals)
        max_err = max(max_err, abs(s2_vals[i] - expected[i]))
    end
    @printf("S=1/2 应有 10 重简并（S²=0.75）\n")
    @printf("S=3/2 应有 16 重简并（S²=3.75）\n")
    @printf("S=5/2 应有 6 重简并（S²=8.75）\n")
    @printf("最大误差：%.2e  %s\n", max_err, max_err < 1e-10 ? "PASS ✓" : "FAIL ✗")

    # 同时验证哈密顿量与 S² 对易
    H = Matrix(pentamer_hamiltonian_matrix(1.0, 1.0))
    comm = norm(H*S2 - S2*H)
    @printf("[H, S²] 范数：%.2e  %s\n", comm, comm < 1e-10 ? "PASS ✓" : "FAIL ✗")
    return max_err < 1e-10 && comm < 1e-10
end

# ---------- 验证 3：镜像宇称分块 ----------
# 通过同时本征矢构造各扇区子空间，与解析矩阵对比
function verify_sector_blocks()
    println("\n" * "="^80)
    println("验证 3：各 (S, r) 扇区哈密顿矩阵")
    println("="^80)

    H = Matrix(pentamer_hamiltonian_matrix(1.0, 1.0))
    S2 = Matrix(total_spin_squared_matrix(5))
    R = mirror_matrix(5)
    dim = 32

    # 构造总 Sz
    Sz = zeros(Float64, dim, dim)
    for idx in 1:dim
        cfg = PentamerChain.index_to_config(idx, 5)
        Sz[idx, idx] = sum(PentamerChain.sz_value.(cfg))
    end

    all_pass = true
    for (S, r, dim_expected) in [(5//2, +1, 1), (3//2, -1, 2), (3//2, +1, 2),
                                  (1//2, -1, 2), (1//2, +1, 3)]
        S_target = Float64(S)
        S2_target = S_target * (S_target + 1)
        M_target = S_target  # 取最高权态

        # 1) 限定 Sz = M_target 子空间
        sz_inds = findall(idx -> abs(Sz[idx, idx] - M_target) < 1e-12, 1:dim)
        H_sub = H[sz_inds, sz_inds]
        S2_sub = S2[sz_inds, sz_inds]
        R_sub = R[sz_inds, sz_inds]

        # 2) 在此子空间对角化 H
        vals_m, vecs_m = eigen(Hermitian(H_sub))

        # 3) 对每个能级簇，在简并子空间内对角化 R 和 S² 取共同本征矢
        used = falses(length(vals_m))
        sector_vecs = Vector{Vector{Float64}}()
        for i in eachindex(vals_m)
            used[i] && continue
            # 收集简并（同能量）
            degen = [i]
            for j in (i+1):length(vals_m)
                if !used[j] && abs(vals_m[j] - vals_m[i]) < 1e-8
                    push!(degen, j)
                    used[j] = true
                end
            end
            used[i] = true
            Vdeg = vecs_m[:, degen]
            # 在简并子空间对角化 R
            R_deg = Vdeg' * R_sub * Vdeg
            rv, rvecs = eigen(Hermitian(R_deg))
            # 同步检查 S²（应仍守恒）
            S2_deg = Vdeg' * S2_sub * Vdeg
            for k in eachindex(rv)
                if abs(rv[k] - r) < 1e-6 && abs(diag(S2_deg)[k] - S2_target) < 1e-6
                    # 重构到原始 32 维空间
                    v_full = zeros(Float64, dim)
                    v_full[sz_inds] = Vdeg * rvecs[:, k]
                    push!(sector_vecs, v_full)
                end
            end
        end

        n_found = length(sector_vecs)
        @printf("扇区 S=%-4s r=%+d: 期望维数 %d, 找到 %d  %s\n",
                S, r, dim_expected, n_found,
                n_found == dim_expected ? "✓" : "✗")
        if n_found != dim_expected
            all_pass = false
            continue
        end

        # 构造子空间投影
        V = hcat(sector_vecs...)
        Qf = qr(V)
        Q = Matrix(Qf.Q)[:, 1:n_found]
        H_block = Matrix(Q' * H * Q)

        analytic = analytic_block(S, r, 1.0)
        # 注：数值基底是 R 的本征矢，未必是 analytic_block 的耦合基底，
        # 所以矩阵元不一定匹配，但本征值集合必须一致。
        ev = sort(eigvals(Hermitian(H_block)))
        ev_a = sort(eigvals(Hermitian(analytic)))
        ev_err = isempty(ev) ? 0.0 : maximum(abs.(ev .- ev_a))

        @printf("  解析矩阵:\n")
        for row in eachrow(analytic)
            @printf("    [%s]\n", join(@sprintf("%10.6f", x) for x in row))
        end
        @printf("  数值矩阵 (R 本征基):\n")
        for row in eachrow(H_block)
            @printf("    [%s]\n", join(@sprintf("%10.6f", x) for x in row))
        end
        @printf("  本征值对比: 数值=%s  解析=%s  err=%.2e  %s\n",
                join(@sprintf("%.6f", x) for x in ev),
                join(@sprintf("%.6f", x) for x in ev_a), ev_err,
                ev_err < 1e-8 ? "PASS ✓" : "FAIL ✗")
        if ev_err >= 1e-8
            all_pass = false
        end
    end
    return all_pass
end

# ---------- 验证 4：解析本征矢对比 ----------
# references/pentamer_analytical_states.txt 给出了 α=1 的全部 32 个本征矢
# 在乘积基 |m1 m2 m3 m4 m5⟩ 下的展开。这里只挑几个关键的验证重叠。
function verify_eigenvectors()
    println("\n" * "="^80)
    println("验证 4：本征矢重叠（关键态）")
    println("="^80)

    H = Matrix(pentamer_hamiltonian_matrix(1.0, 1.0))
    vals, vecs = eigen(H)
    dim = 32

    # 构造总 Sz 和镜像算符 R
    Sz = zeros(Float64, dim, dim)
    for idx in 1:dim
        cfg = PentamerChain.index_to_config(idx, 5)
        Sz[idx, idx] = sum(PentamerChain.sz_value.(cfg))
    end
    R = mirror_matrix(5)

    # 辅助：在 (M, r, E) 三量子数指定的本征态上算与目标态的重叠
    # 1) 取 Sz=M_target 子空间
    # 2) 在此子空间对角化 R 拿 r=r_target 子空间
    # 3) 在 (M, r) 子空间对角化 H，取能量≈E_target 的本征矢
    function overlap_with_quantum_numbers(target_state, E_target, M_target, r_target; Etol=1e-6)
        # 1) Sz 子空间
        sz_inds = findall(idx -> abs(Sz[idx, idx] - M_target) < 1e-12, 1:dim)
        H_m = Hermitian(H[sz_inds, sz_inds])
        R_m = Hermitian(R[sz_inds, sz_inds])
        # 2) 在 M 子空间对角化 R
        rv, rvecs = eigen(R_m)
        r_inds = findall(k -> abs(rv[k] - r_target) < 1e-6, eachindex(rv))
        isempty(r_inds) && return (0.0, NaN)
        # (M, r) 子空间的本征矢基底
        Vr = rvecs[:, r_inds]
        # 3) 在此子空间对角化 H
        H_mr = Hermitian(Vr' * H[sz_inds, sz_inds] * Vr)
        hv, hvecs = eigen(H_mr)
        # 找能量匹配且重叠最大的
        best_ov = 0.0
        best_E = NaN
        for k in eachindex(hv)
            if abs(hv[k] - E_target) < Etol
                v_full = zeros(Float64, dim)
                v_full[sz_inds] = Vr * hvecs[:, k]
                ov = abs(dot(v_full, target_state))
                if ov > best_ov
                    best_ov = ov
                    best_E = hv[k]
                end
            end
        end
        return (best_ov, best_E)
    end

    # S=5/2, M=+5/2: |↑↑↑↑↑⟩
    s_upup = zeros(32)
    s_upup[PentamerChain.spin_basis_state([1,1,1,1,1])] = 1.0
    ov1, E1_num = overlap_with_quantum_numbers(s_upup, 1.0, 2.5, +1)
    @printf("S=5/2, M=+5/2 (|↑↑↑↑↑⟩):  |⟨num|analytic⟩| = %.10f  %s\n",
            ov1, ov1 > 0.9999 ? "PASS ✓" : "FAIL ✗")

    # S=5/2, M=+3/2: √5/5 × (5 个单翻转态)
    s_3_2 = zeros(32)
    for cfg in [[1,1,1,1,0], [1,1,1,0,1], [1,1,0,1,1], [1,0,1,1,1], [0,1,1,1,1]]
        s_3_2[PentamerChain.spin_basis_state(cfg)] = sqrt(5)/5
    end
    s_3_2 ./= norm(s_3_2)
    ov2, _ = overlap_with_quantum_numbers(s_3_2, 1.0, 1.5, +1)
    @printf("S=5/2, M=+3/2:           |⟨num|analytic⟩| = %.10f  %s\n",
            ov2, ov2 > 0.9999 ? "PASS ✓" : "FAIL ✗")

    # LEVEL 1 (基态): E=-1.9278862533, S=1/2, r=+, M=+1/2
    cfg_strs = ["↑↓↑↓↑", "↑↓↑↑↓", "↓↑↑↓↑", "↑↑↓↑↓", "↑↑↓↓↑",
                "↑↓↓↑↑", "↓↑↓↑↑", "↓↑↑↑↓", "↑↑↑↓↓", "↓↓↑↑↑"]
    coeffs = [0.66545714, -0.38444677, -0.38444677, 0.23302176, -0.23302176,
              -0.23302176, 0.23302176, 0.19941362, -0.04798861, -0.04798861]
    gs_state = zeros(32)
    for (s, c) in zip(cfg_strs, coeffs)
        cfg = [ch == '↑' ? 1 : 0 for ch in s]
        gs_state[PentamerChain.spin_basis_state(cfg)] = c
    end
    gs_state ./= norm(gs_state)
    ov3, E_gs_num = overlap_with_quantum_numbers(gs_state, -1.9278862533, 0.5, +1, Etol=1e-4)
    @printf("基态 E=%.6f, M=+1/2:      |⟨num|analytic⟩| = %.10f  %s\n",
            E_gs_num, ov3, ov3 > 0.9999 ? "PASS ✓" : "FAIL ✗")

    # LEVEL 2 & 3：在 (M, r, S) 三量子数子空间里取数值本征矢，验证能量等于解析公式
    # 验证 3 已证 block 矩阵本征值正确，这里再独立确认 (M,S,r) 标签正确
    S2op = Matrix(total_spin_squared_matrix(5))

    function energy_in_sector(M_target, r_target, S_target, E_target; Etol=1e-6)
        # 1) Sz=M 子空间
        sz_inds = findall(idx -> abs(Sz[idx, idx] - M_target) < 1e-12, 1:dim)
        # 2) 在 M 子空间对角化 R
        R_m = Hermitian(R[sz_inds, sz_inds])
        rv, rvecs = eigen(R_m)
        r_inds = findall(k -> abs(rv[k] - r_target) < 1e-6, eachindex(rv))
        Vr = rvecs[:, r_inds]
        # 3) 在 (M,r) 子空间对角化 S²
        S2_mr = Hermitian(Vr' * S2op[sz_inds, sz_inds] * Vr)
        s2v, s2vecs = eigen(S2_mr)
        s_target = S_target * (S_target + 1)
        s_inds = findall(k -> abs(s2v[k] - s_target) < 1e-6, eachindex(s2v))
        Vs = Vr * s2vecs[:, s_inds]
        # 4) 在 (M,r,S) 子空间对角化 H
        H_mrs = Hermitian(Vs' * H[sz_inds, sz_inds] * Vs)
        ev = eigvals(H_mrs)
        # 找最接近 E_target 的
        if isempty(ev)
            return (NaN, NaN)
        end
        i = argmin(abs.(ev .- E_target))
        return (ev[i], abs(ev[i] - E_target))
    end

    # LEVEL 2: S=1/2, r=-, M=1/2, E=-√2/2-1/2
    E2 = -sqrt(2)/2 - 1/2
    E2_num, E2_err = energy_in_sector(0.5, -1, 1//2, E2)
    @printf("LEVEL 2 E=%.6f (1/2,r=-): 数值 E=%.6f, err=%.2e  %s\n",
            E2, E2_num, E2_err, E2_err < 1e-8 ? "PASS ✓" : "FAIL ✗")

    # LEVEL 3: S=3/2, r=+, M=3/2, E=-√5/4-1/4
    E3 = -sqrt(5)/4 - 1/4
    E3_num, E3_err = energy_in_sector(1.5, +1, 3//2, E3)
    @printf("LEVEL 3 E=%.6f (3/2,r=+): 数值 E=%.6f, err=%.2e  %s\n",
            E3, E3_num, E3_err, E3_err < 1e-8 ? "PASS ✓" : "FAIL ✗")

    # 额外：验证 LEVEL 5 (3/2,r=-), LEVEL 7 (3/2,r=+), LEVEL 9 (3/2,r=-)
    E5 = 1//4 - sqrt(5)/4
    E5_num, E5_err = energy_in_sector(1.5, -1, 3//2, Float64(E5))
    @printf("LEVEL 5 E=%.6f (3/2,r=-): 数值 E=%.6f, err=%.2e  %s\n",
            Float64(E5), E5_num, E5_err, E5_err < 1e-8 ? "PASS ✓" : "FAIL ✗")

    E7 = -1//4 + sqrt(5)/4
    E7_num, E7_err = energy_in_sector(1.5, +1, 3//2, Float64(E7))
    @printf("LEVEL 7 E=%.6f (3/2,r=+): 数值 E=%.6f, err=%.2e  %s\n",
            Float64(E7), E7_num, E7_err, E7_err < 1e-8 ? "PASS ✓" : "FAIL ✗")

    E9 = 1//4 + sqrt(5)/4
    E9_num, E9_err = energy_in_sector(1.5, -1, 3//2, Float64(E9))
    @printf("LEVEL 9 E=%.6f (3/2,r=-): 数值 E=%.6f, err=%.2e  %s\n",
            Float64(E9), E9_num, E9_err, E9_err < 1e-8 ? "PASS ✓" : "FAIL ✗")

    # LEVEL 6: S=1/2, r=-, M=1/2, E=-1/2+√2/2
    E6 = -1//2 + sqrt(2)/2
    E6_num, E6_err = energy_in_sector(0.5, -1, 1//2, Float64(E6))
    @printf("LEVEL 6 E=%.6f (1/2,r=-): 数值 E=%.6f, err=%.2e  %s\n",
            Float64(E6), E6_num, E6_err, E6_err < 1e-8 ? "PASS ✓" : "FAIL ✗")

    return ov1 > 0.9999 && ov2 > 0.9999 && ov3 > 0.9999 &&
           E2_err < 1e-8 && E3_err < 1e-8 && E5_err < 1e-8 &&
           E7_err < 1e-8 && E9_err < 1e-8 && E6_err < 1e-8
end

# 辅助：总 Sz 算符
function Sz_total(N=5)
    dim = 2^N
    Sz = zeros(Float64, dim, dim)
    for idx in 1:dim
        cfg = PentamerChain.index_to_config(idx, N)
        Sz[idx, idx] = sum(PentamerChain.sz_value.(cfg))
    end
    return Sz
end

# ---------- 验证 5：α 变化时解析公式 ----------
function verify_alpha_sweep()
    println("\n" * "="^80)
    println("验证 5：α 扫描下各扇区最低能级")
    println("="^80)
    # 验证 E_{1/2,-}^{±} = -1/2 ± 1/2√(1+α²)
    # 这是 r=-, S=1/2 扇区的 2x2 解析解
    alphas = [0.0, 0.3, 0.5, 0.7, 1.0, 1.5, 2.0]
    max_err = 0.0
    @printf("%-6s  %-22s  %-22s  %-12s\n", "α", "E_{1/2,-}^- 解析", "数值最低(r=-)", "|Δ|")
    println("-"^80)
    dim = 32
    for α in alphas
        H = Matrix(pentamer_hamiltonian_matrix(1.0, α))
        S2 = Matrix(total_spin_squared_matrix(5))
        R = mirror_matrix(5)
        # 构造 Sz
        Sz = Diagonal([sum(PentamerChain.sz_value.(PentamerChain.index_to_config(i,5))) for i in 1:dim])
        # 1) M=1/2 子空间
        sz_inds = findall(i -> abs(Sz[i,i] - 0.5) < 1e-12, 1:dim)
        # 2) 在 M 子空间对角化 R
        R_m = Hermitian(R[sz_inds, sz_inds])
        rv, rvecs = eigen(R_m)
        r_inds = findall(k -> abs(rv[k] + 1) < 1e-6, eachindex(rv))
        Vr = rvecs[:, r_inds]
        # 3) 在 (M,r) 子空间对角化 S²
        S2_mr = Hermitian(Vr' * S2[sz_inds, sz_inds] * Vr)
        s2v, s2vecs = eigen(S2_mr)
        s_inds = findall(k -> abs(s2v[k] - 0.75) < 1e-6, eachindex(s2v))
        Vs = Vr * s2vecs[:, s_inds]
        # 4) 对角化 H
        H_mrs = Hermitian(Vs' * H[sz_inds, sz_inds] * Vs)
        ev = sort(eigvals(H_mrs))
        E_analytic = -0.5 - 0.5*sqrt(1+α^2)
        if isempty(ev)
            @printf("%-6.1f  子空间为空\n", α)
            continue
        end
        err = abs(ev[1] - E_analytic)
        max_err = max(max_err, err)
        @printf("%-6.1f  %22.12f  %22.12f  %.2e\n", α, E_analytic, ev[1], err)
    end
    println("-"^80)
    @printf("最大误差：%.2e  %s\n", max_err, max_err < 1e-8 ? "PASS ✓" : "FAIL ✗")
    return max_err < 1e-8
end

# ---------- 主程序 ----------
function main()
    println("="^80)
    println("五聚体 J₁-J₂ 海森堡模型：解析推导 vs 数值 ED 验证")
    println("="^80)

    r1 = verify_energies()
    r2 = verify_spin_classification()
    r3 = verify_sector_blocks()
    r4 = verify_eigenvectors()
    r5 = verify_alpha_sweep()

    println("\n" * "="^80)
    println("总结")
    println("="^80)
    @printf("  能级对比:         %s\n", r1 ? "PASS ✓" : "FAIL ✗")
    @printf("  S² 分类:          %s\n", r2 ? "PASS ✓" : "FAIL ✗")
    @printf("  扇区哈密顿矩阵:   %s\n", r3 ? "PASS ✓" : "FAIL ✗")
    @printf("  本征矢重叠:       %s\n", r4 ? "PASS ✓" : "FAIL ✗")
    @printf("  α 扫描公式:       %s\n", r5 ? "PASS ✓" : "FAIL ✗")
    println("="^80)
end

main()
