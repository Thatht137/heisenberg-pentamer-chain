"""用动量源自相关计算严格 q=pi 动态结构因子。"""

include(joinpath(dirname(dirname(@__DIR__)), "src", "PentamerChain.jl"))
using .PentamerChain
using Dates
using ITensors
using ITensorMPS
using JLD2
using Printf


function parse_config()
    length(ARGS) == 16 || error(
        "参数: OUTDIR ALPHA BETA N_UNITS ETA OMEGA_MIN OMEGA_MAX OMEGA_STEP " *
        "TSTEP N_STEPS DMRG_MAXDIM TEBD_MAXDIM NSWEEPS DMRG_CUTOFF " *
        "TEBD_CUTOFF CHECKPOINT_INTERVAL"
    )
    return (
        outdir=abspath(ARGS[1]),
        alpha=parse(Float64, ARGS[2]),
        beta=parse(Float64, ARGS[3]),
        n_units=parse(Int, ARGS[4]),
        eta=parse(Float64, ARGS[5]),
        omega_min=parse(Float64, ARGS[6]),
        omega_max=parse(Float64, ARGS[7]),
        omega_step=parse(Float64, ARGS[8]),
        tstep=parse(Float64, ARGS[9]),
        n_steps=parse(Int, ARGS[10]),
        dmrg_maxdim=parse(Int, ARGS[11]),
        tebd_maxdim=parse(Int, ARGS[12]),
        nsweeps=parse(Int, ARGS[13]),
        dmrg_cutoff=parse(Float64, ARGS[14]),
        tebd_cutoff=parse(Float64, ARGS[15]),
        checkpoint_interval=parse(Int, ARGS[16]),
    )
end


function sweep_schedule(maxdim::Int, nsweeps::Int)
    return [min(maxdim, 20 * 2^(min(sweep - 1, 5))) for sweep in 1:nsweeps]
end


function pentamer_bonds(n_units::Int; alpha::Real, beta::Real)
    bonds = Tuple{Int, Int, Float64}[]
    for unit in 1:n_units
        first = 5 * (unit - 1) + 1
        append!(bonds, [
            (first, first + 1, Float64(alpha)),
            (first + 1, first + 2, 1.0),
            (first + 2, first + 3, 1.0),
            (first + 3, first + 4, Float64(alpha)),
        ])
        unit < n_units && push!(bonds, (first + 4, first + 5, Float64(beta)))
    end
    return bonds
end


function heisenberg_gate(sites, left::Int, right::Int, coupling::Real, tstep::Real)
    s1, s2 = sites[left], sites[right]
    bond = coupling * (
        op("Sz", s1) * op("Sz", s2) +
        0.5 * op("S+", s1) * op("S-", s2) +
        0.5 * op("S-", s1) * op("S+", s2)
    )
    return exp(-im * tstep / 2 * bond)
end


function tebd_gates(sites, n_units::Int; alpha::Real, beta::Real, tstep::Real)
    gates = ITensor[
        heisenberg_gate(sites, left, right, coupling, tstep)
        for (left, right, coupling) in pentamer_bonds(n_units; alpha, beta)
    ]
    append!(gates, reverse(gates))
    return gates
end


function momentum_source(ground, sites; maxdim::Int, cutoff::Real)
    source = nothing
    normalization = sqrt(length(sites))
    for site in eachindex(sites)
        term = copy(ground)
        term[site] = noprime(term[site] * op("Sz", sites[site]))
        term *= exp(im * pi * site) / normalization
        source = isnothing(source) ? term : add(source, term; maxdim, cutoff)
    end
    return source
end


function atomic_jldsave(path::String; kwargs...)
    temporary = path * ".tmp"
    jldsave(temporary; kwargs...)
    mv(temporary, path; force=true)
end


function omega_grid(first::Real, last::Real, step::Real)
    count = round(Int, (last - first) / step)
    isapprox(first + count * step, last; atol=1e-12, rtol=1e-12) ||
        error("omega 网格不能整除")
    return collect(range(Float64(first), Float64(last); length=count + 1))
end


function fourier_spectrum(times, correlations, omegas, eta::Real)
    length(times) == length(correlations) || error("时间和相关函数长度不一致")
    length(times) >= 2 || error("至少需要两个时间点")
    tstep = times[2] - times[1]
    spectrum = Float64[]
    for omega in omegas
        values = exp.((im * omega - eta) .* times) .* correlations
        integral = tstep * (sum(values) - 0.5 * values[1] - 0.5 * values[end])
        push!(spectrum, real(integral) / pi)
    end
    return spectrum
end


