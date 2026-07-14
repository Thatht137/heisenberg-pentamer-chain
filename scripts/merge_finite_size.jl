"""
合并 finite_size 扫描的 per-task CSV 文件。
输出：data/finite_size/finite_size_all.csv
"""

using Printf

function main()
    tasks_dir = joinpath(dirname(@__DIR__), "data", "finite_size", "tasks")
    outfile = joinpath(dirname(@__DIR__), "data", "finite_size", "finite_size_all.csv")

    if !isdir(tasks_dir)
        error("任务目录不存在: $tasks_dir")
    end

    files = filter(f -> endswith(f, ".csv"), readdir(tasks_dir))
    isempty(files) && error("$tasks_dir 中没有 CSV 文件")

    println("找到 $(length(files)) 个任务文件")

    rows = Tuple{Float64,Float64,Float64,String}[]  # (beta, L, alpha, line)

    for fname in files
        fpath = joinpath(tasks_dir, fname)
        for line in readlines(fpath)
            startswith(line, "alpha") && continue
            isempty(strip(line)) && continue
            parts = split(line, ",")
            length(parts) >= 8 || continue

            alpha = parse(Float64, parts[1])
            beta = parse(Float64, parts[2])
            L = parse(Float64, parts[3])  # 先解析为 Float，排序时自动处理

            push!(rows, (beta, L, alpha, line))
        end
    end

    # 排序：beta, L, alpha
    sort!(rows, by=x -> (x[1], x[2], x[3]))

    mkpath(dirname(outfile))
    open(outfile, "w") do f
        println(f, "alpha,beta,L,N_units,O_str,S_L2,energy,maxdim")
        for (_, _, _, line) in rows
            println(f, line)
        end
    end

    println("已合并 $(length(files)) 个文件，共 $(length(rows)) 行")
    println("输出: $outfile")
end

main()
