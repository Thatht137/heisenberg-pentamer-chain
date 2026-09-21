"""可恢复地计算一个 q 切片的修正向量谱。"""

include(joinpath(dirname(dirname(@__DIR__)), "src", "PentamerChain.jl"))
using .PentamerChain
using Dates
using ITensors
using ITensorMPS
using JLD2
using Printf

function parse_config()
    length(ARGS) in (15, 16) || error(
        "参数: OUTDIR ALPHA BETA N_UNITS Q_OVER_PI ETA OMEGA_MIN OMEGA_MAX " *
        "OMEGA_STEP DMRG_MAXDIM CV_MAXDIM NSWEEPS DMRG_CUTOFF CV_CUTOFF " *
        "MAX_NEW_POINTS [OMEGA_ORDER]"
    )
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
        dmrg_cutoff=parse(Float64, ARGS[13]),
        cv_cutoff=parse(Float64, ARGS[14]),
        max_new_points=parse(Int, ARGS[15]),
        omega_order=length(ARGS) == 16 ? ARGS[16] : "ascending",
    )
end

function sweep_schedule(maxdim::Int, nsweeps::Int)
    return [min(maxdim, 20 * 2^(min(sweep - 1, 5))) for sweep in 1:nsweeps]
end

function atomic_jldsave(path::String; kwargs...)
    temporary = path * ".tmp"
    rm(temporary; force=true)
    jldsave(temporary; kwargs...)
    mv(temporary, path; force=true)
end

function atomic_write(writer, path::String)
    temporary = path * ".tmp"
    rm(temporary; force=true)
    open(writer, temporary, "w")
    mv(temporary, path; force=true)
end

function momentum_source(psi, sites, q::Real; maxdim::Int, cutoff::Real)
    result = nothing
    normalization = sqrt(length(sites))
    for site in eachindex(sites)
        term = deepcopy(psi)
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

function point_path(outdir::String, index::Int)
    return joinpath(outdir, "points", @sprintf("omega-%04d.csv", index))
end

function write_point(path::String, row)
    atomic_write(path) do file
        println(file, "q_over_pi,omega,intensity,relative_residual,solve_seconds,solution_maxdim")
        @printf(
            file,
            "%.12g,%.12g,%.16e,%.16e,%.8f,%d\n",
            row.q_over_pi,
            row.omega,
            row.intensity,
            row.relative_residual,
            row.solve_seconds,
            row.solution_maxdim,
        )
    end
end

function read_point(path::String)
    lines = readlines(path)
    length(lines) == 2 || error("频率点文件损坏: $path")
    fields = split(lines[2], ',')
    length(fields) == 6 || error("频率点字段损坏: $path")
    return (
        q_over_pi=parse(Float64, fields[1]),
        omega=parse(Float64, fields[2]),
        intensity=parse(Float64, fields[3]),
        relative_residual=parse(Float64, fields[4]),
        solve_seconds=parse(Float64, fields[5]),
        solution_maxdim=parse(Int, fields[6]),
    )
end

function write_spectrum(path::String, rows)
    atomic_write(path) do file
        println(file, "q_over_pi,omega,intensity,relative_residual,solve_seconds,solution_maxdim")
        for row in rows
            @printf(
                file,
                "%.12g,%.12g,%.16e,%.16e,%.8f,%d\n",
                row.q_over_pi,
                row.omega,
                row.intensity,
                row.relative_residual,
                row.solve_seconds,
                row.solution_maxdim,
            )
        end
    end
end