function write_outputs(
    config,
    times,
    correlations,
    norms,
    linkdims_history,
    omegas,
    spectrum,
    metrics,
    source,
)
    open(joinpath(config.outdir, "correlation.csv"), "w") do file
        println(file, "time,real_corr,imag_corr,norm,linkdim")
        for index in eachindex(times)
            @printf(
                file,
                "%.12g,%.16e,%.16e,%.16e,%d\n",
                times[index],
                real(correlations[index]),
                imag(correlations[index]),
                norms[index],
                linkdims_history[index],
            )
        end
    end
    open(joinpath(config.outdir, "spectrum.csv"), "w") do file
        println(file, "q_over_pi,omega,intensity")
        for index in eachindex(omegas)
            @printf(file, "1,%.12g,%.16e\n", omegas[index], spectrum[index])
        end
    end
    open(joinpath(config.outdir, "metrics.csv"), "w") do file
        println(file, "metric,value")
        for (key, value) in metrics
            println(file, key, ',', value)
        end
    end
    jldsave(
        joinpath(config.outdir, "correlation.jld2");
        times,
        correlations,
        norms,
        linkdims_history,
        source_norm_squared=real(inner(source, source)),
    )
    jldsave(joinpath(config.outdir, "spectrum.jld2"); omegas, spectrum, eta=config.eta)
end


