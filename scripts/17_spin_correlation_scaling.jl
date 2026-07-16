"""
脚本 17：计算多尺寸实空间自旋关联。

用法：
  julia --project=. scripts/17_spin_correlation_scaling.jl [task_id] [beta] [nsweeps]
"""

using Pkg
Pkg.activate(dirname(@__DIR__))

include(joinpath(dirname(@__DIR__), "src", "PentamerChain.jl"))
using .PentamerChain
using ITensorMPS
using Printf
using Statistics

function task_grid()
    alpha_text = get(
        ENV,
        "PENTAMER_CORRELATION_ALPHAS",
        "0.14,0.23,0.33",
    )
    alphas = parse.(Float64, strip.(split(alpha_text, ",")))
    N_units_list = [8, 12, 16]
    return [
        (alpha, N_units)
        for N_units in N_units_list
        for alpha in alphas
    ]
end

function maxdim_for_units(N_units::Int)
    settings = Dict(8 => 800, 12 => 1000, 16 => 1500)
    return settings[N_units]
end

function main()
    task_id = length(ARGS) >= 1 ? parse(Int, ARGS[1]) : error("需要 task_id")
    beta = length(ARGS) >= 2 ? parse(Float64, ARGS[2]) : 0.5
    nsweeps = length(ARGS) >= 3 ? parse(Int, ARGS[3]) : 30
    tasks = task_grid()
    1 <= task_id <= length(tasks) || error("task_id 超出范围")

    alpha, N_units = tasks[task_id]
    L = 5 * N_units
    maxdim = maxdim_for_units(N_units)
    cutoff = 1e-10
    data_dir = joinpath(
        dirname(@__DIR__), "data", "spin_correlations", "tasks")
    mkpath(data_dir)
    outfile = joinpath(
        data_dir,
        @sprintf("corr_a%.2f_b%.2f_L%03d.csv", alpha, beta, L),
    )
    force_recompute = get(ENV, "FORCE_RECOMPUTE", "0") == "1"
    if isfile(outfile) && !force_recompute
        println("已存在，跳过：$outfile")
        return
    end

    energy, psi, _ = compute_ground_state_hires(;
        N_units, alpha, beta, maxdim, cutoff, nsweeps)
    correlations = 3 .* real.(correlation_matrix(psi, "Sz", "Sz"))
    magnetization = real.(expect(psi, "Sz"))
    connected = correlations .- 3 .* magnetization * transpose(magnetization)

    margin = max(2, L ÷ 10)
    first_site = margin + 1
    last_site = L - margin
    max_distance = min(L ÷ 2, last_site - first_site)

    open(outfile, "w") do file
        println(
            file,
            "alpha,beta,L,distance,C_mean,C_std,C_sem,staggered,energy,nsweeps",
        )
        for distance in 1:max_distance
            values = [
                connected[site, site + distance]
                for site in first_site:(last_site - distance)
            ]
            mean_value = mean(values)
            std_value = length(values) > 1 ? std(values) : 0.0
            staggered = (-1)^distance * mean_value
            @printf(
                file,
                "%.6f,%.6f,%d,%d,%.12e,%.12e,%.12e,%.12e,%.12f,%d\n",
                alpha,
                beta,
                L,
                distance,
                mean_value,
                std_value,
                std_value / sqrt(length(values)),
                staggered,
                energy,
                nsweeps,
            )
        end
    end
    println("完成：$outfile")
end

main()
