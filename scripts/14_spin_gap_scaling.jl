"""
脚本 14：计算指定参数的自旋能隙。

用法：
  julia --project=. scripts/14_spin_gap_scaling.jl [task_id] [beta] [nsweeps]
"""

using Pkg
Pkg.activate(dirname(@__DIR__))

include(joinpath(dirname(@__DIR__), "src", "PentamerChain.jl"))
using .PentamerChain
using Printf

function task_grid()
    alpha_text = get(
        ENV,
        "PENTAMER_SPIN_GAP_ALPHAS",
        "0.10,0.20,0.25,0.30,0.40,0.50",
    )
    alphas = parse.(Float64, strip.(split(alpha_text, ",")))
    N_units_list = [8, 12, 16]
    return [(alpha, N_units) for N_units in N_units_list for alpha in alphas]
end

function maxdim_for_units(N_units::Int)
    settings = Dict(8 => 800, 12 => 1000, 16 => 1500)
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

    data_dir = joinpath(
        dirname(@__DIR__), "data", "spin_gap", "tasks")
    mkpath(data_dir)
    outfile = joinpath(
        data_dir,
        @sprintf("a%.2f_b%.2f_L%03d.csv", alpha, beta, L),
    )
    force_recompute = get(ENV, "FORCE_RECOMPUTE", "0") == "1"

    if isfile(outfile) && !force_recompute
        println("已存在，跳过：$outfile")
        return
    end

    @printf(
        "Task %d/%d: alpha=%.2f, beta=%.2f, L=%d, nsweeps=%d\n",
        task_id, length(tasks), alpha, beta, L, nsweeps,
    )

    start_time = time()
    energy_sz0, _, _ = compute_sector_ground_state_hires(;
        N_units,
        alpha,
        beta,
        target_sz=0,
        maxdim,
        cutoff,
        nsweeps,
    )
    energy_sz1, _, _ = compute_sector_ground_state_hires(;
        N_units,
        alpha,
        beta,
        target_sz=1,
        maxdim,
        cutoff,
        nsweeps,
    )
    gap = energy_sz1 - energy_sz0

    open(outfile, "w") do file
        println(
            file,
            "alpha,beta,L,N_units,E_sz0,E_sz1,spin_gap,maxdim,nsweeps",
        )
        @printf(
            file,
            "%.6f,%.6f,%d,%d,%.12f,%.12f,%.12f,%d,%d\n",
            alpha,
            beta,
            L,
            N_units,
            energy_sz0,
            energy_sz1,
            gap,
            maxdim,
            nsweeps,
        )
    end

    @printf(
        "完成：gap=%.10f，耗时 %.1f 秒，输出 %s\n",
        gap,
        time() - start_time,
        outfile,
    )
end

main()
