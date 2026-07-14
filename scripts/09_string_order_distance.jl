"""
脚本 09：计算弦序随位胞距离的变化。

用法：
  julia --project=. scripts/09_string_order_distance.jl [task_id] [beta]
"""

using Pkg
Pkg.activate(dirname(@__DIR__))

include(joinpath(dirname(@__DIR__), "src", "PentamerChain.jl"))
using .PentamerChain
using Printf

function task_grid()
    alphas = [-0.50, -0.05, 0.05, 0.50]
    N_units_list = [12, 16, 20]
    return [(alpha, N_units) for N_units in N_units_list for alpha in alphas]
end

function maxdim_for_units(N_units::Int)
    settings = Dict(12 => 1000, 16 => 1500, 20 => 2000)
    return settings[N_units]
end

function main()
    task_id = if length(ARGS) >= 1
        parse(Int, ARGS[1])
    elseif haskey(ENV, "SLURM_ARRAY_TASK_ID")
        parse(Int, ENV["SLURM_ARRAY_TASK_ID"])
    else
        error("需要指定 task_id")
    end

    beta = length(ARGS) >= 2 ? parse(Float64, ARGS[2]) : 0.5
    tasks = task_grid()
    1 <= task_id <= length(tasks) ||
        error("task_id=$task_id 超出范围 1-$(length(tasks))")

    alpha, N_units = tasks[task_id]
    L = 5 * N_units
    maxdim = maxdim_for_units(N_units)
    cutoff = 1e-10
    nsweeps = 20
    margin = 2

    data_dir = joinpath(
        dirname(@__DIR__), "data", "string_order_distance", "tasks")
    mkpath(data_dir)
    outfile = joinpath(
        data_dir,
        @sprintf("a%+.2f_b%.2f_L%03d.csv", alpha, beta, L),
    )

    if isfile(outfile)
        println("已存在，跳过：$outfile")
        return
    end

    @printf(
        "Task %d/%d: alpha=%+.2f, beta=%.2f, L=%d, maxdim=%d\n",
        task_id, length(tasks), alpha, beta, L, maxdim,
    )
    flush(stdout)

    start_time = time()
    energy, psi, sites = compute_ground_state_hires(;
        N_units, alpha, beta, maxdim, cutoff, nsweeps)
    profile = string_order_distance_profile(
        psi, sites, N_units; margin)

    open(outfile, "w") do file
        println(
            file,
            "alpha,beta,L,N_units,distance_units,O_mean,O_std,O_sem,n_pairs,energy,maxdim",
        )
        for row in profile
            @printf(
                file,
                "%.6f,%.6f,%d,%d,%d,%.12f,%.12f,%.12f,%d,%.12f,%d\n",
                alpha,
                beta,
                L,
                N_units,
                row.distance_units,
                row.O_mean,
                row.O_std,
                row.O_sem,
                row.n_pairs,
                energy,
                maxdim,
            )
        end
    end

    @printf("完成：%s，耗时 %.1f 秒\n", outfile, time() - start_time)
end

main()
