"""
脚本 02：五聚体链的 DMRG 基态计算。
用于验证极限情形并计算基础观测量。
"""

using Pkg
Pkg.activate(dirname(@__DIR__))

include(joinpath(dirname(@__DIR__), "src", "PentamerChain.jl"))
using .PentamerChain
using ITensors
using ITensorMPS
using Printf

function main()
    println("=" ^ 60)
    println("DMRG 基态计算：五聚体链")
    println("=" ^ 60)

    # 验证 1：近似孤立五聚体
    println("\n--- 验证：beta≈0（近似孤立五聚体）---")
    alpha = 1.0
    N_units = 4

    # 单个五聚体 ED 
    vals_ed, _, _ = diagonalize_pentamer(alpha)
    E_ed_per_unit = vals_ed[1]
    E_ed_total = N_units * E_ed_per_unit
    println("ED 参考：E_gs/unit = $E_ed_per_unit, total = $E_ed_total")

    energy, _, _, _ = compute_ground_state(;
        N_units, alpha, beta=0.001, maxdim=100, cutoff=1e-8, nsweeps=6)
    @printf("DMRG（beta≈0）：E_gs = %.8f（参考 %.8f）\n", energy, E_ed_total)

    # 验证 2：均匀 Heisenberg 链
    println("\n--- 验证：alpha=1, beta=1（均匀 Heisenberg 链）---")
    N_units_large = 12
    energy2, _, _, _ = compute_ground_state(;
        N_units=N_units_large, alpha=1.0, beta=1.0,
        maxdim=200, cutoff=1e-8, nsweeps=8)
    E_per_site = energy2 / (5 * N_units_large)
    @printf("DMRG：E/site = %.6f（Bethe ansatz 热力学极限：-0.443147）\n", E_per_site)

    # 物理参数示例
    println("\n--- 示例计算：alpha=1.0, beta=0.5 ---")
    energy3, psi3, sites3, _ = compute_ground_state(;
        N_units=12, alpha=1.0, beta=0.5,
        maxdim=400, cutoff=1e-8, nsweeps=10)
    @printf("E_gs = %.8f, E/site = %.6f\n", energy3, energy3 / 60)

    # 磁化强度分布
    Sz_profile = expect(psi3, "Sz")
    println("\nSz 分布（前 15 个格点）：")
    for i in 1:15
        @printf("  site %2d: Sz = %+.6f\n", i, Sz_profile[i])
    end

    println("\n完成。")
end

main()
