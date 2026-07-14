"""
脚本 08：计算沿链纠缠熵分布。
针对指定的 (α, β, L) 参数点，计算所有 bond 的纠缠熵。

用法：
  julia --project=. scripts/08_entanglement_profile.jl <alpha> <beta> <L>

示例：
  julia --project=. scripts/08_entanglement_profile.jl 0.25 0.5 60
"""

using Pkg
Pkg.activate(dirname(@__DIR__))

include(joinpath(dirname(@__DIR__), "src", "PentamerChain.jl"))
using .PentamerChain
using ITensors
using ITensorMPS
using Printf

function main()
    if length(ARGS) < 3
        error("用法: julia scripts/08_entanglement_profile.jl <alpha> <beta> <L>")
    end

    alpha = parse(Float64, ARGS[1])
    beta = parse(Float64, ARGS[2])
    L = parse(Int, ARGS[3])
    nsweeps = length(ARGS) >= 4 ? parse(Int, ARGS[4]) : 40

    @assert L % 5 == 0 "L must be multiple of 5"
    N_units = L ÷ 5

    # 根据 L 选择 maxdim
    maxdim_map = Dict(40 => 800, 60 => 1000, 80 => 1500, 100 => 2000)
    maxdim = get(maxdim_map, L, 1000)
    cutoff = 1e-10

    data_dir = joinpath(dirname(@__DIR__), "data", "entanglement_profiles")
    mkpath(data_dir)
    outfile = joinpath(
        data_dir,
        @sprintf("profile_a%.4f_b%.4f_L%03d.csv", alpha, beta, L),
    )
    force_recompute = get(ENV, "FORCE_RECOMPUTE", "0") == "1"

    if isfile(outfile) && !force_recompute
        println("已存在，跳过：$outfile")
        return
    end

    @printf("计算沿链纠缠熵分布\n")
    @printf("参数: α=%.4f, β=%.4f, L=%d, maxdim=%d\n", alpha, beta, L, maxdim)
    flush(stdout)

    t0 = time()

    # DMRG 求基态
    energy, psi, sites = compute_ground_state_hires(;
        N_units, alpha, beta, maxdim, cutoff, nsweeps)

    @printf("基态能量: E=%.10f\n", energy)
    flush(stdout)

    # 计算所有 bond 的纠缠熵
    @printf("计算纠缠熵分布...\n")
    flush(stdout)

    S_profile = Float64[]
    for bond in 1:(L-1)
        S = bipartite_entropy(psi, bond)
        push!(S_profile, S)
    end

    elapsed = time() - t0

    # 输出文件
    open(outfile, "w") do f
        println(f, "bond,S")
        for (bond, S) in enumerate(S_profile)
            @printf(f, "%d,%.10f\n", bond, S)
        end
    end

    @printf("完成! 用时 %.1f 秒\n", elapsed)
    @printf("输出: %s\n", outfile)
    flush(stdout)
end

main()
