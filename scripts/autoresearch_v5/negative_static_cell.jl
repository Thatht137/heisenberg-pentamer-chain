"""计算负 alpha 静态相图所需的双扇区 DMRG 与全动量诊断。"""

project_root = dirname(dirname(@__DIR__))
Base.active_project() == joinpath(project_root, "Project.toml") || error("必须使用 --project=. 运行")

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
    length(ARGS) in (12, 14, 15, 16) || error("用法: negative_static_cell.jl OUT ALPHA BETA N_UNITS MAXDIM NSWEEPS CUTOFF INIT_MODE STRING_MARGIN SCHMIDT_LEVELS Q_COUNT SAVE_STATE [NOISE_PROFILE RANDOM_SEED ENRICHED [EIGSOLVE_KRYLOVDIM]]")
    return (
        outdir=abspath(ARGS[1]), alpha=parse(Float64, ARGS[2]), beta=parse(Float64, ARGS[3]),
        n_units=parse(Int, ARGS[4]), maxdim=parse(Int, ARGS[5]), nsweeps=parse(Int, ARGS[6]),
        cutoff=parse(Float64, ARGS[7]), init_mode=Symbol(ARGS[8]), string_margin=parse(Int, ARGS[9]),
        schmidt_levels=parse(Int, ARGS[10]), q_count=parse(Int, ARGS[11]), save_state=ARGS[12] == "1",
        noise_profile=length(ARGS) >= 14 ? Symbol(ARGS[13]) : :legacy,
        random_seed=length(ARGS) >= 14 ? parse(Int, ARGS[14]) : 20260811,
        enriched_diagnostics=length(ARGS) >= 15 && ARGS[15] == "1",
        eigsolve_krylovdim=length(ARGS) >= 16 ? parse_krylovdim(ARGS[16]) : 3,
        eigsolve_maxiter=1,
        eigsolve_tol=1.0e-14,
    )
end

function parse_krylovdim(text::AbstractString)
    occursin(r"^[0-9]+$", text) || error("EIGSOLVE_KRYLOVDIM 必须是十进制整数")
    value = try
        parse(Int, text)
    catch
        error("EIGSOLVE_KRYLOVDIM 不是有效整数")
    end
    3 <= value <= 32 || error("EIGSOLVE_KRYLOVDIM 必须位于 [3,32]")
    return value
end

