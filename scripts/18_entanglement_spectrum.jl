"""
脚本 18：计算中心五种切口的纠缠谱。

用法：
  julia --project=. scripts/18_entanglement_spectrum.jl [task_id] [beta] [nsweeps]
"""

using Pkg
Pkg.activate(dirname(@__DIR__))

include(joinpath(dirname(@__DIR__), "src", "PentamerChain.jl"))
using .PentamerChain
using ITensors
using ITensorMPS
using Printf

function schmidt_probabilities(psi, bond::Int)
    orthogonalize!(psi, bond)
    left_indices = if bond == 1
        (siteind(psi, bond),)
    else
        (linkind(psi, bond - 1), siteind(psi, bond))
    end
    _, singular, _, _ = svd(psi[bond], left_indices)
    spectrum_index = first(inds(singular))
    values = Float64[]
    quantum_numbers = Float64[]
    global_index = 1
    for sector in space(spectrum_index)
        sector_qn = first(sector)
        sector_dimension = last(sector)
        for _ in 1:sector_dimension
            push!(values, singular[global_index, global_index])
            push!(quantum_numbers, val(sector_qn, "Sz") / 2)
            global_index += 1
        end
    end
    probabilities = abs2.(values)
    order = sortperm(probabilities; rev=true)
    probabilities = probabilities[order]
    quantum_numbers = quantum_numbers[order]
    return probabilities ./ sum(probabilities), quantum_numbers
end

function main()
    task_id = length(ARGS) >= 1 ? parse(Int, ARGS[1]) : error("需要 task_id")
    beta = length(ARGS) >= 2 ? parse(Float64, ARGS[2]) : 0.5
    nsweeps = length(ARGS) >= 3 ? parse(Int, ARGS[3]) : 30
    alphas = [-0.50, -0.05, 0.14, 0.33]
    1 <= task_id <= length(alphas) || error("task_id 超出范围")

    alpha = alphas[task_id]
    N_units = 16
    L = 5 * N_units
    maxdim = 1500
    cutoff = 1e-10
    data_dir = joinpath(
        dirname(@__DIR__), "data", "entanglement_spectrum")
    mkpath(data_dir)
    outfile = joinpath(
        data_dir,
        @sprintf("spectrum_a%.2f_b%.2f_L%03d.csv", alpha, beta, L),
    )
    force_recompute = get(ENV, "FORCE_RECOMPUTE", "0") == "1"
    if isfile(outfile) && !force_recompute
        println("已存在，跳过：$outfile")
        return
    end

    energy, psi, _ = compute_ground_state_hires(;
        N_units, alpha, beta, maxdim, cutoff, nsweeps)
    center = L ÷ 2
    bonds = (center - 2):(center + 2)

    open(outfile, "w") do file
        println(
            file,
            "alpha,beta,L,bond,bond_class,level,schmidt_sz,probability,entanglement_energy,energy",
        )
        for bond in bonds
            probabilities, quantum_numbers = schmidt_probabilities(
                psi,
                bond,
            )
            for level in 1:min(16, length(probabilities))
                probability = probabilities[level]
                @printf(
                    file,
                    "%.6f,%.6f,%d,%d,%d,%d,%.1f,%.12e,%.12f,%.12f\n",
                    alpha,
                    beta,
                    L,
                    bond,
                    mod(bond, 5),
                    level,
                    quantum_numbers[level],
                    probability,
                    -log(probability),
                    energy,
                )
            end
        end
    end
    println("完成：$outfile")
end

main()
