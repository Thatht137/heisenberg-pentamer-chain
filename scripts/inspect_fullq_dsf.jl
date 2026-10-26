"""读取已完成单元或断点的范数漂移，不加载 MPS。"""

using JLD2
using Printf

outdir = only(ARGS)
for name in sort(readdir(outdir))
    startswith(name, "q") && (endswith(name, ".jld2") || endswith(name, ".checkpoint")) || continue
    jldopen(joinpath(outdir, name), "r") do file
        corr, norms, config, q = file["corr"], file["norms"], file["config"], file["q"]
        step = haskey(file, "step") ? file["step"] : length(corr) - 1
        source_norm = real(corr[1])
        drift = source_norm > 1e-20 ? maximum(abs.(norms[1:step+1] .- source_norm)) / source_norm : 0.0
        @printf("%s q/pi=%.4f t=%.2f norm_drift=%.6g\n", name, q/pi, step * config.dt, drift)
    end
end
