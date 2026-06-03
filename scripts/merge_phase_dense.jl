"""
合并 data/phase_dense/alpha_*.csv 为单个 data/phase_diagram_dense.csv。
"""

using Printf

function main()
    data_dir = joinpath(dirname(@__DIR__), "data", "phase_dense")
    outfile = joinpath(dirname(@__DIR__), "data", "phase_diagram_dense.csv")

    files = filter(f -> endswith(f, ".csv"), readdir(data_dir))
    if isempty(files)
        error("data/phase_dense/ 中没有 CSV 文件")
    end

    rows = Tuple{Float64,Float64,String}[]

    for fname in files
        for line in readlines(joinpath(data_dir, fname))
            startswith(line, "alpha") && continue
            isempty(strip(line)) && continue
            parts = split(line, ",")
            length(parts) >= 4 || continue
            a = parse(Float64, parts[1])
            b = parse(Float64, parts[2])
            push!(rows, (a, b, line))
        end
    end

    sort!(rows, by=x -> (x[2], x[1]))

    open(outfile, "w") do f
        println(f, "alpha,beta,O_str,energy")
        for (_, _, line) in rows
            println(f, line)
        end
    end

    println("已合并 $(length(files)) 个文件，共 $(length(rows)) 行 → $outfile")
end

main()
