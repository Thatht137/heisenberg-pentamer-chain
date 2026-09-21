"""计算有效理论验证所需的指定 Sz 扇区 DMRG cell。"""

using Pkg
Pkg.activate(dirname(dirname(@__DIR__)))

include(joinpath(dirname(dirname(@__DIR__)), "src", "PentamerChain.jl"))
using .PentamerChain
using Dates
using ITensors
using ITensorMPS
using Printf

function parse_args()
    length(ARGS) == 9 || error("用法: effective_sector_cell.jl OUT ALPHA BETA N_UNITS SZ MAXDIM NSWEEPS CUTOFF INIT_MODE")
    return (
        outdir=abspath(ARGS[1]),
        alpha=parse(Float64, ARGS[2]),
        beta=parse(Float64, ARGS[3]),
        n_units=parse(Int, ARGS[4]),
        target_sz=parse(Int, ARGS[5]),
        maxdim=parse(Int, ARGS[6]),
        nsweeps=parse(Int, ARGS[7]),
        cutoff=parse(Float64, ARGS[8]),
        init_mode=Symbol(ARGS[9]),
    )
end

function initial_state(total_sites::Int, target_sz::Int, mode::Symbol)
    iseven(total_sites) || error("本任务只接受偶数总格点")
    mode in (:center, :left, :right, :domain) || error("INIT_MODE 必须为 center、left、right 或 domain")
    state = [isodd(site) ? "Up" : "Dn" for site in 1:total_sites]
    if mode == :domain
        target_sz == 0 || error("domain 初态只用于 Sz=0")
        span = 2 * div(total_sites, 4)
        first = div(total_sites - span, 2) + 1
        for site in first:(first + span - 1)
            state[site] = state[site] == "Up" ? "Dn" : "Up"
        end
        return state
    end
    if target_sz > 0
        candidates = collect(2:2:total_sites)
        mode == :center && sort!(candidates; by=site -> abs(site - (total_sites + 1) / 2))
        mode == :right && reverse!(candidates)
        for site in candidates[1:target_sz]
            state[site] = "Up"
        end
    elseif target_sz < 0
        candidates = collect(1:2:total_sites)
        mode == :center && sort!(candidates; by=site -> abs(site - (total_sites + 1) / 2))
        mode == :right && reverse!(candidates)
        for site in candidates[1:(-target_sz)]
            state[site] = "Dn"
        end
    end
    return state
end

function schedule(maxdim::Int, nsweeps::Int)
    return [sweep <= 5 ? min(maxdim, 50 * 2^(sweep - 1)) : maxdim for sweep in 1:nsweeps]
end

function main()
    config = parse_args()
    0.0 <= config.alpha <= 1.0 || error("禁止 alpha<0 或 alpha>1")
    0.0 <= config.beta <= 1.0 || error("beta 必须位于 [0,1]")
    config.target_sz in (0, 1) || error("本任务只计算 Sz=0 或 Sz=1")
    iseven(config.n_units) || error("N_UNITS 必须为偶数")
    mkpath(config.outdir)

    total_sites = 5 * config.n_units
    sites = siteinds("S=1/2", total_sites; conserve_qns=true)
    hamiltonian = pentamer_chain_hamiltonian(sites, config.n_units; alpha=config.alpha, beta=config.beta)
    psi0 = MPS(sites, initial_state(total_sites, config.target_sz, config.init_mode))
    noise = zeros(config.nsweeps)
    noise[1:min(3, config.nsweeps)] .= [1e-6, 1e-7, 1e-8][1:min(3, config.nsweeps)]
    observer = DMRGObserver()

    started_at = now(UTC)
    algorithm_start = time()
    energy, psi = dmrg(
        hamiltonian,
        psi0;
        nsweeps=config.nsweeps,
        maxdim=schedule(config.maxdim, config.nsweeps),
        cutoff=config.cutoff,
        noise,
        observer,
        outputlevel=1,
    )
    algorithm_seconds = time() - algorithm_start
    energy_squared = real(inner(hamiltonian, psi, hamiltonian, psi))
    variance_raw = energy_squared - energy^2
    variance = max(variance_raw, 0.0)
    total_sz = sum(real.(expect(psi, "Sz")))
    sweep_energies = real.(energies(observer))
    truncations = truncerrors(observer)

    open(joinpath(config.outdir, "sweep_history.csv"), "w") do file
        println(file, "sweep,energy,max_truncation_error")
        for sweep in eachindex(sweep_energies)
            truncation = sweep <= length(truncations) ? truncations[sweep] : NaN
            @printf(file, "%d,%.16e,%.16e\n", sweep, sweep_energies[sweep], truncation)
        end
    end
    metrics = [
        "alpha" => config.alpha,
        "beta" => config.beta,
        "n_units" => config.n_units,
        "L" => total_sites,
        "target_sz" => config.target_sz,
        "energy" => energy,
        "energy_density" => energy / total_sites,
        "variance" => variance,
        "variance_per_site" => variance / total_sites,
        "total_sz" => total_sz,
        "requested_maxdim" => config.maxdim,
        "actual_maxdim" => maximum(linkdims(psi)),
        "max_truncation_error" => isempty(truncations) ? NaN : maximum(truncations),
        "final_energy_change" => length(sweep_energies) >= 2 ? abs(sweep_energies[end] - sweep_energies[end - 1]) : NaN,
        "nsweeps_completed" => length(sweep_energies),
        "cutoff" => config.cutoff,
        "threads" => Threads.nthreads(),
        "algorithm_seconds" => algorithm_seconds,
        "started_at_utc" => Dates.format(started_at, dateformat"yyyy-mm-ddTHH:MM:SS"),
        "finished_at_utc" => Dates.format(now(UTC), dateformat"yyyy-mm-ddTHH:MM:SS"),
        "init_mode" => config.init_mode,
    ]
    open(joinpath(config.outdir, "metrics.csv"), "w") do file
        println(file, "metric,value")
        for (key, value) in metrics
            println(file, key, ",", value)
        end
    end
    println("SECTOR_CELL_SUCCESS outdir=$(config.outdir)")
end

main()
