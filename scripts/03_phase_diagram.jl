"""
脚本 03：相图扫描。
在 (alpha, beta) 参数空间上计算弦序参量。
"""

using Pkg
Pkg.activate(dirname(@__DIR__))

include(joinpath(dirname(@__DIR__), "src", "PentamerChain.jl"))
using .PentamerChain
using ITensors
using ITensorMPS
using Printf
using JLD2

function main()
    println("=" ^ 60)
    println("相图扫描：弦序参量")
    println("=" ^ 60)

    alpha_range = range(-1.0, 1.0, length=11)
    beta_range = range(0.1, 1.0, length=10)
    N_units = 12 # 
    maxdim = 400 #
    cutoff = 1e-8
    nsweeps = 8

    results = Dict{Tuple{Float64,Float64}, Float64}()

    total = length(alpha_range) * length(beta_range)
    count = 0

    for beta in beta_range
        for alpha in alpha_range
            count += 1
            @printf("[%3d/%3d] alpha=%.2f, beta=%.2f ... ", count, total, alpha, beta)

            _, psi, sites, _ = compute_ground_state(;
                N_units, alpha, beta, maxdim, cutoff, nsweeps,
                conserve_qns=true)

            O_str = string_order_parameter(psi, sites, N_units; margin=3)
            results[(alpha, beta)] = O_str
            @printf("O_str = %.6f\n", O_str)
        end
    end

    # 保存结果
    data_dir = joinpath(dirname(@__DIR__), "data")
    mkpath(data_dir)
    @save joinpath(data_dir, "phase_diagram.jld2") results alpha_range beta_range

    println("\n结果已保存到 data/phase_diagram.jld2")
    println("完成。")
end

main()
