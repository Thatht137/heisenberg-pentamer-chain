"""
五聚体链的 DMRG 基态和激发态计算。
"""

"""
    compute_ground_state(; N_units=12, alpha=1.0, beta=0.5, maxdim=800, cutoff=1e-8, nsweeps=10)

用 DMRG 求五聚体链基态。
返回能量、MPS、格点指标和 MPO。
"""
function compute_ground_state(;
    N_units::Int=12,
    alpha::Real=1.0,
    beta::Real=0.5,
    maxdim::Int=800,
    cutoff::Real=1e-8,
    nsweeps::Int=10,
    conserve_qns::Bool=true
)
    L = 5 * N_units
    sites = siteinds("S=1/2", L; conserve_qns)
    H = pentamer_chain_hamiltonian(sites, N_units; alpha, beta)

    # 初态：类 Neel 排列
    if iseven(L)
        state = [isodd(n) ? "Up" : "Dn" for n in 1:L]
    else
        state = [isodd(n) ? "Up" : "Dn" for n in 1:L]
        state[end] = "Up"  # 奇数长度时总 Sz 为 1/2
    end
    psi0 = random_mps(sites, state; linkdims=10)

    maxdim_schedule = _sweep_schedule(maxdim, nsweeps)

    energy, psi = dmrg(H, psi0;
        nsweeps,
        maxdim=maxdim_schedule,
        cutoff,
        outputlevel=1
    )

    return energy, psi, sites, H
end

"""
    compute_excited_state(H, psi_gs, sites; kwargs...)

用正交约束 DMRG 计算第一激发态。
自旋能隙可在 Sz=1 扇区计算。
"""
function compute_excited_state(H, psi_gs, sites;
    maxdim::Int=800,
    cutoff::Real=1e-8,
    nsweeps::Int=10,
    weight::Real=20.0,
    target_sz::Union{Nothing, Int}=nothing
)
    L = length(sites)

    if isnothing(target_sz)
        state = [isodd(n) ? "Up" : "Dn" for n in 1:L]
    else
        # 构造指定 Sz 扇区的初态
        n_up = div(L, 2) + target_sz
        state = fill("Dn", L)
        for i in 1:n_up
            state[2i-1 <= L ? 2i-1 : i] = "Up"
        end
    end

    psi0 = random_mps(sites, state; linkdims=10)
    maxdim_schedule = _sweep_schedule(maxdim, nsweeps)

    energy, psi = dmrg(H, [psi_gs], psi0;
        nsweeps,
        maxdim=maxdim_schedule,
        cutoff,
        weight,
        outputlevel=1
    )

    return energy, psi
end

function _sweep_schedule(maxdim::Int, nsweeps::Int)
    schedule = Int[]
    ramp_steps = min(5, nsweeps)
    for i in 1:nsweeps
        if i <= ramp_steps
            push!(schedule, min(maxdim, 50 * 2^(i-1)))
        else
            push!(schedule, maxdim)
        end
    end
    return schedule
end
