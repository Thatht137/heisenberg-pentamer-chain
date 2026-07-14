"""
五聚体链的序参量：弦序参量和自旋能隙。

弦序参量沿用 Li 等文献的约定，其中 sigma_z = 2Sz。
"""

"""
    string_order_parameter(psi, sites, N_units; margin=3)

计算五聚体链的 z 方向弦序参量。
两端各丢弃 margin 个单元以减小边界效应。
"""
function string_order_parameter(psi, sites, N_units::Int; margin::Int=3)
    L = length(sites)
    @assert L == 5 * N_units

    # 自动缩减 margin 以适应短链
    while margin > 0 && (N_units - 2 * margin) < 2
        margin -= 1
    end
    if margin == 0 && N_units < 2
        error("Chain too short: need at least N_units=2 for string order parameter")
    end

    n_start = margin + 1
    n_end = N_units - margin

    # 优先取体区内最大距离
    max_sep = n_end - n_start
    values = Float64[]

    for n in n_start:(n_end - max_sep)
        np = n + max_sep
        site_i = 5 * n              # 第 n 个单元末端
        site_j = 5 * (np - 1) + 1   # 第 np 个单元起点

        val = _string_correlator(psi, sites, site_i, site_j)
        push!(values, val)
    end

    if isempty(values)
        # 若最大距离无可用点，则退到较短距离
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

    return sum(values) / length(values)
end

"""
    string_correlator_units(psi, sites, unit_i, unit_j)

计算两个五聚体单元边界之间的弦关联。
"""
function string_correlator_units(psi, sites, unit_i::Int, unit_j::Int)
    N_units = div(length(sites), 5)
    @assert length(sites) == 5 * N_units
    @assert 1 <= unit_i < unit_j <= N_units

    site_i = 5 * unit_i
    site_j = 5 * (unit_j - 1) + 1
    return _string_correlator(psi, sites, site_i, site_j)
end

"""
    string_order_distance_samples(psi, sites, N_units; margin=3, max_distance=nothing)

逐个保存体区内所有端点对的弦关联。
"""
function string_order_distance_samples(
    psi,
    sites,
    N_units::Int;
    margin::Int=3,
    max_distance::Union{Nothing, Int}=nothing,
)
    @assert length(sites) == 5 * N_units
    @assert N_units >= 2
    @assert margin >= 0

    while margin > 0 && N_units - 2 * margin < 2
        margin -= 1
    end

    unit_start = margin + 1
    unit_end = N_units - margin
    available_distance = unit_end - unit_start
    available_distance >= 1 || error("No unit-cell pair available")

    distance_limit = isnothing(max_distance) ?
        available_distance : min(max_distance, available_distance)
    distance_limit >= 1 || error("max_distance must be positive")

    samples = NamedTuple[]
    for distance in 1:distance_limit
        for unit_i in unit_start:(unit_end - distance)
            unit_j = unit_i + distance
            push!(samples, (
                distance_units=distance,
                unit_i=unit_i,
                unit_j=unit_j,
                O_str=string_correlator_units(
                    psi, sites, unit_i, unit_j),
            ))
        end
    end

    return samples
end

"""
    string_order_distance_profile(psi, sites, N_units; margin=2, max_distance=nothing)

计算体区内弦序随位胞距离的变化。
"""
function string_order_distance_profile(
    psi,
    sites,
    N_units::Int;
    margin::Int=2,
    max_distance::Union{Nothing, Int}=nothing,
)
    @assert length(sites) == 5 * N_units
    @assert N_units >= 2
    @assert margin >= 0

    while margin > 0 && N_units - 2 * margin < 2
        margin -= 1
    end

    unit_start = margin + 1
    unit_end = N_units - margin
    available_distance = unit_end - unit_start
    available_distance >= 1 || error("No unit-cell pair available")

    distance_limit = isnothing(max_distance) ?
        available_distance : min(max_distance, available_distance)
    distance_limit >= 1 || error("max_distance must be positive")

    profile = NamedTuple[]
    for distance in 1:distance_limit
        values = Float64[]
        for unit_i in unit_start:(unit_end - distance)
            unit_j = unit_i + distance
            push!(values, string_correlator_units(
                psi, sites, unit_i, unit_j))
        end

        count = length(values)
        mean_value = sum(values) / count
        variance = sum((value - mean_value)^2 for value in values) / count
        std_value = sqrt(max(variance, 0.0))

        push!(profile, (
            distance_units=distance,
            O_mean=mean_value,
            O_std=std_value,
            O_sem=std_value / sqrt(count),
            n_pairs=count,
        ))
    end

    return profile
