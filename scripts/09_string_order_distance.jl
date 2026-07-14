"""
脚本 09：计算弦序随位胞距离的变化。

用法：
  julia --project=. scripts/09_string_order_distance.jl [task_id] [beta] [nsweeps]
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
    nsweeps = length(ARGS) >= 3 ? parse(Int, ARGS[3]) : 30
    tasks = task_grid()
    1 <= task_id <= length(tasks) ||
        error("task_id=$task_id 超出范围 1-$(length(tasks))")

    alpha, N_units = tasks[task_id]
    L = 5 * N_units
    maxdim = maxdim_for_units(N_units)
    cutoff = 1e-10
    margin = 3
    force_recompute = get(ENV, "FORCE_RECOMPUTE", "0") == "1"

    data_dir = joinpath(
        dirname(@__DIR__), "data", "string_order_distance", "pairs")
    mkpath(data_dir)
    outfile = joinpath(
        data_dir,
        @sprintf("a%+.2f_b%.2f_L%03d.csv", alpha, beta, L),
    )

    if isfile(outfile) && !force_recompute
        println("已存在，跳过：$outfile")
        return
    end

    @printf(
        "Task %d/%d: alpha=%+.2f, beta=%.2f, L=%d, maxdim=%d, nsweeps=%d\n",
        task_id, length(tasks), alpha, beta, L, maxdim, nsweeps,
    )
    flush(stdout)

    start_time = time()
    energy, psi, sites = compute_ground_state_hires(;
        N_units, alpha, beta, maxdim, cutoff, nsweeps)
    samples = string_order_distance_samples(
        psi, sites, N_units; margin)

    open(outfile, "w") do file
        println(
            file,
            "alpha,beta,L,N_units,distance_units,unit_i,unit_j,O_str,energy,maxdim,margin,nsweeps",
        )
        for row in samples
            @printf(
                file,
                "%.6f,%.6f,%d,%d,%d,%d,%d,%.12f,%.12f,%d,%d,%d\n",
                alpha,
                beta,
                L,
                N_units,
                row.distance_units,
                row.unit_i,
                row.unit_j,
                row.O_str,
                energy,
                maxdim,
                margin,
                nsweeps,
            )
        end
    end

    @printf("完成：%s，耗时 %.1f 秒\n", outfile, time() - start_time)
end

main()
