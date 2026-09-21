"""计算正区静态验证所需的双扇区 DMRG 与完整诊断。"""

project_root = dirname(dirname(@__DIR__))
Base.active_project() == joinpath(project_root, "Project.toml") ||
    error("必须使用 --project=. 运行")

include(joinpath(project_root, "src", "PentamerChain.jl"))
using .PentamerChain
using Dates
using LinearAlgebra
using Random
using ITensors
using ITensorMPS
using JLD2
using Printf


function parse_args()
    length(ARGS) == 11 || error(
        "用法: positive_static_cell.jl OUT ALPHA BETA N_UNITS MAXDIM NSWEEPS CUTOFF INIT_MODE STRING_MARGIN SCHMIDT_LEVELS SAVE_STATE",
    )
    return (
        outdir=abspath(ARGS[1]),
        alpha=parse(Float64, ARGS[2]),
        beta=parse(Float64, ARGS[3]),
        n_units=parse(Int, ARGS[4]),
        maxdim=parse(Int, ARGS[5]),
        nsweeps=parse(Int, ARGS[6]),
        cutoff=parse(Float64, ARGS[7]),
        init_mode=Symbol(ARGS[8]),
        string_margin=parse(Int, ARGS[9]),
        schmidt_levels=parse(Int, ARGS[10]),
        save_state=ARGS[11] == "1",
    )
end


function initial_state(total_sites::Int, target_sz::Int, mode::Symbol)
    iseven(total_sites) || error("本任务只接受偶数总格点")
    target_sz in (0, 1) || error("只支持 Sz=0 或 Sz=1")
    mode in (:center, :domain) || error("INIT_MODE 必须为 center 或 domain")
    target_sz == 1 && mode == :domain && error("domain 初态只用于 Sz=0")
    state = [isodd(site) ? "Up" : "Dn" for site in 1:total_sites]
    if mode == :domain
        span = 2 * div(total_sites, 4)
        first_site = div(total_sites - span, 2) + 1
        for site in first_site:(first_site + span - 1)
            state[site] = state[site] == "Up" ? "Dn" : "Up"
        end
        # 在活跃 J1 键附近加入成对扰动，保持总 Sz=0。
        center = total_sites ÷ 2
        for site in (center - 2, center + 3)
            state[site] = state[site] == "Up" ? "Dn" : "Up"
        end
    elseif target_sz == 1
        candidates = collect(2:2:total_sites)
        sort!(candidates; by=site -> abs(site - (total_sites + 1) / 2))
        state[first(candidates)] = "Up"
    end
    return state
end


function sweep_schedule(maxdim::Int, nsweeps::Int)
    return [sweep <= 5 ? min(maxdim, 50 * 2^(sweep - 1)) : maxdim for sweep in 1:nsweeps]
end


function configured_noise_scale()
    scale = try
        parse(Float64, get(ENV, "PENTAMER_NOISE_SCALE", "1.0"))
    catch
        error("PENTAMER_NOISE_SCALE 必须是有限正数")
    end
    isfinite(scale) && scale > 0 || error("PENTAMER_NOISE_SCALE 必须是有限正数")
    return scale
end


function run_sector(config, target_sz::Int)
    total_sites = 5 * config.n_units
    sites = siteinds("S=1/2", total_sites; conserve_qns=true)
    hamiltonian = pentamer_chain_hamiltonian(
        sites,
        config.n_units;
        alpha=config.alpha,
        beta=config.beta,
    )
    mode = target_sz == 0 ? config.init_mode : :center
    state = initial_state(total_sites, target_sz, mode)
    psi0 = if mode == :domain
        Random.seed!(0x51a5 + total_sites)
        randomMPS(sites, state, 4)
    else
        MPS(sites, state)
    end
    noise = zeros(config.nsweeps)
    # 前几步扰动可按重试需要缩放，默认保持生产值。
    noise_scale = configured_noise_scale()
    noise[1:min(3, config.nsweeps)] .= noise_scale .* [1e-6, 1e-7, 1e-8][1:min(3, config.nsweeps)]
    observer = DMRGObserver()
    started = time()
    energy, psi = dmrg(
        hamiltonian,
        psi0;
        nsweeps=config.nsweeps,
        maxdim=sweep_schedule(config.maxdim, config.nsweeps),
        cutoff=config.cutoff,
        noise,
        observer,
        outputlevel=1,
    )
    algorithm_seconds = time() - started
    energy_squared = real(inner(hamiltonian, psi, hamiltonian, psi))
    variance_raw = energy_squared - energy^2
    sweep_energies = real.(energies(observer))
    truncations = truncerrors(observer)
    # 预热误差单独留档，门槛只看最终无噪声 sweep。
    final_truncation_error = isempty(truncations) ? NaN : maximum(truncations[max(1, length(truncations) - 2):end])
    diagnostics = (
        target_sz=target_sz,
        energy=energy,
        energy_squared=energy_squared,
        variance_raw=variance_raw,
        variance=max(variance_raw, 0.0),
        total_sz=sum(real.(expect(psi, "Sz"))),
        actual_maxdim=maximum(linkdims(psi)),
        max_truncation_error=isempty(truncations) ? NaN : maximum(truncations),
        final_truncation_error=final_truncation_error,
        final_energy_change=length(sweep_energies) >= 2 ? abs(sweep_energies[end] - sweep_energies[end - 1]) : NaN,
        nsweeps_completed=length(sweep_energies),
        algorithm_seconds=algorithm_seconds,
        sweep_energies=sweep_energies,
        truncations=truncations,
    )
    return energy, psi, sites, hamiltonian, diagnostics
