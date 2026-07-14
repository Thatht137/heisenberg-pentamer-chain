"""
脚本 16：计算候选中间区域的静态自旋结构因子。

用法：
  julia --project=. scripts/16_static_structure_factor.jl [task_id] [beta] [nsweeps] [N_units]
"""

using Pkg
Pkg.activate(dirname(@__DIR__))

include(joinpath(dirname(@__DIR__), "src", "PentamerChain.jl"))
using .PentamerChain
using ITensorMPS
using LinearAlgebra
using Printf

function main()
    task_id = length(ARGS) >= 1 ? parse(Int, ARGS[1]) : error("需要 task_id")
    beta = length(ARGS) >= 2 ? parse(Float64, ARGS[2]) : 0.5
    nsweeps = length(ARGS) >= 3 ? parse(Int, ARGS[3]) : 40
    N_units = length(ARGS) >= 4 ? parse(Int, ARGS[4]) : 20
    alphas = [0.14, 0.23, 0.33]
    1 <= task_id <= length(alphas) || error("task_id 超出范围")

    alpha = alphas[task_id]
    L = 5 * N_units
    maxdim = 2000
    cutoff = 1e-10

    data_dir = joinpath(dirname(@__DIR__), "data", "static_structure_factor")
    mkpath(data_dir)
    outfile = joinpath(
        data_dir,
        @sprintf("Sq_a%.2f_b%.2f_L%03d.csv", alpha, beta, L),
    )
    if isfile(outfile)
        println("已存在，跳过：$outfile")
        return
    end

    energy, psi, _ = compute_ground_state_hires(;
        N_units, alpha, beta, maxdim, cutoff, nsweeps)

    margin = max(1, L ÷ 10)
    selected = (margin + 1):(L - margin)
    full_correlations = real.(correlation_matrix(psi, "Sz", "Sz"))
    correlations = full_correlations[selected, selected]
    magnetization = real.(expect(psi, "Sz"))[selected]
    connected = correlations .- magnetization * transpose(magnetization)

    positions = collect(selected)
    q_values = range(0.0, 2pi; length=401)
    structure_factor = Float64[]
    for q in q_values
        phases = exp.(im .* q .* positions)
        value = 3 * real(dot(phases, connected * phases)) / length(selected)
        push!(structure_factor, value)
    end

    open(outfile, "w") do file
        println(file, "alpha,beta,L,q,Sq,energy,nsweeps")
        for (q, value) in zip(q_values, structure_factor)
            @printf(
                file,
                "%.6f,%.6f,%d,%.12f,%.12f,%.12f,%d\n",
                alpha,
                beta,
                L,
                q,
                value,
                energy,
                nsweeps,
            )
        end
    end

    peak = argmax(structure_factor[2:(end - 1)]) + 1
    @printf(
        "完成：%s，主峰 q/pi=%.4f\n",
        outfile,
        q_values[peak] / pi,
    )
end

main()
