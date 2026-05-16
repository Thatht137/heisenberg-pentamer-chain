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
    correction_vector_dsf(psi_gs, H, sites, E0; q, omega, eta, maxdim, cutoff)

用修正向量法计算单个 (q, omega) 点。
"""
function correction_vector_dsf(psi_gs, H, sites, E0::Real;
    q::Real, omega::Real, eta::Real=0.1,
    maxdim::Int=200, cutoff::Real=1e-6, nsweeps::Int=4)

    # 右端向量
    b = apply_Sq_operator(psi_gs, sites, q)

    # 求解 (a - H)|x> = |b>
    a = (omega + E0) + im * eta

    x = linsolve(H, b, b, a, -1;
        nsweeps, maxdim, cutoff,
        updater_kwargs=(; tol=1e-5))

    return -1 / π * imag(inner(b, x))
end

"""
    compute_dsf_spectrum(psi_gs, H, sites, E0; q_points, omega_range, eta, maxdim, cutoff, chunk_size)

计算完整的 S(q, omega) 谱。
按 q 点分块并行以控制内存占用。
"""
function compute_dsf_spectrum(psi_gs, H, sites, E0::Real;
    q_points=range(0, 2π, length=33),
    omega_range=range(0, 4, length=101),
    eta::Real=0.1,
    maxdim::Int=200,
    cutoff::Real=1e-6,
    chunk_size::Int=4)

    nq = length(q_points)
    nw = length(omega_range)
    S_qw = zeros(Float64, nq, nw)

    q_chunks = Iterators.partition(1:nq, chunk_size)

    for chunk in q_chunks
        tasks = map(chunk) do iq
            Threads.@spawn begin
                local_psi = deepcopy(psi_gs)
                local_H = deepcopy(H)
                local_sites = sites  # 格点指标可共享

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

        for t in tasks
            iq, row = fetch(t)
            S_qw[iq, :] = row
        end
    end

    return S_qw
end