end


function write_sweep_history(path::String, diagnostics)
    open(path, "w") do file
        println(file, "sweep,energy,max_truncation_error")
        for sweep in eachindex(diagnostics.sweep_energies)
            truncation = sweep <= length(diagnostics.truncations) ? diagnostics.truncations[sweep] : NaN
            @printf(file, "%d,%.16e,%.16e\n", sweep, diagnostics.sweep_energies[sweep], truncation)
        end
    end
end


function schmidt_data(psi, bond::Int, level_limit::Int)
    orthogonalize!(psi, bond)
    left = bond == 1 ? (siteind(psi, bond),) : (linkind(psi, bond - 1), siteind(psi, bond))
    _, singular, _, _ = svd(psi[bond], left)
    index = first(inds(singular))
    values = Float64[]
    sectors = Float64[]
    position = 1
    for block in space(index)
        quantum_number, dimension = block
        for _ in 1:dimension
            push!(values, singular[position, position])
            push!(sectors, val(quantum_number, "Sz") / 2)
            position += 1
        end
    end
    probabilities = abs2.(values)
    order = sortperm(probabilities; rev=true)
    probabilities = probabilities[order] ./ sum(probabilities)
    sectors = sectors[order]
    return probabilities[1:min(level_limit, end)], sectors[1:min(level_limit, end)]
end


function write_measurements(config, psi, sites)
    started = time()
    string_rows = string_order_distance_profile(
        psi,
        sites,
        config.n_units;
        margin=config.string_margin,
    )
    open(joinpath(config.outdir, "string_profile.csv"), "w") do file
        println(file, "distance_units,O_mean,O_std,O_sem,n_pairs")
        for row in string_rows
            @printf(file, "%d,%.16e,%.16e,%.16e,%d\n",
                    row.distance_units, row.O_mean, row.O_std, row.O_sem, row.n_pairs)
        end
    end

    correlations = bond_spin_correlations(psi, sites)
    open(joinpath(config.outdir, "bond_correlations.csv"), "w") do file
        println(file, "bond,left_site,right_site,bond_class,correlation")
        for (bond, correlation) in enumerate(correlations)
            @printf(file, "%d,%d,%d,%d,%.16e\n", bond, bond, bond + 1, mod(bond, 5), correlation)
        end
    end

    # 用体区结构因子构造无量纲相关比值。
    total_sites = length(psi)
    margin = max(1, total_sites ÷ 10)
    selected = collect((margin + 1):(total_sites - margin))
    full_correlations = real.(correlation_matrix(psi, "Sz", "Sz"))
    magnetization = real.(expect(psi, "Sz"))
    connected = full_correlations .- magnetization * transpose(magnetization)
    window_correlations = connected[selected, selected]
    positions = Float64.(selected)
    q_pi = pi
    q_one = pi - 2pi / length(selected)
    structure_factor(q) = begin
        phases = exp.(im .* q .* positions)
        real(dot(phases, window_correlations * phases)) / length(selected)
    end
    sq_pi = structure_factor(q_pi)
    sq_one = structure_factor(q_one)
    sq_pi > 0 || error("q=pi 结构因子必须为正")
    ratio = 1 - sq_one / sq_pi
    open(joinpath(config.outdir, "structure_factor.csv"), "w") do file
        println(file, "q,Sq,window_sites")
        @printf(file, "%.16e,%.16e,%d\n", q_pi, sq_pi, length(selected))
        @printf(file, "%.16e,%.16e,%d\n", q_one, sq_one, length(selected))
    end

    center = total_sites ÷ 2
    open(joinpath(config.outdir, "schmidt_spectrum.csv"), "w") do file
        println(file, "bond,bond_class,level,schmidt_sz,probability,entanglement_energy")
        for bond in (center - 2):(center + 2)
            probabilities, sectors = schmidt_data(copy(psi), bond, config.schmidt_levels)
            for level in eachindex(probabilities)
                @printf(file, "%d,%d,%d,%.1f,%.16e,%.16e\n",
                        bond, mod(bond, 5), level, sectors[level], probabilities[level], -log(probabilities[level]))
            end
        end
    end
    return string_rows, correlations, (ratio=ratio, sq_pi=sq_pi, sq_one=sq_one,
                                       window_sites=length(selected)), time() - started
