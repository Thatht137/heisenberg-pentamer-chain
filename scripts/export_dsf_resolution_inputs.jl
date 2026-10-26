"""导出旧试算数据及实际坐标，供无平滑审计。"""

using JLD2
using DelimitedFiles
using SHA

function main()
    root = dirname(@__DIR__)
    outdir = length(ARGS) == 1 ? abspath(ARGS[1]) : joinpath(root, "results", "dsf_resolution_20261001")
    mkpath(outdir)
    open(joinpath(outdir, "metadata.csv"), "w") do io
        println(io, "alpha,beta,L,dt,tmin,tmax,dmrg_maxdim,tebd_maxdim,space_window,corr_sha256,spectrum_sha256")
        for alpha in (-0.5, -0.05, 0.14, 0.23, 0.33)
            stem = "a$(alpha)"
            corrpath = joinpath(root, "data", "NDSF_pentamer_alpha=$(alpha)_beta=0.5_L=40_L40_t15.jld2")
            specpath = joinpath(root, "data", "Sqw_tebd_pentamer_alpha=$(alpha)_beta=0.5_L40_t15.jld2")
            corr = load(corrpath)
            spec = load(specpath)
            writedlm(joinpath(outdir, "$(stem)_correlation.csv"), permutedims(corr["result"]), ',')
            writedlm(joinpath(outdir, "$(stem)_stored.csv"), spec["spectrum"], ',')
            writedlm(joinpath(outdir, "$(stem)_q.csv"), spec["qvals"], ',')
            writedlm(joinpath(outdir, "$(stem)_omega.csv"), spec["omegavals"], ',')
            times = sort(unique(corr["result"][1, :]))
            values = (alpha, corr["beta"], corr["total_sites"], times[2] - times[1], first(times), last(times),
                      get(corr, "dmrg_maxdim", "unknown"), get(corr, "tebd_maxdim", "unknown"), spec["space_window"],
                      bytes2hex(open(sha256, corrpath)), bytes2hex(open(sha256, specpath)))
            println(io, join(values, ','))
        end
    end
    println("Exported: ", outdir)
end

main()