end

"""
用 ITensors OpSum 计算多点 Sz 乘积。
"""
function _string_correlator(psi, sites, i::Int, j::Int)
    N_mid = j - i - 1
    coeff = -(2.0)^N_mid

    os = OpSum()
    args = Any[coeff]
    for k in i:j
        push!(args, "Sz")
        push!(args, k)
    end
    os += Tuple(args)

    O = MPO(os, sites)
    return real(inner(psi', O, psi))
end

"""
    bond_spin_correlations(psi, sites)

计算所有最近邻键的自旋关联。
"""
function bond_spin_correlations(psi, sites)
    correlations = Float64[]
    for site in 1:(length(sites) - 1)
        os = OpSum()
        os += 1.0, "Sz", site, "Sz", site + 1
        os += 0.5, "S+", site, "S-", site + 1
        os += 0.5, "S-", site, "S+", site + 1
        operator = MPO(os, sites)
        push!(correlations, real(inner(psi', operator, psi)))
    end
    return correlations
end

"""
    bipartite_entropy(psi::MPS, bond::Int)

计算 MPS 在给定 bond 处的双分区 von Neumann 纠缠熵（单位：nats）。
bond=L÷2 对应链中央切分。
bond=b 表示在格点 b 和 b+1 之间切分。
"""
function bipartite_entropy(psi::MPS, bond::Int)
    L = length(psi)
    @assert 1 <= bond < L "bond must be in 1:(L-1), got $bond for L=$L"

    orthogonalize!(psi, bond)

    # 构造左侧指标（bond=1 时没有左 link）
    if bond == 1
        left_inds = (siteind(psi, bond),)
    else
        left_inds = (linkind(psi, bond-1), siteind(psi, bond))
    end

    U, S, V, spec = svd(psi[bond], left_inds)

    return ITensors.entropy(spec)  # nats
end

"""
    spin_gap(; N_units=12, alpha=1.0, beta=0.5, kwargs...)

计算自旋能隙：E(Sz=1) - E(Sz=0)。
要求总格点数为偶数。
"""
function spin_gap(; N_units::Int=12, alpha::Real=1.0, beta::Real=0.5,
                  maxdim::Int=400, cutoff::Real=1e-8, nsweeps::Int=8)
    L = 5 * N_units
    @assert iseven(L) "spin_gap requires even L (even N_units for pentamer)"

    # Sz=0 扇区基态
    sites = siteinds("S=1/2", L; conserve_qns=true)
    H = pentamer_chain_hamiltonian(sites, N_units; alpha, beta)

    state_0 = [isodd(n) ? "Up" : "Dn" for n in 1:L]
    psi0 = random_mps(sites, state_0; linkdims=10)
    schedule = _sweep_schedule(maxdim, nsweeps)
    E0, _ = dmrg(H, psi0; nsweeps, maxdim=schedule, cutoff, outputlevel=0)

    # Sz=1 扇区最低态
    state_1 = copy(state_0)
    state_1[2] = "Up"  # 增加一个向上自旋
    psi1 = random_mps(sites, state_1; linkdims=10)
    E1, _ = dmrg(H, psi1; nsweeps, maxdim=schedule, cutoff, outputlevel=0)

    return E1 - E0
end
