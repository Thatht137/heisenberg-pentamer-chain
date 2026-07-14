"""
脚本 03d：加密相图 80×60 高精度版本。
相比 03c 的关键变化：
  - nsweeps: 8 → 20
  - maxdim: 400 → 1000
  - cutoff: 1e-8 → 1e-10
  - 用确定性 Néel 初态（linkdims=2，无随机性）
目的：消除 1D 切片的小幅跳跃，让曲线像文献那样平滑。

用法：
  julia --project=. scripts/03d_phase_diagram_80x60_hires.jl [task_id]
"""

using Pkg
Pkg.activate(dirname(@__DIR__))

include(joinpath(dirname(@__DIR__), "src", "PentamerChain.jl"))
using .PentamerChain
using ITensors
using ITensorMPS
using Printf

function main()
    task_id = if length(ARGS) >= 1
        parse(Int, ARGS[1])
    elseif haskey(ENV, "SLURM_ARRAY_TASK_ID")
        parse(Int, ENV["SLURM_ARRAY_TASK_ID"])
    else
        error("需要指定 task_id")
    end

    alpha_all = collect(range(-1.0, 1.0, length=81))
    filter!(x -> abs(x) > 1e-10, alpha_all)
    beta_range = range(0.05, 1.0, length=60)

    if task_id < 1 || task_id > length(alpha_all)
        error("task_id=$task_id 超出范围 [1, $(length(alpha_all))]")
    end

    alpha = alpha_all[task_id]

    # ─── 高精度 DMRG 参数 ───
    N_units = 12
    maxdim = 1000
    cutoff = 1e-10
    nsweeps = 20

    data_dir = joinpath(dirname(@__DIR__), "data", "phase_dense_80x60_hires")
    mkpath(data_dir)
    outfile = joinpath(data_dir, @sprintf("alpha_%03d.csv", task_id))

    done_betas = Set{Float64}()
    if isfile(outfile)
        for line in readlines(outfile)
            startswith(line, "alpha") && continue
            parts = split(line, ",")
            length(parts) >= 2 && push!(done_betas, parse(Float64, parts[2]))
        end
    end

    if !isfile(outfile)
        open(outfile, "w") do f
            println(f, "alpha,beta,O_str,energy")
        end
    end

    @printf("Task %03d: alpha=%.4f, %d beta points (HIRES)\n", task_id, alpha, length(beta_range))

    for (i, beta) in enumerate(beta_range)
        if any(abs(beta - b) < 1e-6 for b in done_betas)
            @printf("  [%2d/%2d] beta=%.4f — 已存在，跳过\n", i, length(beta_range), beta)
            continue
        end

        @printf("  [%2d/%2d] beta=%.4f ... ", i, length(beta_range), beta)
        t0 = time()

        energy, psi, sites = compute_ground_state_hires(;
            N_units, alpha, beta, maxdim, cutoff, nsweeps)

        O_str = string_order_parameter(psi, sites, N_units; margin=3)
        elapsed = time() - t0

        open(outfile, "a") do f
            @printf(f, "%.4f,%.4f,%.8f,%.10f\n", alpha, beta, O_str, energy)
        end

        @printf("O_str=%.6f, E=%.6f, %.1fs\n", O_str, energy, elapsed)
    end

    println("Task $task_id 完成：$outfile")
end

main()
