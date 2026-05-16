"""
脚本 04：动力学结构因子 S(q, omega)。
使用修正向量法，建议先用小体系验证。
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
    println("动力学结构因子 S(q, omega)")
    println("=" ^ 60)

    N_units = 12
    alpha = 1.0
    beta = 0.5
    eta = 0.05

    println("计算基态：N=$N_units 个五聚体，L=$(5*N_units)...")
    E0, psi_gs, sites, H = compute_ground_state(;
        N_units, alpha, beta, maxdim=400, cutoff=1e-8, nsweeps=10)
    @printf("E_gs = %.8f\n", E0)

    q_points = range(0, 2π, length=17)
    omega_range = range(0.0, 3.0, length=31)

    println("\n在 $(length(q_points))x$(length(omega_range)) 网格上计算 S(q, omega)...")
    println("这一步可能耗时较长。")

    S_qw = compute_dsf_spectrum(psi_gs, H, sites, E0;
        q_points, omega_range, eta,
        maxdim=200, cutoff=1e-6, chunk_size=2)

    # 保存结果
    data_dir = joinpath(dirname(@__DIR__), "data")
    mkpath(data_dir)
    @save joinpath(data_dir, "dsf_spectrum.jld2") S_qw q_points omega_range alpha beta N_units eta

    println("\nS(q, omega) 最大强度：$(maximum(S_qw))")
    println("结果已保存到 data/dsf_spectrum.jld2")
    println("完成。")
end

main()
