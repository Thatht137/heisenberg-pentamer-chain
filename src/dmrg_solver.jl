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

"""
    compute_ground_state_hires(; N_units, alpha, beta, maxdim, cutoff, nsweeps)

高精度确定性 DMRG 基态计算，用于有限尺寸标度和加密相图。
与 compute_ground_state 的关键差异：
- 确定性 Néel 初态（MPS 产品态，无随机扰动）
- 早期噪声调度（前 7 步加噪声逃局部极小）
- 严格的 bond dim ramp（前 6 步几何增长）
返回 (energy, psi, sites)。
"""
function compute_ground_state_hires(;
    N_units::Int,
    alpha::Real,
    beta::Real,
    maxdim::Int,
    cutoff::Real,
    nsweeps::Int,
    conserve_qns::Bool=true
)
    L = 5 * N_units
    sites = siteinds("S=1/2", L; conserve_qns)
    H = pentamer_chain_hamiltonian(sites, N_units; alpha, beta)

    # 确定性 Néel 初态（奇数长度尾部修正使总 Sz=1/2）
    state = [isodd(n) ? "Up" : "Dn" for n in 1:L]
    if isodd(L)
        state[end] = "Up"
    end
    psi0 = MPS(sites, state)  # 确定性产品态，无随机扰动

    # bond dim schedule：前 6 个 sweep 几何增长，后续保持满值
    schedule = Int[]
    for i in 1:nsweeps
        if i <= 6
            push!(schedule, min(maxdim, 50 * 2^(i-1)))
        else
            push!(schedule, maxdim)
        end
    end

    # 早期加噪声逃局部极小，后续关闭
    noise_schedule = zeros(nsweeps)
    if nsweeps >= 7
        noise_schedule[1:min(3, nsweeps)] .= [1e-6, 1e-7, 1e-8][1:min(3, nsweeps)]
    end

    energy, psi = dmrg(H, psi0;
        nsweeps,
        maxdim=schedule,
        cutoff,
        noise=noise_schedule,
        outputlevel=1,
    )

    return energy, psi, sites
end

"""
    compute_sector_ground_state_hires(; N_units, alpha, beta, target_sz, ...)

在指定总 Sz 扇区中计算高精度基态。
"""
function compute_sector_ground_state_hires(;
    N_units::Int,
    alpha::Real,
    beta::Real,
    target_sz::Int,
    maxdim::Int,
    cutoff::Real,
    nsweeps::Int,
    initial_mode::Symbol=:center,
)
    L = 5 * N_units
    @assert iseven(L)
    @assert abs(target_sz) <= div(L, 2)

    sites = siteinds("S=1/2", L; conserve_qns=true)
    H = pentamer_chain_hamiltonian(sites, N_units; alpha, beta)
    state = [isodd(site) ? "Up" : "Dn" for site in 1:L]
    initial_mode in (:center, :left, :right) ||
        error("initial_mode 必须为 :center、:left 或 :right")

    if target_sz > 0
        candidates = collect(2:2:L)
        if initial_mode == :center
            sort!(candidates; by=site -> abs(site - (L + 1) / 2))
        elseif initial_mode == :right
            reverse!(candidates)
        end
        for site in candidates[1:target_sz]
            state[site] = "Up"
        end
    elseif target_sz < 0
        candidates = collect(1:2:L)
        if initial_mode == :center
            sort!(candidates; by=site -> abs(site - (L + 1) / 2))
        elseif initial_mode == :right
            reverse!(candidates)
        end
        for site in candidates[1:(-target_sz)]
            state[site] = "Dn"
        end
    end

    psi0 = MPS(sites, state)
    schedule = _sweep_schedule(maxdim, nsweeps)
    noise_schedule = zeros(nsweeps)
    noise_schedule[1:min(3, nsweeps)] .=
        [1e-6, 1e-7, 1e-8][1:min(3, nsweeps)]

    energy, psi = dmrg(
        H,
        psi0;
        nsweeps,
        maxdim=schedule,
        cutoff,
        noise=noise_schedule,
        outputlevel=1,
    )

    return energy, psi, sites
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
