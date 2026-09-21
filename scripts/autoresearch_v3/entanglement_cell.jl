"""计算五聚体链或 Heisenberg 链的基态纠缠熵。"""

using Pkg
Pkg.activate(dirname(dirname(@__DIR__)))

include(joinpath(dirname(dirname(@__DIR__)), "src", "PentamerChain.jl"))
using .PentamerChain
using Dates
using ITensors
using ITensorMPS
using Printf

function parse_args()
    length(ARGS) == 9 || error("用法: entanglement_cell.jl OUT MODEL ALPHA BETA N_UNITS MAXDIM NSWEEPS CUTOFF INIT_MODE")
    return (
        outdir=abspath(ARGS[1]),
        model=Symbol(ARGS[2]),
        alpha=parse(Float64, ARGS[3]),
        beta=parse(Float64, ARGS[4]),
        n_units=parse(Int, ARGS[5]),
        maxdim=parse(Int, ARGS[6]),
        nsweeps=parse(Int, ARGS[7]),
        cutoff=parse(Float64, ARGS[8]),
        init_mode=Symbol(ARGS[9]),
    )
end

function initial_state(total_sites::Int, mode::Symbol)
    iseven(total_sites) || error("总格点数必须为偶数")
    mode in (:center, :domain) || error("INIT_MODE 必须为 center 或 domain")
    state = [isodd(site) ? "Up" : "Dn" for site in 1:total_sites]
    if mode == :domain
        span = 2 * div(total_sites, 4)
        first = div(total_sites - span, 2) + 1
        for site in first:(first + span - 1)
            state[site] = state[site] == "Up" ? "Dn" : "Up"
        end
    end
    return state
end

function heisenberg_hamiltonian(sites)
    terms = OpSum()
    for site in 1:(length(sites) - 1)
        terms += 1.0, "Sz", site, "Sz", site + 1
        terms += 0.5, "S+", site, "S-", site + 1
        terms += 0.5, "S-", site, "S+", site + 1
    end
    return MPO(terms, sites)
end

function schedule(maxdim::Int, nsweeps::Int)
    return [sweep <= 5 ? min(maxdim, 50 * 2^(sweep - 1)) : maxdim for sweep in 1:nsweeps]
end

function entropy_profile!(psi, model::Symbol)
    rows = NamedTuple[]
    for bond in 1:(length(psi) - 1)
        entropy = bipartite_entropy(psi, bond)
        unit_cut = model == :pentamer && bond % 5 == 0 ? bond ÷ 5 : model == :heisenberg ? bond : 0
        push!(rows, (
            bond=bond,
            cut_class=mod(bond, model == :pentamer ? 5 : 1),
            unit_cut=unit_cut,
            intercell=unit_cut > 0,
            entropy=entropy,
        ))
    end
    return rows
end

function main()
    config = parse_args()
    config.model in (:pentamer, :heisenberg) || error("MODEL 必须为 pentamer 或 heisenberg")
    0.0 <= config.alpha <= 1.0 || error("禁止 alpha<0 或 alpha>1")
    0.0 <= config.beta <= 1.0 || error("beta 必须位于 [0,1]")
    iseven(config.n_units) || error("N_UNITS 必须为偶数")
    mkpath(config.outdir)

    total_sites = config.model == :pentamer ? 5 * config.n_units : config.n_units
    sites = siteinds("S=1/2", total_sites; conserve_qns=true)
    hamiltonian = config.model == :pentamer ?
        pentamer_chain_hamiltonian(sites, config.n_units; alpha=config.alpha, beta=config.beta) :
        heisenberg_hamiltonian(sites)
    psi0 = MPS(sites, initial_state(total_sites, config.init_mode))
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
    rows = entropy_profile!(psi, config.model)

    open(joinpath(config.outdir, "entropy_profile.csv"), "w") do file
        println(file, "bond,cut_class,unit_cut,intercell,entropy")
        for row in rows
            @printf(file, "%d,%d,%d,%s,%.16e\n", row.bond, row.cut_class, row.unit_cut, row.intercell, row.entropy)
        end
    end
    open(joinpath(config.outdir, "sweep_history.csv"), "w") do file
        println(file, "sweep,energy,max_truncation_error")
        for sweep in eachindex(sweep_energies)
            truncation = sweep <= length(truncations) ? truncations[sweep] : NaN
            @printf(file, "%d,%.16e,%.16e\n", sweep, sweep_energies[sweep], truncation)
        end
    end
    metrics = [
        "model" => config.model,
        "alpha" => config.alpha,
        "beta" => config.beta,
        "n_units" => config.n_units,
        "L" => total_sites,
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
        "midchain_entropy" => rows[total_sites ÷ 2].entropy,
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
    println("ENTANGLEMENT_CELL_SUCCESS outdir=$(config.outdir)")
end

main()
