"""L=40 两个自旋扇区的能隙及预算对照。"""

include(joinpath(dirname(@__DIR__), "src", "PentamerChain.jl"))
using .PentamerChain
using ITensors
using ITensorMPS
using JLD2
using LinearAlgebra
using TOML
using Printf

function solve_sector(alpha, target_sz, maxdim, cutoff, seed)
    if isnothing(seed)
        energy, state, sites = compute_sector_ground_state_hires(; N_units=8, alpha, beta=0.5,
            target_sz, maxdim, cutoff, nsweeps=24)
    else
        state = deepcopy(seed)
        sites = siteinds(state)
        hamiltonian = pentamer_chain_hamiltonian(sites, 8; alpha, beta=0.5)
        energy, state = dmrg(hamiltonian, state; nsweeps=10, maxdim, cutoff,
            eigsolve_krylovdim=8, eigsolve_maxiter=4, outputlevel=1)
    end
    hamiltonian = pentamer_chain_hamiltonian(sites, 8; alpha, beta=0.5)
    variance = max(real(inner(hamiltonian, state, hamiltonian, state)) - energy^2, 0.0) / 40
    for attempt in 1:3
        variance <= 1e-10 && break
        println("GAP_REFINE alpha=$(alpha) Sz=$(target_sz) variance=$(variance)")
        flush(stdout)
        energy, state = dmrg(hamiltonian, state; nsweeps=20, maxdim, cutoff,
            eigsolve_krylovdim=8, eigsolve_maxiter=4, outputlevel=1)
        variance = max(real(inner(hamiltonian, state, hamiltonian, state)) - energy^2, 0.0) / 40
    end
    variance <= 1e-10 || error("能隙扇区基态方差未达标")
    abs(sum(expect(state, "Sz")) - target_sz) < 1e-8 || error("总 Sz 扇区不符")
    return energy, state, variance
end

function main()
    length(ARGS) == 1 || error("参数：OUTDIR")
    outdir = abspath(only(ARGS))
    mkpath(outdir)
    BLAS.set_num_threads(1)
    rows = Dict{String, Any}[]
    for alpha in (0.5, -0.5)
        energies = Dict{Tuple{Int, Int}, Float64}()
        variances = Dict{Tuple{Int, Int}, Float64}()
        for target_sz in (0, 1)
            seed = nothing
            if target_sz == 0
                path = alpha > 0 ? joinpath(dirname(outdir), "L40_positive", "ground.jld2") :
                    joinpath(outdir, "negative_seed.jld2")
                if isfile(path)
                    saved = load(path)
                    saved["config"].alpha == alpha && saved["config"].beta == 0.5 &&
                        saved["config"].n_units == 8 || error("能隙种子模型不符")
                    seed = saved["ground"]
                end
            end
            for (maxdim, cutoff) in ((512, 1e-12), (768, 1e-13))
                path = joinpath(outdir, "alpha$(alpha)_Sz$(target_sz)_chi$(maxdim).jld2")
                if isfile(path)
                    saved = load(path)
                    energy, seed, variance = saved["energy"], saved["state"], saved["variance"]
                else
                    energy, seed, variance = solve_sector(alpha, target_sz, maxdim, cutoff, seed)
                    jldsave(path; alpha, target_sz, maxdim, cutoff, energy, state=seed, variance)
                end
                energies[(target_sz, maxdim)] = energy
                variances[(target_sz, maxdim)] = variance
                @printf("GAP_SECTOR alpha=%.1f Sz=%d maxdim=%d E=%.15f variance=%.6g\n",
                    alpha, target_sz, maxdim, energy, variance)
                flush(stdout)
            end
        end
        gap512 = energies[(1, 512)] - energies[(0, 512)]
        gap768 = energies[(1, 768)] - energies[(0, 768)]
        drift = abs(gap512 - gap768)
        gap768 > 0 && drift < 1e-6 || error("能隙预算对照未通过")
        push!(rows, Dict{String, Any}("alpha" => alpha, "beta" => 0.5, "L" => 40,
            "gap512" => gap512, "gap768" => gap768, "budget_drift" => drift,
            "energy_sz0" => energies[(0, 768)], "energy_sz1" => energies[(1, 768)],
            "variance_sz0" => variances[(0, 768)], "variance_sz1" => variances[(1, 768)],
            "window_fwhm_T60" => 5.566229513 / 60,
            "gap_smaller_than_window_fwhm" => gap768 < 5.566229513 / 60))
    end
    open(joinpath(outdir, "gap_results.toml"), "w") do io
        TOML.print(io, Dict{String, Any}("cases" => rows, "julia_version" => string(VERSION),
            "method" => "sector DMRG, joint bond-dimension and cutoff comparison",
            "rigorous_error_bound" => false, "thermodynamic_extrapolation" => false))
    end
    println("SPIN_GAP_SUCCESS ", outdir)
end

main()
