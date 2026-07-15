"""
脚本 19：计算总 Sz=1 扇区的边缘磁化。

用法：
  julia --project=. scripts/19_edge_magnetization.jl [task_id] [beta] [nsweeps]
"""

using Pkg
Pkg.activate(dirname(@__DIR__))

include(joinpath(dirname(@__DIR__), "src", "PentamerChain.jl"))
using .PentamerChain
using ITensorMPS
using Printf

function task_grid()
    alphas = [-0.50, -0.05, 0.14, 0.33]
    N_units_list = [8, 12, 16]
    return [
        (alpha, N_units)
        for N_units in N_units_list
        for alpha in alphas
    ]
end

function maxdim_for_units(N_units::Int)
    settings = Dict(8 => 1000, 12 => 1500, 16 => 2000)
    return settings[N_units]
end

function main()
    task_id = length(ARGS) >= 1 ? parse(Int, ARGS[1]) : error("需要 task_id")
    beta = length(ARGS) >= 2 ? parse(Float64, ARGS[2]) : 0.5
    nsweeps = length(ARGS) >= 3 ? parse(Int, ARGS[3]) : 35
    tasks = task_grid()
    1 <= task_id <= length(tasks) || error("task_id 超出范围")

    alpha, N_units = tasks[task_id]
    L = 5 * N_units
    maxdim = maxdim_for_units(N_units)
    cutoff = 1e-10
    data_dir = joinpath(
        dirname(@__DIR__), "data", "edge_magnetization", "tasks")
    mkpath(data_dir)
    outfile = joinpath(
        data_dir,
        @sprintf("edge_a%.2f_b%.2f_L%03d.csv", alpha, beta, L),
    )
    if isfile(outfile)
        println("已存在，跳过：$outfile")
        return
    end

    energy, psi, _ = compute_sector_ground_state_hires(;
        N_units,
        alpha,
        beta,
        target_sz=1,
        maxdim,
        cutoff,
        nsweeps,
    )
    magnetization = real.(expect(psi, "Sz"))
    left_cumulative = cumsum(magnetization)
    right_cumulative = reverse(cumsum(reverse(magnetization)))

    open(outfile, "w") do file
        println(
            file,
            "alpha,beta,L,site,Sz,left_cumulative,right_cumulative,energy,nsweeps",
        )
        for site in 1:L
            @printf(
                file,
                "%.6f,%.6f,%d,%d,%.12e,%.12e,%.12e,%.12f,%d\n",
                alpha,
                beta,
                L,
                site,
                magnetization[site],
                left_cumulative[site],
                right_cumulative[site],
                energy,
                nsweeps,
            )
        end
    end
    @printf(
        "完成：%s，总 Sz=%.8f\n",
        outfile,
        sum(magnetization),
    )
end

main()
