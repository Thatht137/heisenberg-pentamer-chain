"""
脚本 03b：加密相图扫描（支持 SLURM array job）。
每个 task 计算一个 alpha 值对应的所有 beta 点。

用法：
  julia --project=. scripts/03b_phase_diagram_dense.jl [task_id]

task_id 可通过命令行参数或 SLURM_ARRAY_TASK_ID 环境变量指定（1-40）。
"""

using Pkg
Pkg.activate(dirname(@__DIR__))

include(joinpath(dirname(@__DIR__), "src", "PentamerChain.jl"))
using .PentamerChain
using ITensors
using ITensorMPS
using Printf

function main()
    # ─── 确定 task_id ───
    task_id = if length(ARGS) >= 1
        parse(Int, ARGS[1])
    elseif haskey(ENV, "SLURM_ARRAY_TASK_ID")
        parse(Int, ENV["SLURM_ARRAY_TASK_ID"])
    else
        error("需要指定 task_id：通过命令行参数或 SLURM_ARRAY_TASK_ID")
    end

    # ─── 参数网格 ───
    alpha_all = collect(range(-1.0, 1.0, length=41))
    filter!(x -> abs(x) > 1e-10, alpha_all)  # 去掉 alpha=0
    beta_range = range(0.1, 1.0, length=20)

    if task_id < 1 || task_id > length(alpha_all)
        error("task_id=$task_id 超出范围 [1, $(length(alpha_all))]")
    end

    alpha = alpha_all[task_id]

    # ─── DMRG 参数 ───
    N_units = 12
    maxdim = 400
    cutoff = 1e-8
    nsweeps = 8

    # ─── 输出文件 ───
    data_dir = joinpath(dirname(@__DIR__), "data", "phase_dense")
    mkpath(data_dir)
    outfile = joinpath(data_dir, @sprintf("alpha_%02d.csv", task_id))

    # 读取已有结果（断点续算）
    done_betas = Set{Float64}()
    if isfile(outfile)
        for line in readlines(outfile)
            startswith(line, "alpha") && continue
            parts = split(line, ",")
            length(parts) >= 2 && push!(done_betas, parse(Float64, parts[2]))
        end
    end

    # 写入表头（如果文件不存在）
    if !isfile(outfile)
        open(outfile, "w") do f
            println(f, "alpha,beta,O_str,energy")
        end
    end

    @printf("Task %02d: alpha=%.4f, %d beta points\n", task_id, alpha, length(beta_range))

    for (i, beta) in enumerate(beta_range)
        if beta in done_betas
            @printf("  [%2d/%2d] beta=%.4f — 已存在，跳过\n", i, length(beta_range), beta)
            continue
        end

        @printf("  [%2d/%2d] beta=%.4f ... ", i, length(beta_range), beta)

        energy, psi, sites, _ = compute_ground_state(;
            N_units, alpha, beta, maxdim, cutoff, nsweeps,
            conserve_qns=true)

        O_str = string_order_parameter(psi, sites, N_units; margin=3)

        open(outfile, "a") do f
            @printf(f, "%.4f,%.4f,%.8f,%.10f\n", alpha, beta, O_str, energy)
        end

        @printf("O_str=%.6f, E=%.6f\n", O_str, energy)
    end

    println("Task $task_id 完成。结果保存在 $outfile")
end

main()
