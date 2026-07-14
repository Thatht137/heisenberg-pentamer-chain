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
    spectrum_dimension = dim(first(inds(singular)))
    values = [
        singular[index, index]
        for index in 1:spectrum_dimension
    ]
    probabilities = sort(abs2.(values); rev=true)
    return probabilities ./ sum(probabilities)
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
    if isfile(outfile)
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
            "alpha,beta,L,bond,bond_class,level,probability,entanglement_energy,energy",
        )
        for bond in bonds
            probabilities = schmidt_probabilities(psi, bond)
            for level in 1:min(16, length(probabilities))
                probability = probabilities[level]
                @printf(
                    file,
                    "%.6f,%.6f,%d,%d,%d,%d,%.12e,%.12f,%.12f\n",
                    alpha,
                    beta,
                    L,
                    bond,
                    mod(bond, 5),
                    level,
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
