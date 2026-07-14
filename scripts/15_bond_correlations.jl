"""
脚本 15：计算代表参数点的最近邻键关联。

用法：
  julia --project=. scripts/15_bond_correlations.jl [task_id] [beta] [nsweeps]
"""

using Pkg
Pkg.activate(dirname(@__DIR__))

include(joinpath(dirname(@__DIR__), "src", "PentamerChain.jl"))
using .PentamerChain
using Printf

function main()
    task_id = length(ARGS) >= 1 ? parse(Int, ARGS[1]) : error("需要 task_id")
    beta = length(ARGS) >= 2 ? parse(Float64, ARGS[2]) : 0.5
    nsweeps = length(ARGS) >= 3 ? parse(Int, ARGS[3]) : 40
    alphas = [0.10, 0.14, 0.17, 0.20, 0.23, 0.27, 0.30, 0.33, 0.40, 0.50]
    1 <= task_id <= length(alphas) || error("task_id 超出范围")

    alpha = alphas[task_id]
    N_units = 20
    L = 100
    maxdim = 2000
    cutoff = 1e-10

    data_dir = joinpath(
        dirname(@__DIR__), "data", "bond_correlations")
    mkpath(data_dir)
    outfile = joinpath(
        data_dir,
        @sprintf("bond_a%.2f_b%.2f_L%03d.csv", alpha, beta, L),
    )

    if isfile(outfile)
        println("已存在，跳过：$outfile")
        return
    end

    energy, psi, sites = compute_ground_state_hires(;
        N_units, alpha, beta, maxdim, cutoff, nsweeps)
    correlations = bond_spin_correlations(psi, sites)

    labels = Dict(
        0 => "J3",
        1 => "J2_left",
        2 => "J1_left",
        3 => "J1_right",
        4 => "J2_right",
    )

    open(outfile, "w") do file
        println(file, "alpha,beta,L,bond,bond_type,SdotS,energy,nsweeps")
        for (bond, value) in enumerate(correlations)
            @printf(
                file,
                "%.6f,%.6f,%d,%d,%s,%.12f,%.12f,%d\n",
                alpha,
                beta,
                L,
                bond,
                labels[mod(bond, 5)],
                value,
                energy,
                nsweeps,
            )
        end
    end

    println("完成：$outfile")
end

main()
