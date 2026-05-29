"""
用修正向量法计算动力学结构因子 S(q, omega)。

通过 ITensorMPS.linsolve 求解修正向量方程。
"""

"""
    apply_Sq_operator(psi, sites, q)

对 MPS 施加动量空间的 S^z_q 算符。
margin_sites 用于丢弃边界格点。
"""
function apply_Sq_operator(psi, sites, q::Real; margin_sites::Int=0)
    N = length(sites)
    n_start = margin_sites + 1
    n_end = N - margin_sites
    N_eff = n_end - n_start + 1

    result = nothing
    for j in n_start:n_end
        coeff = exp(im * q * j) / sqrt(N_eff)
        psi_j = copy(psi)
        new_tensor = noprime(psi_j[j] * op("Sz", sites[j]))
        psi_j[j] = new_tensor

        if isnothing(result)
            result = coeff * psi_j
        else
            result = add(result, coeff * psi_j; cutoff=1e-10, maxdim=linkdim_max(psi) + 50)
        end
    end
    return result
end

function linkdim_max(psi)
    return maximum(dim.(linkinds(psi)))
end

"""
    correction_vector_dsf(b, H, E0; omega, eta, maxdim, cutoff)

用修正向量法计算单个 (q, omega) 点。b = S^z_q |psi> 由外部预先计算。
"""
function correction_vector_dsf(b, H, E0::Real;
    omega::Real, eta::Real=0.1,
    maxdim::Int=200, cutoff::Real=1e-6, nsweeps::Int=4)

    a = (omega + E0) + im * eta

    x = linsolve(H, b, b, a, -1;
        nsweeps, maxdim, cutoff,
        updater_kwargs=(; tol=1e-5))

    return -1 / π * imag(inner(b, x))
end

"""
    compute_dsf_spectrum(psi_gs, H, sites, E0; q_points, omega_range, eta, maxdim, cutoff, chunk_size, checkpoint_file)

计算完整的 S(q, omega) 谱。
按 q 点分块并行以控制内存占用。支持 checkpoint 断点续算。
"""
function compute_dsf_spectrum(psi_gs, H, sites, E0::Real;
    q_points=range(0, 2π, length=33),
    omega_range=range(0, 4, length=101),
    eta::Real=0.1,
    maxdim::Int=200,
    cutoff::Real=1e-6,
    chunk_size::Int=4,
    checkpoint_file::String="")

    nq = length(q_points)
    nw = length(omega_range)
    S_qw = zeros(Float64, nq, nw)
    completed = falses(nq)

    # 从 checkpoint 恢复
    if !isempty(checkpoint_file) && isfile(checkpoint_file)
        @info "从 checkpoint 恢复: $checkpoint_file"
        ckpt = load(checkpoint_file)
        S_qw .= ckpt["S_qw"]
        completed .= ckpt["completed"]
        n_done = count(completed)
        @info "已完成 $n_done/$nq 个 q 点，继续计算剩余部分..."
    end

    remaining = findall(.!completed)
    if isempty(remaining)
        @info "所有 q 点已完成，无需继续计算。"
        return S_qw
    end

    q_chunks = Iterators.partition(remaining, chunk_size)

    for chunk in q_chunks
        tasks = map(chunk) do iq
            Threads.@spawn begin
                local_psi = deepcopy(psi_gs)
                local_H = deepcopy(H)
                local_sites = sites

                q = q_points[iq]
                b = apply_Sq_operator(local_psi, local_sites, q)
                @info "q[$iq/$nq] = $(round(q, digits=3)): S^z_q|ψ> 已构造"
                flush(stdout); flush(stderr)

                row = zeros(Float64, nw)
                for (iw, omega) in enumerate(omega_range)
                    row[iw] = correction_vector_dsf(
                        b, local_H, E0;
                        omega, eta, maxdim, cutoff)
                    if iw % 5 == 0 || iw == nw
                        @info "  q[$iq] omega 进度: $iw/$nw"
                        flush(stdout); flush(stderr)
                    end
                end
                (iq, row)
            end
        end

        for t in tasks
            iq, row = fetch(t)
            S_qw[iq, :] = row
            completed[iq] = true
        end

        # 每完成一个 chunk 就保存 checkpoint
        if !isempty(checkpoint_file)
            n_done = count(completed)
            @info "进度: $n_done/$nq q 点完成，保存 checkpoint..."
            jldsave(checkpoint_file; S_qw, completed,
                q_points=collect(q_points), omega_range=collect(omega_range),
                eta, maxdim, E0)
        end
    end

    return S_qw
end
