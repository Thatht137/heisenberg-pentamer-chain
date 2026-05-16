"""
脚本 01：单个五聚体的精确对角化。
扫描 alpha = J2/J1，并按总自旋分类能级。
"""

using Pkg
Pkg.activate(dirname(@__DIR__))

include(joinpath(dirname(@__DIR__), "src", "PentamerChain.jl"))
using .PentamerChain
using LinearAlgebra
using Printf

function main()
    println("=" ^ 60)
    println("单个五聚体精确对角化")
    println("=" ^ 60)

    # 测试情形：alpha = 1
    println("\n--- alpha = 1.0（均匀 5 格点链）---")
    vals, _, spins = diagonalize_pentamer(1.0)
    levels = classify_states(vals, spins)

    println("能级（E/J1，总自旋 S，简并度）：")
    for (E, S, deg) in levels
        @printf("  E = %8.5f,  S = %.1f,  deg = %d\n", E, S, deg)
    end
    println("\n基态能量：$(vals[1])")
    println("开边界均匀 5 格点反铁磁链参考值：-1.92789...")

    # 扫描 alpha
    println("\n--- 能级扫描：alpha 属于 [-1, 1] ---")
    alpha_range = range(-1.0, 1.0, length=41)
    all_energies = zeros(length(alpha_range), 32)

    for (i, alpha) in enumerate(alpha_range)
        vals_i, _, _ = diagonalize_pentamer(alpha)
        all_energies[i, :] = vals_i
    end

    # 输出若干点的基态自旋
    println("\n基态自旋扇区随 alpha 的变化：")
    for (i, alpha) in enumerate(alpha_range)
        if i % 10 == 1 || i == length(alpha_range)
            vals_i, _, spins_i = diagonalize_pentamer(alpha)
            gs_spin = spins_i[1]
            @printf("  alpha = %5.2f: E_gs = %8.5f, S_gs = %.1f\n", alpha, vals_i[1], gs_spin)
        end
    end

    # 保存数据
    data_dir = joinpath(@__DIR__, "..", "data")
    mkpath(data_dir)

    open(joinpath(data_dir, "single_pentamer_energies.dat"), "w") do f
        println(f, "# alpha  E1  E2  ...  E32")
        for (i, alpha) in enumerate(alpha_range)
            print(f, @sprintf("%.4f", alpha))
            for j in 1:32
                print(f, @sprintf(" %.8f", all_energies[i, j]))
            end
            println(f)
        end
    end

    println("\n数据已保存到 data/single_pentamer_energies.dat")
    println("完成。")
end

main()
