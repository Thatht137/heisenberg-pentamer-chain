"""导出服务器部分关联，用于跨环境核验，不加载 MPS。"""

using JLD2
using DelimitedFiles
using SHA
using TOML

length(ARGS) == 2 || error("参数：INPUT_DIR OUTPUT_DIR")
input, output = abspath.(ARGS)
mkpath(output)
energy, variance, config = jldopen(joinpath(input, "ground.jld2"), "r") do file
    file["energy"], file["variance"], file["config"]
end
cells = Dict{String, Any}[]
for index in 1:config.q_points
    name = "q$(lpad(index, 3, '0'))"
    complete = joinpath(input, name * ".jld2")
    checkpoint = complete * ".checkpoint"
    path = isfile(complete) ? complete : checkpoint
    isfile(path) || continue
    q, corr, norms, step = jldopen(path, "r") do file
        file["config"] == config || error("断点模型不匹配")
        values = file["corr"]
        count = haskey(file, "step") ? file["step"] : length(values) - 1
        file["q"], values[1:count+1], file["norms"][1:count+1], count
    end
    times = collect(0:step) .* config.dt
    open(joinpath(output, name * "_correlation.csv"), "w") do io
        println(io, "time,real_corr,imag_corr,norm_squared")
        writedlm(io, hcat(times, real.(corr), imag.(corr), norms), ',')
    end
    push!(cells, Dict("name" => name, "q" => q, "t_reached" => times[end],
        "checkpoint_sha256" => bytes2hex(open(sha256, path)), "source_file" => basename(path)))
end
metadata = Dict{String, Any}(string(key) => value for (key, value) in pairs(config))
merge!(metadata, Dict("L" => 5 * config.n_units, "energy" => energy,
    "variance_per_site" => variance, "julia_version" => string(VERSION),
    "partial_only" => true, "cells" => cells))
open(joinpath(output, "partial_metadata.toml"), "w") do io
    TOML.print(io, metadata)
end
println("PARTIAL_EXPORT_SUCCESS cells=$(length(cells)) ", output)