end


function write_metrics(path::String, rows)
    open(path, "w") do file
        println(file, "metric,value")
        for (key, value) in rows
            println(file, key, ",", value)
        end
    end
end


function main()
    config = parse_args()
    0.0 <= config.alpha <= 1.0 || error("禁止 alpha<0 或 alpha>1")
    0.0 <= config.beta <= 1.0 || error("beta 必须位于 [0,1]")
    iseven(config.n_units) || error("N_UNITS 必须为偶数")
    config.string_margin >= 0 || error("STRING_MARGIN 必须非负")
    config.schmidt_levels >= 4 || error("SCHMIDT_LEVELS 至少为 4")
    mkpath(config.outdir)

    started_at = now(UTC)
    energy0, psi0, sites0, hamiltonian0, diagnostics0 = run_sector(config, 0)
    energy1, psi1, sites1, hamiltonian1, diagnostics1 = run_sector(config, 1)
    write_sweep_history(joinpath(config.outdir, "sweep_history_sz0.csv"), diagnostics0)
    write_sweep_history(joinpath(config.outdir, "sweep_history_sz1.csv"), diagnostics1)
    string_rows, correlations, structure, measurement_seconds = write_measurements(config, psi0, sites0)

    total_sites = 5 * config.n_units
    noise_scale = configured_noise_scale()
    metrics = [
        "alpha" => config.alpha,
        "beta" => config.beta,
        "n_units" => config.n_units,
        "L" => total_sites,
        "energy_sz0" => energy0,
        "energy_sz1" => energy1,
        "spin_gap" => energy1 - energy0,
        "structure_factor_ratio" => structure.ratio,
        "structure_factor_pi" => structure.sq_pi,
        "structure_factor_q1" => structure.sq_one,
        "structure_factor_window_sites" => structure.window_sites,
        "variance_sz0" => diagnostics0.variance,
        "variance_per_site_sz0" => diagnostics0.variance / total_sites,
        "variance_sz1" => diagnostics1.variance,
        "variance_per_site_sz1" => diagnostics1.variance / total_sites,
        "total_sz0" => diagnostics0.total_sz,
        "total_sz1" => diagnostics1.total_sz,
        "requested_maxdim" => config.maxdim,
        "actual_maxdim_sz0" => diagnostics0.actual_maxdim,
        "actual_maxdim_sz1" => diagnostics1.actual_maxdim,
        "max_truncation_error_sz0" => diagnostics0.max_truncation_error,
        "max_truncation_error_sz1" => diagnostics1.max_truncation_error,
        "final_truncation_error_sz0" => diagnostics0.final_truncation_error,
        "final_truncation_error_sz1" => diagnostics1.final_truncation_error,
        "final_energy_change_sz0" => diagnostics0.final_energy_change,
        "final_energy_change_sz1" => diagnostics1.final_energy_change,
        "nsweeps_requested" => config.nsweeps,
        "nsweeps_completed_sz0" => diagnostics0.nsweeps_completed,
        "nsweeps_completed_sz1" => diagnostics1.nsweeps_completed,
        "cutoff" => config.cutoff,
        "noise_scale" => noise_scale,
        "threads" => Threads.nthreads(),
        "algorithm_seconds_sz0" => diagnostics0.algorithm_seconds,
        "algorithm_seconds_sz1" => diagnostics1.algorithm_seconds,
        "measurement_seconds" => measurement_seconds,
        "string_margin" => config.string_margin,
        "string_distances" => length(string_rows),
        "bond_count" => length(correlations),
        "schmidt_levels" => config.schmidt_levels,
        "init_mode_sz0" => config.init_mode,
        "init_mode_sz1" => "center",
        "started_at_utc" => Dates.format(started_at, dateformat"yyyy-mm-ddTHH:MM:SS"),
        "finished_at_utc" => Dates.format(now(UTC), dateformat"yyyy-mm-ddTHH:MM:SS"),
    ]
    write_metrics(joinpath(config.outdir, "metrics.csv"), metrics)

    if config.save_state
        jldsave(
            joinpath(config.outdir, "state_sz0.jld2");
            psi=psi0,
            sites=sites0,
            energy=energy0,
            alpha=config.alpha,
            beta=config.beta,
            n_units=config.n_units,
        )
    end
    println("POSITIVE_STATIC_SUCCESS outdir=$(config.outdir)")
end


main()
