"""用 ITensor 修正向量计算一个 q 切片并记录残差。"""

include(joinpath(dirname(dirname(@__DIR__)), "src", "PentamerChain.jl"))
using .PentamerChain
using Dates
using ITensors
using ITensorMPS
using JLD2
using Printf

function parse_config()
    length(ARGS) in (13, 14) || error(
        "参数: OUTDIR ALPHA BETA N_UNITS Q_OVER_PI ETA OMEGA_MIN OMEGA_MAX " *
        "OMEGA_STEP DMRG_MAXDIM CV_MAXDIM NSWEEPS DMRG_CUTOFF [CV_CUTOFF]"
    )
    dmrg_cutoff = parse(Float64, ARGS[13])
    return (
        outdir=abspath(ARGS[1]),
        alpha=parse(Float64, ARGS[2]),
        beta=parse(Float64, ARGS[3]),
        n_units=parse(Int, ARGS[4]),
        q_over_pi=parse(Float64, ARGS[5]),
        eta=parse(Float64, ARGS[6]),
        omega_min=parse(Float64, ARGS[7]),
        omega_max=parse(Float64, ARGS[8]),
        omega_step=parse(Float64, ARGS[9]),
        dmrg_maxdim=parse(Int, ARGS[10]),
        cv_maxdim=parse(Int, ARGS[11]),
        nsweeps=parse(Int, ARGS[12]),
        dmrg_cutoff,
        cv_cutoff=length(ARGS) == 14 ? parse(Float64, ARGS[14]) : dmrg_cutoff,
    )
end

function sweep_schedule(maxdim::Int, nsweeps::Int)
    return [min(maxdim, 20 * 2^(min(sweep - 1, 5))) for sweep in 1:nsweeps]
end

function momentum_source(psi, sites, q::Real; maxdim::Int, cutoff::Real)
    result = nothing
    normalization = sqrt(length(sites))
    for site in eachindex(sites)
        term = copy(psi)
        term[site] = noprime(term[site] * op("Sz", sites[site]))
        term *= exp(im * q * site) / normalization
        result = isnothing(result) ? term : add(result, term; maxdim, cutoff)
    end
    return result
end