function main()
    config = parse_config()
    0.0 <= config.alpha <= 1.0 || error("alpha 必须位于 [0,1]")
    0.0 <= config.beta <= 1.0 || error("beta 必须位于 [0,1]")
    config.n_units > 0 && iseven(config.n_units) || error("n_units 必须为正偶数")
    min(config.eta, config.omega_step, config.tstep, config.dmrg_cutoff, config.tebd_cutoff) > 0 ||
        error("步长、展宽和截断必须为正数")
    min(config.n_steps, config.dmrg_maxdim, config.tebd_maxdim, config.nsweeps) > 0 ||
        error("计算规模必须为正整数")
    config.checkpoint_interval > 0 || error("checkpoint_interval 必须为正整数")
    stop_after_step = parse(Int, get(ENV, "PENTAMER_STOP_AFTER_STEP", "0"))
    0 <= stop_after_step < config.n_steps || error("受控停止步必须位于 [0,n_steps)")
    mkpath(config.outdir)
    final_path = joinpath(config.outdir, "spectrum.csv")
    isfile(final_path) && error("拒绝覆盖已有终态结果")

    checkpoint_path = joinpath(config.outdir, "checkpoint_latest.jld2")
    total_sites = 5 * config.n_units
    times = zeros(Float64, config.n_steps + 1)
    correlations = zeros(ComplexF64, config.n_steps + 1)
    norms = zeros(Float64, config.n_steps + 1)
    linkdims_history = zeros(Int, config.n_steps + 1)
    start_step = 1

    if isfile(checkpoint_path)
        checkpoint = load(checkpoint_path)
        checkpoint["config"] == config || error("checkpoint 参数不匹配")
        energy = checkpoint["energy"]
        ground = checkpoint["ground"]
        source = checkpoint["source"]
        evolved = checkpoint["evolved"]
        sites = siteinds(ground)
        saved_times = checkpoint["times"]
        saved_correlations = checkpoint["correlations"]
        saved_norms = checkpoint["norms"]
        saved_linkdims = checkpoint["linkdims_history"]
        saved_count = length(saved_times)
        times[1:saved_count] .= saved_times
        correlations[1:saved_count] .= saved_correlations
        norms[1:saved_count] .= saved_norms
        linkdims_history[1:saved_count] .= saved_linkdims
        start_step = checkpoint["last_step"] + 1
        dmrg_seconds = checkpoint["dmrg_seconds"]
        variance_per_site = checkpoint["variance_per_site"]
        total_sz = checkpoint["total_sz"]
        dmrg_actual_maxdim = checkpoint["dmrg_actual_maxdim"]
        max_dmrg_truncation = checkpoint["max_dmrg_truncation"]
        final_dmrg_energy_delta = checkpoint["final_dmrg_energy_delta"]
        println("resume checkpoint step=$(start_step - 1)")
        flush(stdout)
    else
        sites = siteinds("S=1/2", total_sites; conserve_qns=true)
        hamiltonian = pentamer_chain_hamiltonian(
            sites, config.n_units; alpha=config.alpha, beta=config.beta
        )
        initial = MPS(sites, [isodd(site) ? "Up" : "Dn" for site in 1:total_sites])
        observer = DMRGObserver()
        dmrg_start = time()
        energy, ground = dmrg(
            hamiltonian,
            initial;
            nsweeps=config.nsweeps,
            maxdim=sweep_schedule(config.dmrg_maxdim, config.nsweeps),
            cutoff=config.dmrg_cutoff,
            observer,
            outputlevel=1,
        )
        dmrg_seconds = time() - dmrg_start
        energy_squared = real(inner(hamiltonian, ground, hamiltonian, ground))
        variance_per_site = max(energy_squared - energy^2, 0.0) / total_sites
        total_sz = sum(real.(expect(ground, "Sz")))
        dmrg_actual_maxdim = maximum(linkdims(ground))
        sweep_energies = real.(energies(observer))
        sweep_truncations = truncerrors(observer)
        max_dmrg_truncation = maximum(sweep_truncations)
        final_dmrg_energy_delta = length(sweep_energies) > 1 ?
            abs(sweep_energies[end] - sweep_energies[end - 1]) : NaN
        source = momentum_source(
            ground, sites; maxdim=config.tebd_maxdim, cutoff=config.tebd_cutoff
        )
        evolved = copy(source)
        times[1] = 0.0
        correlations[1] = inner(source, evolved)
        norms[1] = real(inner(evolved, evolved))
        linkdims_history[1] = maximum(linkdims(evolved))
    end
    source_norm_squared = real(inner(source, source))
    gates = tebd_gates(
        sites, config.n_units; alpha=config.alpha, beta=config.beta, tstep=config.tstep
    )

    evolution_start = time()
    report_interval = max(1, div(config.n_steps, 100))
    for step in start_step:config.n_steps
        evolved = apply(
            gates, evolved; cutoff=config.tebd_cutoff, maxdim=config.tebd_maxdim
        )
        current_time = step * config.tstep
        index = step + 1
        times[index] = current_time
        correlations[index] = inner(source, evolved) * exp(im * energy * current_time)
        norms[index] = real(inner(evolved, evolved))
        linkdims_history[index] = maximum(linkdims(evolved))

        if step % report_interval == 0 || step == config.n_steps
            elapsed = time() - evolution_start
            attempted_steps = step - start_step + 1
            eta_seconds = elapsed / attempted_steps * (config.n_steps - step)
            @printf(
                "step %d/%d (%.1f%%) t=%.6f linkdim=%d elapsed=%.1fs ETA=%.1fs\n",
                step,
                config.n_steps,
                100 * step / config.n_steps,
                current_time,
                linkdims_history[index],
                elapsed,
                eta_seconds,
            )
            flush(stdout)
        end
        should_checkpoint =
            (step % config.checkpoint_interval == 0 || step == stop_after_step) &&
            step < config.n_steps
        if should_checkpoint
            atomic_jldsave(
                checkpoint_path;
                config,
                energy,
                ground,
                source,
                evolved,
                dmrg_seconds,
                variance_per_site,
                total_sz,
                dmrg_actual_maxdim,
                max_dmrg_truncation,
                final_dmrg_energy_delta,
                times=times[1:index],
                correlations=correlations[1:index],
                norms=norms[1:index],
                linkdims_history=linkdims_history[1:index],
                last_step=step,
            )
            println("checkpoint step=$(step)")
            flush(stdout)
        end
        if stop_after_step > 0 && step == stop_after_step
            println("controlled stop step=$(step)")
            flush(stdout)
            exit(75)
        end
    end
    evolution_seconds = time() - evolution_start

    omegas = omega_grid(config.omega_min, config.omega_max, config.omega_step)
    fourier_start = time()
    spectrum = fourier_spectrum(times, correlations, omegas, config.eta)
    fourier_seconds = time() - fourier_start
    norm_drift = maximum(abs.(norms .- source_norm_squared)) /
        max(abs(source_norm_squared), eps())
    metrics = [
        "alpha" => config.alpha,
        "beta" => config.beta,
        "n_units" => config.n_units,
        "L" => total_sites,
        "q_over_pi" => 1.0,
        "eta" => config.eta,
        "tstep" => config.tstep,
        "tmax" => config.tstep * config.n_steps,
        "energy" => energy,
        "variance_per_site" => variance_per_site,
        "total_sz" => total_sz,
        "source_norm_squared" => source_norm_squared,
        "correlation_t0_real" => real(correlations[1]),
        "correlation_t0_imag" => imag(correlations[1]),
        "relative_norm_drift" => norm_drift,
        "dmrg_actual_maxdim" => dmrg_actual_maxdim,
        "source_actual_maxdim" => maximum(linkdims(source)),
        "tebd_actual_maxdim" => maximum(linkdims_history),
        "max_dmrg_truncation" => max_dmrg_truncation,
        "final_dmrg_energy_delta" => final_dmrg_energy_delta,
        "spectrum_min" => minimum(spectrum),
        "spectrum_max" => maximum(spectrum),
        "dmrg_seconds" => dmrg_seconds,
        "tebd_seconds" => evolution_seconds,
        "fourier_seconds" => fourier_seconds,
        "threads" => Threads.nthreads(),
        "momentum_normalization" => "1/sqrt(L)",
        "fourier_normalization" => "one_sided_trapezoid/pi",
        "time_window" => "exponential",
        "finished_at_utc" => Dates.format(now(UTC), dateformat"yyyy-mm-ddTHH:MM:SS"),
    ]
    write_outputs(
        config,
        times,
        correlations,
        norms,
        linkdims_history,
        omegas,
        spectrum,
        metrics,
        source,
    )
    isfile(checkpoint_path) && rm(checkpoint_path)
    println("TEBD_QPI_AUTOCORR_SUCCESS outdir=$(config.outdir)")
end


main()
