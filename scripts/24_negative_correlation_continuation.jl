"""
脚本 24：负 alpha 区域的 Sz=0 双向参数连续关联扫描。
"""

using Pkg
Pkg.activate(dirname(@__DIR__))

include(joinpath(dirname(@__DIR__), "src", "PentamerChain.jl"))
using .PentamerChain
using ITensors
using ITensorMPS
using Printf
using Statistics

function initial_state(sites)
    state = [isodd(site) ? "Up" : "Dn" for site in eachindex(sites)]
    return MPS(sites, state)
end

function sweep_settings(nsweeps::Int, maxdim::Int; first_point::Bool)
    if !first_point
        return fill(maxdim, nsweeps), zeros(nsweeps)
    end

    schedule = [
        sweep <= 6 ? min(maxdim, 50 * 2^(sweep - 1)) : maxdim
        for sweep in 1:nsweeps
    ]
    noise = zeros(nsweeps)
    noise[1:min(3, nsweeps)] .=
        [1e-6, 1e-7, 1e-8][1:min(3, nsweeps)]
    return schedule, noise
end

function correlation_profile(psi, L::Int)
    correlations = 3 .* real.(correlation_matrix(psi, "Sz", "Sz"))
    magnetization = real.(expect(psi, "Sz"))
    connected = correlations .- 3 .* magnetization * transpose(magnetization)

    margin = max(2, L ÷ 10)
    first_site = margin + 1
    last_site = L - margin
    max_distance = min(L ÷ 2, last_site - first_site)
    rows = []

    for distance in 1:max_distance
        values = [
            connected[site, site + distance]
            for site in first_site:(last_site - distance)
        ]
        push!(
            rows,
            (
                distance=distance,
                C_mean=mean(values),
                C_std=length(values) > 1 ? std(values) : 0.0,
            ),
        )
    end
    return rows
end

function run_branch(sites, alphas, beta, branch::String)
    N_units = length(sites) ÷ 5
    L = length(sites)
    maxdim = parse(Int, get(ENV, "PENTAMER_MAXDIM", "1500"))
    cutoff = parse(Float64, get(ENV, "PENTAMER_CUTOFF", "1e-10"))
    first_sweeps = parse(Int, get(ENV, "PENTAMER_FIRST_SWEEPS", "48"))
    continuation_sweeps = parse(
        Int,
        get(ENV, "PENTAMER_CONTINUATION_SWEEPS", "20"),
    )
    psi = initial_state(sites)
    results = []

    for (index, alpha) in enumerate(alphas)
        first_point = index == 1
        nsweeps = first_point ? first_sweeps : continuation_sweeps
        schedule, noise = sweep_settings(
            nsweeps,
            maxdim;
            first_point,
        )
        H = pentamer_chain_hamiltonian(
            sites,
            N_units;
            alpha,
            beta,
        )
        energy, psi = dmrg(
            H,
            psi;
            nsweeps,
            maxdim=schedule,
            cutoff,
            noise,
            outputlevel=1,
        )
        profile = correlation_profile(psi, L)
        push!(
            results,
            (
                alpha=alpha,
                energy=energy,
                nsweeps=nsweeps,
                profile=profile,
            ),
        )
        @printf(
            "%s: alpha=%.5f, energy=%.12f, maxlinkdim=%d\n",
            branch,
            alpha,
            energy,
            maximum(linkdims(psi)),
        )
    end
    return results
end

function main()
    beta = length(ARGS) >= 1 ? parse(Float64, ARGS[1]) : 0.5
    N_units = parse(Int, get(ENV, "PENTAMER_N_UNITS", "16"))
    L = 5 * N_units
    alpha_text = get(
        ENV,
        "PENTAMER_NEGATIVE_ALPHAS",
        "-0.50,-0.35,-0.25,-0.15,-0.10,-0.075,-0.05,-0.025",
    )
    alphas = parse.(Float64, strip.(split(alpha_text, ",")))
    sites = siteinds("S=1/2", L; conserve_qns=true)

    forward = run_branch(sites, alphas, beta, "forward")
    backward = run_branch(sites, reverse(alphas), beta, "backward")

    data_dir = joinpath(
        dirname(@__DIR__),
        "data",
        "negative_correlation_continuation",
    )
    mkpath(data_dir)
    outfile = joinpath(
        data_dir,
        @sprintf("profiles_b%.2f_L%03d.csv", beta, L),
    )

    open(outfile, "w") do file
        println(
            file,
            "alpha,beta,L,branch,distance,C_mean,C_std,energy,nsweeps",
        )
        for (branch, results) in [
            ("forward", forward),
            ("backward", backward),
        ]
            for result in results
                for row in result.profile
                    @printf(
                        file,
                        "%.6f,%.6f,%d,%s,%d,%.12e,%.12e,%.12f,%d\n",
                        result.alpha,
                        beta,
                        L,
                        branch,
                        row.distance,
                        row.C_mean,
                        row.C_std,
                        result.energy,
                        result.nsweeps,
                    )
                end
            end
        end
    end
    println("完成：$outfile")
end

main()
