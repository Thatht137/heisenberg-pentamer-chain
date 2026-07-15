"""
脚本 20：扫描 alpha≈0 负侧的多初态收敛。

用法：
  julia --project=. scripts/20_near_zero_multistart.jl [task_id] [beta] [nsweeps]
"""

using Pkg
Pkg.activate(dirname(@__DIR__))

include(joinpath(dirname(@__DIR__), "src", "PentamerChain.jl"))
using .PentamerChain
using ITensorMPS
using Printf

function task_grid()
    alphas = [-0.15, -0.10, -0.075, -0.05, -0.025, 0.0]
    modes = [:center, :left, :right]
    return [(alpha, mode) for alpha in alphas for mode in modes]
end

function main()
    task_id = length(ARGS) >= 1 ? parse(Int, ARGS[1]) : error("需要 task_id")
    beta = length(ARGS) >= 2 ? parse(Float64, ARGS[2]) : 0.5
    nsweeps = length(ARGS) >= 3 ? parse(Int, ARGS[3]) : 40
    tasks = task_grid()
    1 <= task_id <= length(tasks) || error("task_id 超出范围")

    alpha, initial_mode = tasks[task_id]
    N_units = 12
    L = 5 * N_units
    maxdim = 1800
    cutoff = 1e-10
    data_dir = joinpath(
        dirname(@__DIR__), "data", "near_zero_multistart", "tasks")
    mkpath(data_dir)
    outfile = joinpath(
        data_dir,
        @sprintf(
            "near_a%.3f_b%.2f_L%03d_%s.csv",
            alpha,
            beta,
            L,
            String(initial_mode),
        ),
    )
    if isfile(outfile)
        println("已存在，跳过：$outfile")
        return
    end

    energy, psi, _ = compute_sector_ground_state_hires(;
        N_units,
        alpha,
        beta,
        target_sz=1,
        maxdim,
        cutoff,
        nsweeps,
        initial_mode,
    )
    magnetization = real.(expect(psi, "Sz"))

    open(outfile, "w") do file
        println(
            file,
            "alpha,beta,L,initial_mode,site,Sz,energy,nsweeps",
        )
        for site in 1:L
            @printf(
                file,
                "%.6f,%.6f,%d,%s,%d,%.12e,%.12f,%d\n",
                alpha,
                beta,
                L,
                String(initial_mode),
                site,
                magnetization[site],
                energy,
                nsweeps,
            )
        end
    end
    @printf(
        "完成：alpha=%.3f，mode=%s，energy=%.12f\n",
        alpha,
        String(initial_mode),
        energy,
    )
end

main()
