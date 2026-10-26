"""完整动量连通自相关的 DSF，逐个动量独立计算。"""

include(joinpath(dirname(@__DIR__), "src", "PentamerChain.jl"))
using .PentamerChain
using ITensors
using ITensorMPS
using JLD2
using LinearAlgebra
using DelimitedFiles
using Printf
using Random
using TOML

function config_from_args()
    length(ARGS) == 8 || error("参数：OUTDIR ALPHA N_UNITS DT TMAX TEBD_MAXDIM Q_POINTS DMRG_MAXDIM")
    config = (alpha=parse(Float64, ARGS[2]), beta=0.5, n_units=parse(Int, ARGS[3]),
              dt=parse(Float64, ARGS[4]), tmax=parse(Float64, ARGS[5]),
              tebd_maxdim=parse(Int, ARGS[6]), q_points=parse(Int, ARGS[7]),
              dmrg_maxdim=parse(Int, ARGS[8]), cutoff=1e-10, nsweeps=20)
    iseven(config.n_units) && config.n_units > 0 || error("要求偶数个五聚体")
    config.dt > 0 && config.tmax > 0 && config.q_points >= 3 || error("无效网格")
    steps = round(Int, config.tmax / config.dt)
    isapprox(steps * config.dt, config.tmax; atol=1e-12) || error("TMAX/DT 不能整除")
    return abspath(ARGS[1]), config, steps
end

function reflection_gates(sites, config)
    bonds = Float64[]
    for bond in 1:(length(sites) - 1)
        push!(bonds, mod(bond, 5) in (1, 4) ? config.alpha : mod(bond, 5) == 0 ? config.beta : 1.0)
    end
    function layer(parity, dt)
        gates = ITensor[]
        for bond in parity:2:length(bonds)
            a, b = sites[bond], sites[bond + 1]
            h = bonds[bond] * (op("Sz", a) * op("Sz", b) +
                0.5 * op("S+", a) * op("S-", b) + 0.5 * op("S-", a) * op("S+", b))
            push!(gates, exp(-im * dt * h))
        end
        return gates
    end
    # 偶数长度下，各层分别保持空间反演。
    odd = layer(1, config.dt / 2)
    return vcat(odd, layer(2, config.dt), odd)
end

function momentum_source(ground, sites, q, config)
    os = OpSum()
    for j in eachindex(sites)
        os += exp(im * q * j) / sqrt(length(sites)), "Sz", j
    end
    source = apply(MPO(os, sites), ground; cutoff=1e-12, maxdim=2 * config.dmrg_maxdim)
    mean_value = inner(ground, source)
    if abs(mean_value) > 1e-13
        source = add(source, -mean_value * ground; cutoff=1e-12, maxdim=2 * config.dmrg_maxdim)
    end
    return source, mean_value
end

function atomic_save(path; kwargs...)
    jldsave(path * ".tmp"; kwargs...)
    mv(path * ".tmp", path; force=true)
end

function spectrum(times, corr, omegas)
    dt = times[2] - times[1]
    window = 1 .- times ./ times[end]
    weights = copy(window)
    weights[1] *= 0.5
    weights[end] *= 0.5
    return real.(exp.(im .* (omegas * transpose(times))) * (weights .* corr)) .* (dt / pi)
end

