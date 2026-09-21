"""
执行单个正 alpha DMRG cell，并保存完整数值诊断。
"""

using Pkg
Pkg.activate(dirname(dirname(@__DIR__)))

include(joinpath(dirname(dirname(@__DIR__)), "src", "PentamerChain.jl"))
using .PentamerChain
using Dates
using ITensors
using ITensorMPS
using JLD2
using Printf

function parse_args()
    length(ARGS) == 9 || error(
        "用法: dmrg_cell.jl OUTDIR ALPHA BETA N_UNITS MAXDIM NSWEEPS CUTOFF INIT_MODE SAVE_MPS",
    )
    return (
        outdir=abspath(ARGS[1]),
        alpha=parse(Float64, ARGS[2]),
        beta=parse(Float64, ARGS[3]),
        n_units=parse(Int, ARGS[4]),
        maxdim=parse(Int, ARGS[5]),
        nsweeps=parse(Int, ARGS[6]),
        cutoff=parse(Float64, ARGS[7]),
        init_mode=ARGS[8],
        save_mps=ARGS[9] == "1",
    )
end

function initial_state(length::Int, mode::String)
    iseven(length) || error("本任务只接受偶数总格点")
    if mode == "neel"
        return [isodd(site) ? "Up" : "Dn" for site in 1:length]
    elseif mode == "shifted"
        return [isodd(site) ? "Dn" : "Up" for site in 1:length]
    end
    error("INIT_MODE 必须为 neel 或 shifted")
end

function sweep_schedule(maxdim::Int, nsweeps::Int)
    return [sweep <= 5 ? min(maxdim, 50 * 2^(sweep - 1)) : maxdim for sweep in 1:nsweeps]
end

function write_metrics(path::String, values)
    open(path, "w") do file
        println(file, "metric,value")
        for (key, value) in values
            println(file, key, ",", value)
        end
    end
end

function main()
    config = parse_args()
    0.0 <= config.alpha <= 1.0 || error("禁止 alpha<0 或 alpha>1")
    0.0 <= config.beta <= 1.0 || error("beta 必须位于 [0,1]")
    iseven(config.n_units) || error("N_UNITS 必须为偶数以固定 Sz=0")
    mkpath(config.outdir)

    n_sites = 5 * config.n_units
    sites = siteinds("S=1/2", n_sites; conserve_qns=true)
    hamiltonian = pentamer_chain_hamiltonian(
        sites,
        config.n_units;
        alpha=config.alpha,
        beta=config.beta,
    )
    state = initial_state(n_sites, config.init_mode)
    psi0 = MPS(sites, state)
    schedule = sweep_schedule(config.maxdim, config.nsweeps)
    noise = zeros(config.nsweeps)
    noise[1:min(3, config.nsweeps)] .= [1e-6, 1e-7, 1e-8][1:min(3, config.nsweeps)]
    observer = DMRGObserver()

    started_at = now(UTC)
    algorithm_start = time()
    energy, psi = dmrg(
        hamiltonian,
        psi0;
        nsweeps=config.nsweeps,
        maxdim=schedule,
        cutoff=config.cutoff,
        noise,
        observer,
        outputlevel=1,
    )
    algorithm_seconds = time() - algorithm_start

    measurement_start = time()
    energy_squared = real(inner(hamiltonian, psi, hamiltonian, psi))
    variance_raw = energy_squared - energy^2
    variance = max(variance_raw, 0.0)
    total_sz = sum(real.(expect(psi, "Sz")))
    string_order = string_order_parameter(psi, sites, config.n_units; margin=3)
    center_entropy = bipartite_entropy(copy(psi), n_sites ÷ 2)
    measurement_seconds = time() - measurement_start
    sweep_energies = real.(energies(observer))
    sweep_truncations = truncerrors(observer)
    max_truncation = isempty(sweep_truncations) ? NaN : maximum(sweep_truncations)
    final_energy_change = length(sweep_energies) >= 2 ? abs(sweep_energies[end] - sweep_energies[end - 1]) : NaN
    actual_maxdim = maximum(linkdims(psi))

    open(joinpath(config.outdir, "sweep_history.csv"), "w") do file
        println(file, "sweep,energy,max_truncation_error")
        for sweep in eachindex(sweep_energies)
            truncation = sweep <= length(sweep_truncations) ? sweep_truncations[sweep] : NaN
            @printf(file, "%d,%.16e,%.16e\n", sweep, sweep_energies[sweep], truncation)
        end
    end

    metrics = [
        "alpha" => config.alpha,
        "beta" => config.beta,
        "n_units" => config.n_units,
        "L" => n_sites,
        "energy" => energy,
        "energy_density" => energy / n_sites,
        "energy_squared" => energy_squared,
        "variance_raw" => variance_raw,
        "variance" => variance,
        "variance_per_site" => variance / n_sites,
        "total_sz" => total_sz,
        "string_order" => string_order,
        "center_entropy" => center_entropy,
        "requested_maxdim" => config.maxdim,
        "actual_maxdim" => actual_maxdim,
        "max_truncation_error" => max_truncation,
        "final_energy_change" => final_energy_change,
        "nsweeps_requested" => config.nsweeps,
        "nsweeps_completed" => length(sweep_energies),
        "cutoff" => config.cutoff,
        "threads" => Threads.nthreads(),
        "algorithm_seconds" => algorithm_seconds,
        "measurement_seconds" => measurement_seconds,
        "started_at_utc" => Dates.format(started_at, dateformat"yyyy-mm-ddTHH:MM:SS"),
        "finished_at_utc" => Dates.format(now(UTC), dateformat"yyyy-mm-ddTHH:MM:SS"),
        "init_mode" => config.init_mode,
    ]
    write_metrics(joinpath(config.outdir, "metrics.csv"), metrics)

    if config.save_mps
        jldsave(
            joinpath(config.outdir, "state.jld2");
            psi,
            sites,
            energy,
            alpha=config.alpha,
            beta=config.beta,
            n_units=config.n_units,
        )
    end
    println("CELL_SUCCESS outdir=$(config.outdir)")
end

main()
