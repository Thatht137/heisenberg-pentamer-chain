"""
脚本 07：有限尺寸标度扫描。

扫描 N_units ∈ [8,12,16,20]（L=40,60,80,100），
alpha 网格 ~74 点（密集覆盖 ±[0.15,0.35]，疏覆盖两侧），
每个 task 写单行 CSV：alpha,beta,L,N_units,O_str,S_L2,energy,maxdim

用法：
  julia --project=. scripts/07_finite_size_scan.jl [task_id] [beta]
  task_id 映射到 (L_idx, alpha_idx)，beta 默认 0.5
"""

using Pkg
Pkg.activate(dirname(@__DIR__))

include(joinpath(dirname(@__DIR__), "src", "PentamerChain.jl"))
using .PentamerChain
using ITensors
using ITensorMPS
using Printf

function build_alpha_grid()
    # 密集区：覆盖 ±[0.15, 0.35]，step=0.01
    dense_neg = collect(range(-0.35, -0.15; step=0.01))
    dense_pos = collect(range(0.15, 0.35; step=0.01))

    # 疏区：两侧背景 + 跳过 |α|<0.05 退化带
    sparse_far_neg = collect(range(-1.0, -0.4; step=0.05))
    sparse_near_neg = collect(range(-0.09, -0.05; step=0.02))
    sparse_near_pos = collect(range(0.05, 0.09; step=0.02))
    sparse_far_pos = collect(range(0.4, 1.0; step=0.05))

    alpha_all = vcat(sparse_far_neg, dense_neg, sparse_near_neg,
                     sparse_near_pos, dense_pos, sparse_far_pos)
    sort!(alpha_all)
    return alpha_all
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

    alpha_grid = build_alpha_grid()
    N_alpha = length(alpha_grid)

    L_list = [8, 12, 16, 20]
    maxdim_list = [800, 1000, 1500, 2000]

    # task_id -> (L_idx, alpha_idx)
    L_idx = div(task_id - 1, N_alpha) + 1
    alpha_idx = mod(task_id - 1, N_alpha) + 1

    if L_idx < 1 || L_idx > length(L_list)
        error("task_id=$task_id 超出范围：需 1-$(N_alpha * length(L_list))")
    end

    N_units = L_list[L_idx]
    L = 5 * N_units
    alpha = alpha_grid[alpha_idx]
    maxdim = maxdim_list[L_idx]
    cutoff = 1e-10
    nsweeps = 20

    # 输出目录
    data_dir = joinpath(dirname(@__DIR__), "data", "finite_size", "tasks")
    mkpath(data_dir)

    outfile = joinpath(data_dir, @sprintf("L%02d_b%.2f_a%03d.csv", N_units, beta, alpha_idx))

    # Resume：已存在则跳过
    if isfile(outfile)
        @printf("Task %d: L=%d, α=%.4f, β=%.2f — 已存在，跳过\n", task_id, L, alpha, beta)
        flush(stdout)
        return
    end

    @printf("Task %d: L=%d (N_units=%d), α=%.4f, β=%.2f, maxdim=%d\n",
            task_id, L, N_units, alpha, beta, maxdim)
    flush(stdout)

    t0 = time()

    # DMRG 求基态
    energy, psi, sites = compute_ground_state_hires(;
        N_units, alpha, beta, maxdim, cutoff, nsweeps)

    # 弦序参量
    O_str = string_order_parameter(psi, sites, N_units; margin=3)

    # 纠缠熵（链中央）
    S_L2 = bipartite_entropy(psi, L ÷ 2)

    elapsed = time() - t0

    # 写单行 CSV
    open(outfile, "w") do f
        println(f, "alpha,beta,L,N_units,O_str,S_L2,energy,maxdim")
        @printf(f, "%.6f,%.6f,%d,%d,%.10f,%.10f,%.12f,%d\n",
                alpha, beta, L, N_units, O_str, S_L2, energy, maxdim)
    end

    @printf("  → O_str=%.6f, S(L/2)=%.6f, E=%.8f, %.1fs\n",
            O_str, S_L2, energy, elapsed)
    flush(stdout)

    println("Task $task_id 完成：$outfile")
    flush(stdout)
end

main()