function main()
    outdir, config, steps = config_from_args()
    mkpath(outdir)
    metapath = joinpath(outdir, "run_metadata.toml")
    if isfile(metapath)
        TOML.parsefile(metapath)["julia_version"] == string(VERSION) ||
            error("已有数据来自其他 Julia 版本，请使用新目录或只读取 CSV 作图")
    end
    BLAS.set_num_threads(1)
    groundpath = joinpath(outdir, "ground.jld2")
    seedpath = get(ENV, "PENTAMER_GROUND_SEED", "")
    extra_sweeps = 0
    if isfile(groundpath)
        saved = load(groundpath)
        saved["config"] == config || error("已有基态参数不匹配")
        energy, ground, variance = saved["energy"], saved["ground"], saved["variance"]
        extra_sweeps = get(saved, "extra_sweeps", 0)
    elseif !isempty(seedpath)
        saved = load(seedpath)
        all(key -> getproperty(saved["config"], key) == getproperty(config, key),
            (:alpha, :beta, :n_units)) || error("基态种子模型不匹配")
        energy, ground, variance = saved["energy"], saved["ground"], saved["variance"]
        extra_sweeps = get(saved, "extra_sweeps", 0)
    else
        Random.seed!(20261001)
        energy, ground, sites = compute_ground_state_hires(; N_units=config.n_units,
            alpha=config.alpha, beta=config.beta, maxdim=config.dmrg_maxdim,
            cutoff=1e-12, nsweeps=config.nsweeps)
        hamiltonian = pentamer_chain_hamiltonian(sites, config.n_units; alpha=config.alpha, beta=config.beta)
        variance = max(real(inner(hamiltonian, ground, hamiltonian, ground)) - energy^2, 0.0) / length(sites)
    end
    sites = siteinds(ground)
    if variance > 1e-10
        any(name -> startswith(name, "q") && (endswith(name, ".jld2") || endswith(name, ".checkpoint")),
            readdir(outdir)) && error("已有动力学数据，基态改进必须使用新目录")
        hamiltonian = pentamer_chain_hamiltonian(sites, config.n_units; alpha=config.alpha, beta=config.beta)
        # 方差未达标时，先改进基态，不启动谱扫描。
        for attempt in 1:3
            println("GROUND_REFINE attempt=$(attempt) variance_per_site=$(variance)")
            flush(stdout)
            energy, ground = dmrg(hamiltonian, ground; nsweeps=20, maxdim=config.dmrg_maxdim,
                cutoff=1e-12, eigsolve_krylovdim=8, eigsolve_maxiter=4, outputlevel=1)
            extra_sweeps += 20
            variance = max(real(inner(hamiltonian, ground, hamiltonian, ground)) - energy^2, 0.0) / length(sites)
            atomic_save(groundpath; config, energy, ground, variance, extra_sweeps)
            variance <= 1e-10 && break
        end
        variance <= 1e-10 || error("基态方差未通过，须提高预算后在新目录续算")
    end
    atomic_save(groundpath; config, energy, ground, variance, extra_sweeps)
    static = correlation_matrix(ground, "Sz", "Sz")
    println("GROUND L=$(length(sites)) alpha=$(config.alpha) E=$(energy) variance_per_site=$(variance)")
    flush(stdout)
    gates = reflection_gates(sites, config)
    qvals = collect(range(0, 2pi; length=config.q_points))
    if haskey(ENV, "PENTAMER_FULLQ_VALUES")
        qvals = parse.(Float64, split(ENV["PENTAMER_FULLQ_VALUES"], ',')) .* pi
    end
    times = collect(0:steps) .* config.dt
    omegas = collect(range(0, 4; length=801))
    matrix = zeros(length(qvals), length(omegas))
    metrics = Vector{NamedTuple}(undef, length(qvals))
    Threads.@threads :dynamic for iq in eachindex(qvals)
        q = qvals[iq]
        local_gates = deepcopy(gates)
        cellpath = joinpath(outdir, "q$(lpad(iq, 3, '0')).jld2")
        println("Q $(iq)/$(length(qvals)) q/pi=$(q/pi)")
        flush(stdout)
        if isfile(cellpath)
            cell = load(cellpath)
            cell["config"] == config && cell["q"] == q || error("已有动量参数不匹配")
            corr, norms, source_norm, expected = cell["corr"], cell["norms"], cell["source_norm"], cell["expected"]
            norm_api_error = get(cell, "norm_api_error", 0.0)
        else
            source, mean_value = momentum_source(deepcopy(ground), sites, q, config)
            source_norm = real(inner(source, source))
            coefficients = exp.(im .* q .* collect(1:length(sites))) ./ sqrt(length(sites))
            expected = real(dot(coefficients, static * coefficients)) - abs2(mean_value)
            corr = zeros(ComplexF64, steps + 1)
            norms = zeros(steps + 1)
            corr[1], norms[1] = source_norm, source_norm
            evolved = copy(source)
            begin_step = 1
            norm_api_error = 0.0
            checkpoint = cellpath * ".checkpoint"
            if isfile(checkpoint)
                saved = load(checkpoint)
                saved["config"] == config && saved["q"] == q || error("断点参数不匹配")
                evolved, corr, norms = saved["evolved"], saved["corr"], saved["norms"]
                begin_step = saved["step"] + 1
                norm_api_error = get(saved, "norm_api_error", 0.0)
            end
            started = time()
            if source_norm > 1e-20
                for step in begin_step:steps
                    evolved = apply(local_gates, evolved; cutoff=config.cutoff, maxdim=config.tebd_maxdim)
                    corr[step + 1] = inner(source, evolved) * exp(im * energy * times[step + 1])
                    norms[step + 1] = norm(evolved)^2
                    if step % 200 == 0 || step == steps
                        full_norm = real(inner(evolved, evolved))
                        norm_api_error = max(norm_api_error, abs(norms[step + 1] - full_norm) / source_norm)
                        norm_api_error < 1e-8 || error("规范中心范数与完整收缩不一致")
                    end
                    if step % 20 == 0 || step == steps
                        @printf("  q/pi=%.6f step %d/%d t=%.3f chi=%d elapsed=%.2fs\n", q/pi, step, steps,
                            times[step + 1], maximum(linkdims(evolved)), time() - started)
                        flush(stdout)
                    end
                    if step % 200 == 0 && step < steps
                        atomic_save(checkpoint; config, q, evolved, corr, norms, step, norm_api_error)
                    end
                end
            end
            atomic_save(cellpath; config, q, times, corr, norms, source_norm, expected, norm_api_error)
            open(joinpath(outdir, "q$(lpad(iq, 3, '0'))_correlation.csv"), "w") do io
                println(io, "time,real_corr,imag_corr,norm_squared")
                writedlm(io, hcat(times, real.(corr), imag.(corr), norms), ',')
            end
        end
        matrix[iq, :] .= spectrum(times, corr, omegas)
        metrics[iq] = (q_over_pi=q/pi, source_norm=source_norm, expected_static_norm=expected,
            source_norm_error=abs(source_norm - expected),
            norm_api_max_relative_error=norm_api_error,
            relative_norm_drift=source_norm > 1e-20 ? maximum(abs.(norms .- source_norm)) / source_norm : 0.0,
            min_spectrum=minimum(matrix[iq, :]))
    end
    writedlm(joinpath(outdir, "q.csv"), qvals, ',')
    writedlm(joinpath(outdir, "omega.csv"), omegas, ',')
    writedlm(joinpath(outdir, "spectrum.csv"), matrix, ',')
    open(joinpath(outdir, "metrics.csv"), "w") do io
        println(io, join(keys(first(metrics)), ','))
        for row in metrics
            println(io, join(values(row), ','))
        end
    end
    atomic_save(joinpath(outdir, "result.jld2"); config, energy, variance, qvals, omegas,
        matrix, metrics, time_window="triangular", normalization="1/sqrt(L), Re integral/pi",
        inversion_averaging=false, clipping=false)
    metadata = Dict{String, Any}(string(key) => value for (key, value) in pairs(config))
    merge!(metadata, Dict("L" => length(sites), "energy" => energy,
        "variance_per_site" => variance, "time_window" => "triangular",
        "window_fwhm" => 5.566229513 / config.tmax,
        "operator" => "connected full momentum Sz / sqrt(L)",
        "static_reflection_relative_rms" => norm(static - reverse(static; dims=(1, 2))) / norm(static),
        "ground_maxdim_used" => maximum(linkdims(ground)),
        "ground_additional_sweeps" => extra_sweeps, "ground_seed_path" => seedpath,
        "norm_monitor" => "canonical center, full contraction checked every 200 steps",
        "inversion_averaging" => false, "clipping" => false,
        "julia_version" => string(VERSION), "itensors_version" => string(pkgversion(ITensors)),
        "itensormps_version" => string(pkgversion(ITensorMPS))))
    open(joinpath(outdir, "run_metadata.toml"), "w") do io
        TOML.print(io, metadata)
    end
    println("FULLQ_SUCCESS ", outdir)
end

main()