function main()
    config = parse_config()
    0.0 <= config.alpha <= 1.0 || error("alpha 必须位于 [0,1]")
    0.0 <= config.beta <= 1.0 || error("beta 必须位于 [0,1]")
    config.n_units > 0 || error("n_units 必须为正整数")
    0.0 <= config.q_over_pi <= 2.0 || error("q_over_pi 必须位于 [0,2]")
    config.eta > 0 || error("eta 必须为正数")
    config.omega_min >= 0 || error("omega_min 不得为负数")
    config.omega_step > 0 || error("omega_step 必须为正数")
    config.omega_min <= config.omega_max || error("omega_min 不得大于 omega_max")
    config.omega_order in ("ascending", "descending") ||
        error("omega_order 必须为 ascending 或 descending")
    min(config.dmrg_maxdim, config.cv_maxdim, config.nsweeps) > 0 ||
        error("维数上限和 sweep 数必须为正整数")
    min(config.dmrg_cutoff, config.cv_cutoff) > 0 || error("截断阈值必须为正数")
    config.max_new_points >= 0 || error("max_new_points 不得为负数")
    mkpath(config.outdir)
    mkpath(joinpath(config.outdir, "points"))

    total_sites = 5 * config.n_units
    iseven(total_sites) || error("当前计算要求偶数格点")
    ground_path = joinpath(config.outdir, "ground_state.jld2")
    ground_reused = isfile(ground_path)
    if ground_reused
        loaded = load(ground_path)
        loaded["alpha"] == config.alpha || error("基态 alpha 不匹配")
        loaded["beta"] == config.beta || error("基态 beta 不匹配")
        loaded["n_units"] == config.n_units || error("基态长度不匹配")
        sites = loaded["sites"]
        ground = loaded["ground"]
        length(ground) == total_sites || error("缓存基态长度损坏")
        all(siteind(ground, index) == sites[index] for index in eachindex(sites)) ||
            error("缓存基态站点索引损坏")
        energy = loaded["energy"]
        variance = loaded["variance"]
        sweep_energies = loaded["sweep_energies"]
        sweep_truncations = loaded["sweep_truncations"]
        dmrg_seconds = loaded["dmrg_seconds"]
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
        variance = max(energy_squared - energy^2, 0.0)
        sweep_energies = real.(energies(observer))
        sweep_truncations = truncerrors(observer)
        atomic_jldsave(
            ground_path;
            ground,
            sites,
            energy,
            variance,
            sweep_energies,
            sweep_truncations,
            dmrg_seconds,
            alpha=config.alpha,
            beta=config.beta,
            n_units=config.n_units,
        )
    end
    hamiltonian = pentamer_chain_hamiltonian(
        sites, config.n_units; alpha=config.alpha, beta=config.beta
    )

    source_path = joinpath(config.outdir, "source_state.jld2")
    source_reused = isfile(source_path)
    q = config.q_over_pi * pi
    if source_reused
        loaded = load(source_path)
        loaded["q_over_pi"] == config.q_over_pi || error("动量源 q 不匹配")
        source = loaded["source"]
        length(source) == total_sites || error("缓存动量源长度损坏")
        all(siteind(source, index) == sites[index] for index in eachindex(sites)) ||
            error("缓存动量源站点索引损坏")
    else
        source = momentum_source(
            ground, sites, q; maxdim=config.cv_maxdim, cutoff=config.cv_cutoff
        )
        atomic_jldsave(source_path; source, q_over_pi=config.q_over_pi)
    end
    source_norm = real(inner(source, source))
    source_maxdim = maximum(linkdims(source))
    omega_grid = collect(config.omega_min:config.omega_step:config.omega_max)
    omegas = config.omega_order == "descending" ? reverse(omega_grid) : omega_grid
    point_exists = [isfile(point_path(config.outdir, index)) for index in eachindex(omegas)]
    completed = count(identity, point_exists)
    point_exists == [index <= completed for index in eachindex(omegas)] ||
        error("频率点必须从网格起点连续完成")
    rows = [read_point(point_path(config.outdir, index)) for index in 1:completed]
    for index in eachindex(rows)
        isapprox(rows[index].q_over_pi, config.q_over_pi; atol=1e-12, rtol=0.0) ||
            error("频率点动量不匹配: index=$index")
        isapprox(rows[index].omega, omegas[index]; atol=1e-12, rtol=0.0) ||
            error("频率点与网格不匹配: index=$index")
    end

    checkpoint_path = joinpath(config.outdir, "checkpoint_latest.jld2")
    if completed == 0
        if isfile(checkpoint_path)
            checkpoint = load(checkpoint_path)
            checkpoint["last_index"] == 1 || error("首个 checkpoint 索引损坏")
            checkpoint["q_over_pi"] == config.q_over_pi || error("checkpoint 动量不匹配")
            isapprox(checkpoint["omega"], omegas[1]; atol=1e-12, rtol=0.0) ||
                error("checkpoint 频率不匹配")
            row = (
                q_over_pi=Float64(checkpoint["q_over_pi"]),
                omega=Float64(checkpoint["omega"]),
                intensity=Float64(checkpoint["intensity"]),
                relative_residual=Float64(checkpoint["relative_residual"]),
                solve_seconds=Float64(checkpoint["solve_seconds"]),
                solution_maxdim=Int(checkpoint["solution_maxdim"]),
            )
            write_point(point_path(config.outdir, 1), row)
            push!(rows, row)
            completed = 1
            guess = checkpoint["solution"]
        else
            guess = deepcopy(source)
        end
    else
        isfile(checkpoint_path) || error("缺少最新修正向量 checkpoint")
        checkpoint = load(checkpoint_path)
        last_index = checkpoint["last_index"]
        last_index in (completed, completed + 1) || error("checkpoint 索引不匹配")
        last_index <= length(omegas) || error("checkpoint 索引越界")
        checkpoint["q_over_pi"] == config.q_over_pi || error("checkpoint 动量不匹配")
        isapprox(checkpoint["omega"], omegas[last_index]; atol=1e-12, rtol=0.0) ||
            error("checkpoint 频率不匹配")
        if last_index == completed + 1
            row = (
                q_over_pi=Float64(checkpoint["q_over_pi"]),
                omega=Float64(checkpoint["omega"]),
                intensity=Float64(checkpoint["intensity"]),
                relative_residual=Float64(checkpoint["relative_residual"]),
                solve_seconds=Float64(checkpoint["solve_seconds"]),
                solution_maxdim=Int(checkpoint["solution_maxdim"]),
            )
            write_point(point_path(config.outdir, last_index), row)
            push!(rows, row)
            completed = last_index
        end
        guess = checkpoint["solution"]
    end
    length(guess) == total_sites || error("checkpoint 解向量长度损坏")
    all(siteind(guess, index) == sites[index] for index in eachindex(sites)) ||
        error("checkpoint 解向量站点索引损坏")

    new_points = 0
    cv_seconds_this_attempt = 0.0
    for index in Iterators.drop(eachindex(omegas), completed)
        if config.max_new_points > 0 && new_points >= config.max_new_points
            break
        end
        omega = omegas[index]
        coefficient = energy + omega + im * config.eta
        solve_start = time()
        solution = solve_correction_vector(hamiltonian, source, guess, coefficient, config)
        solve_seconds = time() - solve_start
        row = (
            q_over_pi=config.q_over_pi,
            omega,
            intensity=-imag(inner(source, solution)) / pi,
            relative_residual=relative_residual(
                solution, source, hamiltonian, coefficient
            ),
            solve_seconds,
            solution_maxdim=maximum(linkdims(solution)),
        )
        atomic_jldsave(
            checkpoint_path;
            solution,
            last_index=index,
            omega,
            q_over_pi=config.q_over_pi,
            intensity=row.intensity,
            relative_residual=row.relative_residual,
            solve_seconds=row.solve_seconds,
            solution_maxdim=row.solution_maxdim,
        )
        write_point(point_path(config.outdir, index), row)
        push!(rows, row)
        guess = solution
        new_points += 1
        cv_seconds_this_attempt += solve_seconds
        @printf(
            "omega %.4f (%d/%d): S=%.8e residual=%.3e D=%d\n",
            omega,
            index,
            length(omegas),
            row.intensity,
            row.relative_residual,
            row.solution_maxdim,
        )
        flush(stdout)
    end

    write_spectrum(joinpath(config.outdir, "spectrum.csv"), rows)
    complete = length(rows) == length(omegas)
    final_energy_delta = (
        length(sweep_energies) > 1 ? abs(sweep_energies[end] - sweep_energies[end - 1]) : NaN
    )
    atomic_write(joinpath(config.outdir, "sweep_history.csv")) do file
        println(file, "sweep,energy,max_truncation_error")
        for sweep in eachindex(sweep_energies)
            truncation = sweep <= length(sweep_truncations) ? sweep_truncations[sweep] : NaN
            @printf(file, "%d,%.16e,%.16e\n", sweep, sweep_energies[sweep], truncation)
        end
    end
    atomic_write(joinpath(config.outdir, "metrics.csv")) do file
        println(file, "metric,value")
        metrics = [
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
            "max_cv_residual" => maximum(row.relative_residual for row in rows),
            "max_solution_dim" => maximum(row.solution_maxdim for row in rows),
            "dmrg_seconds" => dmrg_seconds,
            "cv_seconds" => sum(row.solve_seconds for row in rows),
            "cv_seconds_this_attempt" => cv_seconds_this_attempt,
            "ground_reused" => ground_reused,
            "source_reused" => source_reused,
            "completed_points" => length(rows),
            "total_points" => length(omegas),
            "complete" => complete,
            "threads" => Threads.nthreads(),
            "finished_at_utc" => Dates.format(now(UTC), dateformat"yyyy-mm-ddTHH:MM:SS"),
        ]
        for (key, value) in metrics
            println(file, key, ',', value)
        end
    end
    atomic_jldsave(
        joinpath(config.outdir, "spectrum.jld2");
        config,
        omegas=[row.omega for row in rows],
        intensities=[row.intensity for row in rows],
        residuals=[row.relative_residual for row in rows],
        solve_times=[row.solve_seconds for row in rows],
        solution_dims=[row.solution_maxdim for row in rows],
        energy,
        variance,
        source_norm,
        complete,
    )
    marker = complete ? "CV_DSF_RESUMABLE_SUCCESS" : "CV_DSF_RESUMABLE_PARTIAL"
    println("$marker outdir=$(config.outdir) completed=$(length(rows))/$(length(omegas))")
end

if abspath(PROGRAM_FILE) == @__FILE__
    main()
end
