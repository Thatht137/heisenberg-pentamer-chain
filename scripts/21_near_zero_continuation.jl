"""
脚本 21：沿 alpha 参数连续推进左右边缘分支。

用法：
  julia --project=. scripts/21_near_zero_continuation.jl [beta]
"""

using Pkg
Pkg.activate(dirname(@__DIR__))

include(joinpath(dirname(@__DIR__), "src", "PentamerChain.jl"))
using .PentamerChain
using ITensors
using ITensorMPS
using Printf

function initial_mps(sites, mode::Symbol)
    L = length(sites)
    state = [isodd(site) ? "Up" : "Dn" for site in 1:L]
    flipped_site = mode == :left ? 2 : L
    state[flipped_site] = "Up"
    return MPS(sites, state)
end

function run_branch(sites, alphas, beta, mode::Symbol)
    N_units = length(sites) ÷ 5
    maxdim = 1800
    cutoff = 1e-10
    psi = initial_mps(sites, mode)
    results = []

    for (index, alpha) in enumerate(alphas)
        H = pentamer_chain_hamiltonian(
            sites,
            N_units;
            alpha,
            beta,
        )
        nsweeps = index == 1 ? 60 : 24
        schedule = index == 1 ?
            [sweep <= 6 ? min(maxdim, 50 * 2^(sweep - 1)) : maxdim
             for sweep in 1:nsweeps] :
            fill(maxdim, nsweeps)
        noise = zeros(nsweeps)
        if index == 1
            noise[1:3] .= [1e-6, 1e-7, 1e-8]
        end
        energy, psi = dmrg(
            H,
            psi;
            nsweeps,
            maxdim=schedule,
            cutoff,
            noise,
            outputlevel=1,
        )
        magnetization = real.(expect(psi, "Sz"))
        push!(
            results,
            (
                alpha=alpha,
                energy=energy,
                magnetization=magnetization,
                nsweeps=nsweeps,
            ),
        )
        @printf(
            "%s: alpha=%.5f，energy=%.12f\n",
            String(mode),
            alpha,
            energy,
        )
    end
    return results
end

function main()
    beta = length(ARGS) >= 1 ? parse(Float64, ARGS[1]) : 0.5
    N_units = 12
    L = 5 * N_units
    alphas = [
        -0.15,
        -0.125,
        -0.10,
        -0.075,
        -0.05,
        -0.0375,
        -0.025,
        -0.0125,
        -0.00625,
    ]
    sites = siteinds("S=1/2", L; conserve_qns=true)
    left_results = run_branch(sites, alphas, beta, :left)
    right_results = run_branch(sites, alphas, beta, :right)

    data_dir = joinpath(
        dirname(@__DIR__), "data", "near_zero_continuation")
    mkpath(data_dir)
    outfile = joinpath(
        data_dir,
        @sprintf("profiles_b%.2f_L%03d.csv", beta, L),
    )
    open(outfile, "w") do file
        println(
            file,
            "alpha,beta,L,branch,site,Sz,energy,nsweeps",
        )
        for (branch, results) in [
            ("left", left_results),
            ("right", right_results),
        ]
            for result in results
                for site in 1:L
                    @printf(
                        file,
                        "%.6f,%.6f,%d,%s,%d,%.12e,%.12f,%d\n",
                        result.alpha,
                        beta,
                        L,
                        branch,
                        site,
                        result.magnetization[site],
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