function relative_residual(x, b, hamiltonian, coefficient)
    xx = real(inner(x, x))
    bb = real(inner(b, b))
    h2 = real(inner(hamiltonian, x, hamiltonian, x))
    xhx = inner(x', hamiltonian, x)
    xb = inner(x, b)
    bhx = inner(b', hamiltonian, x)
    residual_squared = (
        abs2(coefficient) * xx + h2 + bb -
        2 * real(conj(coefficient) * xhx) -
        2 * real(conj(coefficient) * xb) +
        2 * real(bhx)
    )
    return sqrt(max(residual_squared, 0.0)) / max(sqrt(bb), eps())
end

function solve_correction_vector(hamiltonian, source, guess, coefficient, config)
    solution = linsolve(
        hamiltonian,
        source,
        guess,
        coefficient,
        -1.0;
        nsweeps=config.nsweeps,
        maxdim=config.cv_maxdim,
        cutoff=config.cv_cutoff,
        updater_kwargs=(; tol=1e-12, maxiter=500, krylovdim=100),
    )
    residual = relative_residual(solution, source, hamiltonian, coefficient)
    if residual > 1e-5
        # 低频点先用常规预算，超门槛时只对当前点加大求解预算。
        solution = linsolve(
            hamiltonian,
            source,
            solution,
            coefficient,
            -1.0;
            nsweeps=max(config.nsweeps + 4, 2 * config.nsweeps),
            maxdim=config.cv_maxdim,
            cutoff=config.cv_cutoff,
            updater_kwargs=(; tol=1e-13, maxiter=1000, krylovdim=200),
        )
    end
    return solution
end

function main()
    config = parse_config()
    0.0 <= config.alpha <= 1.0 || error("alpha 必须位于 [0,1]")
    0.0 <= config.beta <= 1.0 || error("beta 必须位于 [0,1]")
    isdir(config.outdir) || mkpath(config.outdir)
    isfile(joinpath(config.outdir, "spectrum.csv")) && error("拒绝覆盖已有结果")

    total_sites = 5 * config.n_units
    iseven(total_sites) || error("当前计算要求偶数格点")
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
    variance = max(energy_squared - energy^2, 0.0)
    q = config.q_over_pi * pi
    source = momentum_source(
        ground, sites, q; maxdim=config.cv_maxdim, cutoff=config.cv_cutoff
    )
    source_norm = real(inner(source, source))
    source_maxdim = maximum(linkdims(source))
    omegas = collect(config.omega_min:config.omega_step:config.omega_max)
    intensities = Float64[]
    residuals = Float64[]
    solve_times = Float64[]
    solution_dims = Int[]
    guess = copy(source)

    open(joinpath(config.outdir, "spectrum.csv"), "w") do file
        println(file, "q_over_pi,omega,intensity,relative_residual,solve_seconds,solution_maxdim")
        for (index, omega) in enumerate(omegas)
            coefficient = energy + omega + im * config.eta
            solve_start = time()
            solution = solve_correction_vector(hamiltonian, source, guess, coefficient, config)
            solve_seconds = time() - solve_start
            intensity = -imag(inner(source, solution)) / pi
            residual = relative_residual(solution, source, hamiltonian, coefficient)
            push!(intensities, intensity)
            push!(residuals, residual)
            push!(solve_times, solve_seconds)
            push!(solution_dims, maximum(linkdims(solution)))
            @printf(
                file,
                "%.12g,%.12g,%.16e,%.16e,%.8f,%d\n",
                config.q_over_pi,
                omega,
                intensity,
                residual,
                solve_seconds,
                solution_dims[end],
            )
            flush(file)
            @printf(
                "omega %.4f (%d/%d): S=%.8e residual=%.3e D=%d\n",
                omega,
                index,
                length(omegas),
                intensity,
                residual,
                solution_dims[end],
            )
            flush(stdout)
            guess = solution
        end
    end

    sweep_energies = real.(energies(observer))
    sweep_truncations = truncerrors(observer)
    final_energy_delta = length(sweep_energies) > 1 ? abs(sweep_energies[end] - sweep_energies[end - 1]) : NaN
    open(joinpath(config.outdir, "sweep_history.csv"), "w") do file
        println(file, "sweep,energy,max_truncation_error")
        for sweep in eachindex(sweep_energies)
            truncation = sweep <= length(sweep_truncations) ? sweep_truncations[sweep] : NaN
            @printf(file, "%d,%.16e,%.16e\n", sweep, sweep_energies[sweep], truncation)
        end
    end
    open(joinpath(config.outdir, "metrics.csv"), "w") do file
        println(file, "metric,value")
        rows = [
            "alpha" => config.alpha,
            "beta" => config.beta,
            "n_units" => config.n_units,
            "L" => total_sites,
            "q_over_pi" => config.q_over_pi,
            "eta" => config.eta,
            "dmrg_cutoff" => config.dmrg_cutoff,
            "cv_cutoff" => config.cv_cutoff,
            "energy" => energy,
            "variance_per_site" => variance / total_sites,
            "total_sz" => sum(real.(expect(ground, "Sz"))),
            "source_norm_squared" => source_norm,
            "source_maxdim" => source_maxdim,
            "dmrg_actual_maxdim" => maximum(linkdims(ground)),
            "max_dmrg_truncation" => maximum(sweep_truncations),
            "final_dmrg_energy_delta" => final_energy_delta,
            "max_cv_residual" => maximum(residuals),
            "max_solution_dim" => maximum(solution_dims),
            "dmrg_seconds" => dmrg_seconds,
            "cv_seconds" => sum(solve_times),
            "threads" => Threads.nthreads(),
            "finished_at_utc" => Dates.format(now(UTC), dateformat"yyyy-mm-ddTHH:MM:SS"),
        ]
        for (key, value) in rows
            println(file, key, ',', value)
        end
    end
    jldsave(
        joinpath(config.outdir, "spectrum.jld2");
        config,
        omegas,
        intensities,
        residuals,
        solve_times,
        solution_dims,
        energy,
        variance,
        source_norm,
    )
    println("CV_DSF_CELL_SUCCESS outdir=$(config.outdir)")
end

main()