function bond_product(psi, sites, first_bond::Int, second_bond::Int)
    left, right = minmax(first_bond, second_bond)
    right > left + 1 || error("键乘积要求两键不重叠")
    terms = ((1.0, "Sz", "Sz"), (0.5, "S+", "S-"), (0.5, "S-", "S+"))
    os = OpSum()
    for (c1, a1, a2) in terms, (c2, b1, b2) in terms
        args = Any[c1 * c2, a1, left, a2, left + 1, b1, right, b2, right + 1]
        os += Tuple(args)
    end
    return real(inner(psi', MPO(os, sites), psi))
end

function write_enriched_measurements(config, psi, sites, correlations)
    total_sites = length(psi)
    open(joinpath(config.outdir, "entropy_profile_full.csv"), "w") do file
        println(file, "bond,bond_class,log_chord,entropy")
        for bond in 1:(total_sites - 1)
            chord = (2total_sites / pi) * sin(pi * bond / total_sites)
            entropy = bipartite_entropy(copy(psi), bond)
            @printf(file, "%d,%d,%.16e,%.16e\n", bond, mod(bond, 5), log(chord), entropy)
        end
    end
    open(joinpath(config.outdir, "bond_bond_connected.csv"), "w") do file
        println(file, "bond_class,reference_bond,target_bond,distance_units,connected")
        for bond_class in (0, 1)
            candidates = [bond for bond in 1:(total_sites - 1) if mod(bond, 5) == bond_class]
            reference = candidates[argmin(abs.(candidates .- total_sites ÷ 2))]
            for target in candidates
                abs(target - reference) >= 5 || continue
                connected = bond_product(psi, sites, reference, target) - correlations[reference] * correlations[target]
                @printf(file, "%d,%d,%d,%.1f,%.16e\n", bond_class, reference, target, abs(target-reference)/5, connected)
            end
        end
    end
end

function initial_state(total_sites::Int, target_sz::Int, mode::Symbol)
    iseven(total_sites) || error("本任务只接受偶数总格点")
    target_sz in (0, 1) || error("只支持 Sz=0 或 Sz=1")
    mode in (:center, :center_random, :domain, :ferro_j2) || error("INIT_MODE 非法")
    target_sz == 1 && mode != :center && error("随机/畴初态只用于 Sz=0")
    state = [isodd(site) ? "Up" : "Dn" for site in 1:total_sites]
    if mode == :domain
        span = 2 * div(total_sites, 4)
        first_site = div(total_sites - span, 2) + 1
        for site in first_site:(first_site + span - 1)
            state[site] = state[site] == "Up" ? "Dn" : "Up"
        end
        center = total_sites ÷ 2
        for site in (center - 2, center + 3)
            state[site] = state[site] == "Up" ? "Dn" : "Up"
        end
    elseif mode == :ferro_j2
        # 相邻胞取反，使两条铁磁 J2 键对齐且总 Sz=0。
        for unit in 1:div(total_sites, 5)
            up = isodd(unit)
            for offset in (0, 1, 3, 4)
                state[5 * (unit - 1) + offset + 1] = up ? "Up" : "Dn"
            end
            state[5 * (unit - 1) + 3] = up ? "Dn" : "Up"
        end
    elseif target_sz == 1
        candidates = collect(2:2:total_sites)
        sort!(candidates; by=site -> abs(site - (total_sites + 1) / 2))
        state[first(candidates)] = "Up"
    end
    return state
end

function initial_seed(base::Int, total_sites::Int, mode::Symbol)
    offsets = Dict(:center_random => 101, :domain => 211, :ferro_j2 => 307)
    return base + 17 * total_sites + offsets[mode]
end

sweep_schedule(maxdim::Int, nsweeps::Int) = [sweep <= 5 ? min(maxdim, 50 * 2^(sweep - 1)) : maxdim for sweep in 1:nsweeps]

function configured_noise_scale()
    scale = try parse(Float64, get(ENV, "PENTAMER_NOISE_SCALE", "1.0")) catch; error("PENTAMER_NOISE_SCALE 必须是有限正数") end
    isfinite(scale) && scale > 0 || error("PENTAMER_NOISE_SCALE 必须是有限正数")
    return scale
end

function noise_schedule(profile::Symbol, nsweeps::Int)
    profile in (:legacy, :repair) || error("NOISE_PROFILE 必须为 legacy 或 repair")
    noise = zeros(nsweeps)
    values = profile == :legacy ? [1e-6, 1e-7, 1e-8] : [1e-7, 1e-7, 5e-8, 2e-8, 1e-8, 5e-9, 1e-9, 1e-10]
    noise[1:min(length(values), nsweeps)] .= configured_noise_scale() .* values[1:min(length(values), nsweeps)]
    return noise
end

function run_sector(config, target_sz::Int)
    total_sites = 5 * config.n_units
    sites = siteinds("S=1/2", total_sites; conserve_qns=true)
    hamiltonian = pentamer_chain_hamiltonian(sites, config.n_units; alpha=config.alpha, beta=config.beta)
    mode = target_sz == 0 ? config.init_mode : :center
    state = initial_state(total_sites, target_sz, mode)
    seed = mode in (:center_random, :domain, :ferro_j2) ? initial_seed(config.random_seed, total_sites, mode) : -1
    psi0 = if seed >= 0
        Random.seed!(seed)
        randomMPS(sites, state, 4)
    else
        MPS(sites, state)
    end
    noise = noise_schedule(config.noise_profile, config.nsweeps)
    observer = DMRGObserver()
    started = time()
    energy, psi = dmrg(hamiltonian, psi0; nsweeps=config.nsweeps, maxdim=sweep_schedule(config.maxdim, config.nsweeps), cutoff=config.cutoff, noise, observer, eigsolve_krylovdim=config.eigsolve_krylovdim, eigsolve_maxiter=config.eigsolve_maxiter, eigsolve_tol=config.eigsolve_tol, outputlevel=1)
    energy_squared = real(inner(hamiltonian, psi, hamiltonian, psi))
    sweep_energies = real.(energies(observer))
    truncations = truncerrors(observer)
    diagnostics = (
        target_sz=target_sz, energy=energy, energy_squared=energy_squared,
        variance=max(energy_squared - energy^2, 0.0), state_norm=norm(psi), total_sz=sum(real.(expect(psi, "Sz"))),
        actual_maxdim=maximum(linkdims(psi)), max_truncation_error=isempty(truncations) ? NaN : maximum(truncations),
        final_truncation_error=isempty(truncations) ? NaN : maximum(truncations[max(1, length(truncations)-2):end]),
        final_energy_change=length(sweep_energies) >= 2 ? abs(sweep_energies[end]-sweep_energies[end-1]) : NaN,
        nsweeps_completed=length(sweep_energies), algorithm_seconds=time()-started, initial_seed=seed,
        sweep_energies=sweep_energies, truncations=truncations,
    )
    return energy, psi, sites, diagnostics
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
    index = first(inds(singular)); values = Float64[]; sectors = Float64[]; position = 1
    for block in space(index)
        quantum_number, dimension = block
        for _ in 1:dimension
            push!(values, singular[position, position]); push!(sectors, val(quantum_number, "Sz") / 2); position += 1
        end
    end
    probabilities = abs2.(values); order = sortperm(probabilities; rev=true)
    probabilities = probabilities[order] ./ sum(probabilities); sectors = sectors[order]
    return probabilities[1:min(level_limit, end)], sectors[1:min(level_limit, end)]
end

function nearest_index(values, target)
    return argmin(abs.(values .- clamp(target, first(values), last(values))))
end

function write_measurements(config, psi, sites)
    started = time()
    string_rows = string_order_distance_profile(psi, sites, config.n_units; margin=config.string_margin)
    open(joinpath(config.outdir, "string_profile.csv"), "w") do file
        println(file, "distance_units,O_mean,O_std,O_sem,n_pairs")
        for row in string_rows
            @printf(file, "%d,%.16e,%.16e,%.16e,%d\n", row.distance_units, row.O_mean, row.O_std, row.O_sem, row.n_pairs)
        end
    end
    correlations = bond_spin_correlations(psi, sites)
    open(joinpath(config.outdir, "bond_correlations.csv"), "w") do file
        println(file, "bond,left_site,right_site,bond_class,correlation")
        for (bond, correlation) in enumerate(correlations)
            @printf(file, "%d,%d,%d,%d,%.16e\n", bond, bond, bond + 1, mod(bond, 5), correlation)
        end
    end
    total_sites = length(psi); margin = max(1, total_sites ÷ 10)
    selected = collect((margin + 1):(total_sites - margin)); positions = Float64.(selected)
    full_correlations = real.(correlation_matrix(psi, "Sz", "Sz")); magnetization = real.(expect(psi, "Sz"))
    connected = full_correlations .- magnetization * transpose(magnetization)
    window_correlations = connected[selected, selected]
    structure_factor(q) = begin
        phases = exp.(im .* q .* positions)
        real(dot(phases, window_correlations * phases)) / length(selected)
    end
    qs = collect(range(0.0, pi; length=config.q_count)); sqs = [structure_factor(q) for q in qs]
    peak_index = argmax(sqs); peak_q = qs[peak_index]; peak_sq = sqs[peak_index]
    peak_sq > 0 || error("主峰结构因子必须为正")
    offset = 2pi / length(selected)
    if peak_index == 1
        peak_neighbor = sqs[nearest_index(qs, peak_q + offset)]
        peak_ratio = 1 - peak_neighbor / peak_sq
        peak_ratio_mode = "one_sided_right"
    elseif peak_index == length(qs)
        peak_neighbor = sqs[nearest_index(qs, peak_q - offset)]
        peak_ratio = 1 - peak_neighbor / peak_sq
        peak_ratio_mode = "one_sided_left"
    else
        left_sq = sqs[nearest_index(qs, peak_q - offset)]
        right_sq = sqs[nearest_index(qs, peak_q + offset)]
        peak_ratio = 1 - (left_sq + right_sq) / (2peak_sq)
        peak_ratio_mode = "symmetric"
    end
    pi_index = nearest_index(qs, pi); q1_index = nearest_index(qs, pi - offset)
    sq_pi = sqs[pi_index]; sq_one = sqs[q1_index]; sq_pi > 0 || error("q=pi 结构因子必须为正")
    pi_ratio = 1 - sq_one / sq_pi
    open(joinpath(config.outdir, "structure_factor_fullq.csv"), "w") do file
        println(file, "q,q_over_pi,Sq,window_sites")
        for index in eachindex(qs)
            @printf(file, "%.16e,%.16e,%.16e,%d\n", qs[index], qs[index]/pi, sqs[index], length(selected))
        end
    end
    center = total_sites ÷ 2
    open(joinpath(config.outdir, "schmidt_spectrum.csv"), "w") do file
        println(file, "bond,bond_class,level,schmidt_sz,probability,entanglement_energy")
        for bond in (center - 2):(center + 2)
            probabilities, sectors = schmidt_data(copy(psi), bond, config.schmidt_levels)
            for level in eachindex(probabilities)
                @printf(file, "%d,%d,%d,%.1f,%.16e,%.16e\n", bond, mod(bond, 5), level, sectors[level], probabilities[level], -log(probabilities[level]))
            end
        end
    end
    return string_rows, correlations, (pi_ratio=pi_ratio, sq_pi=sq_pi, sq_one=sq_one, window_sites=length(selected), q_count=config.q_count, peak_q=peak_q, peak_q_over_pi=peak_q/pi, peak_sq=peak_sq, peak_ratio=peak_ratio, peak_ratio_mode=peak_ratio_mode), time()-started
end

function write_metrics(path::String, rows)
    open(path, "w") do file
        println(file, "metric,value")
        for (key, value) in rows; println(file, key, ",", value); end
    end
end

function main()
    config = parse_args()
    -1.0 <= config.alpha < 0.0 || error("alpha 必须位于 [-1,0)")
    0.0 <= config.beta <= 1.0 || error("beta 必须位于 [0,1]")
    iseven(config.n_units) || error("N_UNITS 必须为偶数")
    config.string_margin >= 0 || error("STRING_MARGIN 必须非负")
    config.schmidt_levels >= 4 || error("SCHMIDT_LEVELS 至少为 4")
    config.q_count >= 401 || error("Q_COUNT 至少为 401")
    config.noise_profile in (:legacy, :repair) || error("NOISE_PROFILE 非法")
    config.random_seed >= 0 || error("RANDOM_SEED 必须非负")
    mkpath(config.outdir); started_at = now(UTC)
    energy0, psi0, sites0, diagnostics0 = run_sector(config, 0)
    energy1, psi1, sites1, diagnostics1 = run_sector(config, 1)
    write_sweep_history(joinpath(config.outdir, "sweep_history_sz0.csv"), diagnostics0)
    write_sweep_history(joinpath(config.outdir, "sweep_history_sz1.csv"), diagnostics1)
    string_rows, correlations, structure, measurement_seconds = write_measurements(config, psi0, sites0)
    enriched_seconds = 0.0
    if config.enriched_diagnostics
        enriched_started = time()
        write_enriched_measurements(config, psi0, sites0, correlations)
        enriched_seconds = time() - enriched_started
    end
    total_sites = 5 * config.n_units
    metrics = [
        "alpha"=>config.alpha, "beta"=>config.beta, "n_units"=>config.n_units, "L"=>total_sites,
        "energy_sz0"=>energy0, "energy_sz1"=>energy1, "spin_gap"=>energy1-energy0,
        "structure_factor_ratio"=>structure.pi_ratio, "structure_factor_pi"=>structure.sq_pi, "structure_factor_q1"=>structure.sq_one,
        "structure_factor_window_sites"=>structure.window_sites, "structure_factor_q_count"=>structure.q_count,
        "structure_factor_peak_q"=>structure.peak_q, "structure_factor_peak_q_over_pi"=>structure.peak_q_over_pi,
        "structure_factor_peak"=>structure.peak_sq, "structure_factor_peak_ratio"=>structure.peak_ratio,
        "dominant_structure_factor_ratio"=>structure.peak_ratio, "dominant_structure_factor_ratio_mode"=>structure.peak_ratio_mode,
        "variance_sz0"=>diagnostics0.variance, "variance_per_site_sz0"=>diagnostics0.variance/total_sites,
        "variance_sz1"=>diagnostics1.variance, "variance_per_site_sz1"=>diagnostics1.variance/total_sites,
        "state_norm_sz0"=>diagnostics0.state_norm, "state_norm_sz1"=>diagnostics1.state_norm,
        "total_sz0"=>diagnostics0.total_sz, "total_sz1"=>diagnostics1.total_sz, "requested_maxdim"=>config.maxdim,
        "actual_maxdim_sz0"=>diagnostics0.actual_maxdim, "actual_maxdim_sz1"=>diagnostics1.actual_maxdim,
        "max_truncation_error_sz0"=>diagnostics0.max_truncation_error, "max_truncation_error_sz1"=>diagnostics1.max_truncation_error,
        "final_truncation_error_sz0"=>diagnostics0.final_truncation_error, "final_truncation_error_sz1"=>diagnostics1.final_truncation_error,
        "final_energy_change_sz0"=>diagnostics0.final_energy_change, "final_energy_change_sz1"=>diagnostics1.final_energy_change,
        "nsweeps_requested"=>config.nsweeps, "nsweeps_completed_sz0"=>diagnostics0.nsweeps_completed, "nsweeps_completed_sz1"=>diagnostics1.nsweeps_completed,
        "cutoff"=>config.cutoff, "noise_scale"=>configured_noise_scale(), "noise_profile"=>config.noise_profile,
        "eigsolve_krylovdim"=>config.eigsolve_krylovdim, "eigsolve_maxiter"=>config.eigsolve_maxiter, "eigsolve_tol"=>config.eigsolve_tol,
        "random_seed_base"=>config.random_seed, "initial_seed_sz0"=>diagnostics0.initial_seed,
        "initial_seed_sz1"=>diagnostics1.initial_seed, "threads"=>Threads.nthreads(),
        "algorithm_seconds_sz0"=>diagnostics0.algorithm_seconds, "algorithm_seconds_sz1"=>diagnostics1.algorithm_seconds,
        "measurement_seconds"=>measurement_seconds, "string_margin"=>config.string_margin, "string_distances"=>length(string_rows),
        "enriched_diagnostics"=>config.enriched_diagnostics, "enriched_seconds"=>enriched_seconds,
        "bond_count"=>length(correlations), "schmidt_levels"=>config.schmidt_levels, "init_mode_sz0"=>config.init_mode,
        "init_mode_sz1"=>"center", "started_at_utc"=>Dates.format(started_at, dateformat"yyyy-mm-ddTHH:MM:SS"),
        "finished_at_utc"=>Dates.format(now(UTC), dateformat"yyyy-mm-ddTHH:MM:SS"),
    ]
    write_metrics(joinpath(config.outdir, "metrics.csv"), metrics)
    if config.save_state
        jldsave(joinpath(config.outdir, "state_sz0.jld2"); psi=psi0, sites=sites0, energy=energy0, alpha=config.alpha, beta=config.beta, n_units=config.n_units)
    end
    println("NEGATIVE_STATIC_SUCCESS outdir=$(config.outdir)")
end

if abspath(PROGRAM_FILE) == @__FILE__
    main()
end
