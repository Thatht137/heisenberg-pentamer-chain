"""
脚本 25：在负 alpha 低能延拓态上计算弦关联。
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

function odd_string_samples(psi, sites, N_units::Int, margin::Int)
    unit_start = margin + 1
    unit_end = N_units - margin
    rows = NamedTuple[]

    for distance in 1:2:(unit_end - unit_start)
        sign = (-1)^((distance - 1) ÷ 2)
        for unit_i in unit_start:(unit_end - distance)
            unit_j = unit_i + distance
            value = string_correlator_units(
                psi,
                sites,
                unit_i,
                unit_j,
            )
            push!(
                rows,
                (
                    distance_units=distance,
                    unit_i=unit_i,
                    unit_j=unit_j,
                    O_str=value,
                    O_envelope=sign * value,
                ),
            )
        end
    end
    return rows
end

function main()
    beta = length(ARGS) >= 1 ? parse(Float64, ARGS[1]) : 0.5
    N_units = parse(Int, get(ENV, "PENTAMER_N_UNITS", "16"))
    L = 5 * N_units
    maxdim = parse(Int, get(ENV, "PENTAMER_MAXDIM", "1500"))
    cutoff = parse(Float64, get(ENV, "PENTAMER_CUTOFF", "1e-10"))
    first_sweeps = parse(Int, get(ENV, "PENTAMER_FIRST_SWEEPS", "48"))
    continuation_sweeps = parse(
        Int,
        get(ENV, "PENTAMER_CONTINUATION_SWEEPS", "20"),
    )
    margin = parse(Int, get(ENV, "PENTAMER_STRING_MARGIN", "1"))
    alpha_text = get(
        ENV,
        "PENTAMER_NEGATIVE_ALPHAS",
        "-0.50,-0.35,-0.25,-0.15,-0.10,-0.075,-0.05",
    )
    target_text = get(
        ENV,
        "PENTAMER_STRING_TARGETS",
        "-0.50,-0.25,-0.10,-0.05",
    )
    alphas = parse.(Float64, strip.(split(alpha_text, ",")))
    targets = Set(parse.(Float64, strip.(split(target_text, ","))))
    all(target -> target in alphas, targets) ||
        error("所有测量点必须包含在延拓路径中")

    sites = siteinds("S=1/2", L; conserve_qns=true)
    psi = initial_state(sites)
    results = NamedTuple[]

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
        @printf(
            "forward: alpha=%.5f, energy=%.12f, maxlinkdim=%d\n",
            alpha,
            energy,
            maximum(linkdims(psi)),
        )
        flush(stdout)

        if alpha in targets
            samples = odd_string_samples(
                psi,
                sites,
                N_units,
                margin,
            )
            push!(
                results,
                (
                    alpha=alpha,
                    energy=energy,
                    nsweeps=nsweeps,
                    samples=samples,
                ),
            )
        end
    end

    data_dir = joinpath(
        dirname(@__DIR__),
        "data",
        "negative_string_continuation",
    )
    mkpath(data_dir)
    outfile = joinpath(
        data_dir,
        @sprintf("profiles_b%.2f_L%03d.csv", beta, L),
    )
    open(outfile, "w") do file
        println(
            file,
            "alpha,beta,L,N_units,distance_units,unit_i,unit_j,O_str,O_envelope,energy,maxdim,margin,nsweeps",
        )
        for result in results
            for row in result.samples
                @printf(
                    file,
                    "%.6f,%.6f,%d,%d,%d,%d,%d,%.12e,%.12e,%.12f,%d,%d,%d\n",
                    result.alpha,
                    beta,
                    L,
                    N_units,
                    row.distance_units,
                    row.unit_i,
                    row.unit_j,
                    row.O_str,
                    row.O_envelope,
                    result.energy,
                    maxdim,
                    margin,
                    result.nsweeps,
                )
            end
        end
    end
    println("完成：$outfile")
end

main()
