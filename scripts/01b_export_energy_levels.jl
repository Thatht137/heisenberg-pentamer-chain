"""
脚本 01b：导出单五聚体能级和自旋标签到 CSV。
扫描 alpha∈[-1,1]（101 点），输出长格式表供 Python 绘图。
"""

using Pkg
Pkg.activate(dirname(@__DIR__))

include(joinpath(dirname(@__DIR__), "src", "PentamerChain.jl"))
using .PentamerChain
using Printf

function main()
    alpha_range = range(-1.0, 1.0, length=101)
    data_dir = joinpath(dirname(@__DIR__), "data")
    mkpath(data_dir)

    outfile = joinpath(data_dir, "single_pentamer_levels.csv")
    open(outfile, "w") do f
        println(f, "alpha,level_index,energy,spin_S")
        for alpha in alpha_range
            vals, _, spins = diagonalize_pentamer(alpha)
            for j in 1:32
                @printf(f, "%.4f,%d,%.10f,%.1f\n", alpha, j, vals[j], spins[j])
            end
        end
    end

    println("已保存: $outfile ($(101*32) 行)")
end

main()
