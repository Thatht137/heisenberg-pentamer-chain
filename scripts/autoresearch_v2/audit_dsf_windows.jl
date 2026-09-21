"""审计正 alpha 原始关联的时间窗与未裁剪频谱。"""

using Pkg
Pkg.activate(dirname(dirname(@__DIR__)))

using DelimitedFiles
using JLD2
using LinearAlgebra
using Printf
using SHA

function spectrum_for(data, cutoff_time, qvals, omegavals)
    times = sort(unique(data[1, :]))
    dt = times[2] - times[1]
    selected_times = times[times .<= cutoff_time + 1e-12]
    tmax = maximum(selected_times)
    sites = sort(unique(Int.(data[2, :])))
    center = maximum(sites) ÷ 2
    corr = reshape(data[4, :] .+ im .* data[5, :], length(sites), length(times))'
    corr = corr[1:length(selected_times), :]
    distances = sites .- center
    window = sin.(pi .* selected_times ./ tmax) .^ 2
    result = zeros(Float64, length(qvals), length(omegavals))
    for (iq, q) in enumerate(qvals)
        cq = corr * exp.(-im .* q .* distances)
        for (iw, omega) in enumerate(omegavals)
            result[iq, iw] = 2 * real(sum(dt .* window .* exp.(im .* omega .* selected_times) .* cq))
        end
    end
    return result, dt, tmax
end

function main()
    length(ARGS) == 1 || error("用法: audit_dsf_windows.jl OUTDIR")
    outdir = abspath(ARGS[1])
    isdir(outdir) && !isempty(readdir(outdir)) && error("拒绝覆盖非空目录: $outdir")
    mkpath(outdir)
    root = dirname(dirname(@__DIR__))
    alphas = (0.14, 0.23, 0.33)
    cutoffs = (7.5, 10.0, 15.0)
    qvals = collect(range(0, 2pi; length=81))
    omegavals = collect(range(0, 3; length=181))
    rows = NamedTuple[]
    spectra = Dict{String, Matrix{Float64}}()
    for alpha in alphas
        input = joinpath(root, "data", "NDSF_pentamer_alpha=$(alpha)_beta=0.5_L=40_L40_t15.jld2")
        loaded = load(input)
        data = loaded["result"]
        for cutoff_time in cutoffs
            spectrum, dt, actual_tmax = spectrum_for(data, cutoff_time, qvals, omegavals)
            key = @sprintf("a%.2f_t%.1f", alpha, cutoff_time)
            spectra[key] = spectrum
            reverse_rms = norm(spectrum .- reverse(spectrum; dims=1)) / max(norm(spectrum), eps())
            q0_ratio = maximum(abs.(spectrum[1, 2:end])) / max(maximum(abs.(spectrum)), eps())
            negative_ratio = abs(minimum(spectrum)) / max(maximum(spectrum), eps())
            qpi = argmin(abs.(qvals .- pi))
            omega_mask = omegavals .>= 0.1
            peak_local = argmax(spectrum[qpi, omega_mask])
            peak_omega = omegavals[omega_mask][peak_local]
            push!(rows, (
                alpha=alpha,
                beta=0.5,
                L=40,
                dt=dt,
                tmax=actual_tmax,
                qpi_peak_omega=peak_omega,
                inversion_relative_rms=reverse_rms,
                q0_inelastic_ratio=q0_ratio,
                negative_to_positive_ratio=negative_ratio,
                raw_input_sha256=bytes2hex(open(sha256, input)),
            ))
        end
    end
    open(joinpath(outdir, "window_summary.csv"), "w") do file
        println(file, join(keys(first(rows)), ','))
        for row in rows
            println(file, join(values(row), ','))
        end
    end
    for (key, spectrum) in spectra
        writedlm(joinpath(outdir, "spectrum_$(key).csv"), spectrum, ',')
    end
    drift = Dict{String, Float64}()
    for alpha in alphas
        group = filter(row -> row.alpha == alpha, rows)
        peaks = [row.qpi_peak_omega for row in group]
        drift[@sprintf("alpha_%.2f", alpha)] = maximum(peaks) - minimum(peaks)
    end
    acceptance = Dict(
        "time_window_peak_drift" => drift,
        "time_window_pass" => all(value <= 0.05 for value in values(drift)),
        "raw_inversion_pass" => all(row.inversion_relative_rms <= 0.02 for row in rows),
        "raw_q0_pass" => all(row.q0_inelastic_ratio <= 1e-6 for row in rows),
        "raw_nonnegative_pass" => all(row.negative_to_positive_ratio <= 1e-10 for row in rows),
        "dt_half_available" => false,
        "production_dynamics_pass" => false,
        "reason" => "现有原始数据只有 dt=0.05；未满足 dt/2 强制验收",
    )
    jldsave(joinpath(outdir, "window_audit.jld2"); rows, spectra, qvals, omegavals, acceptance)
    open(joinpath(outdir, "acceptance.txt"), "w") do file
        for (key, value) in sort(collect(acceptance); by=first)
            println(file, key, "=", value)
        end
    end
    open(joinpath(outdir, "checksums.sha256"), "w") do file
        for name in sort(filter(!=("checksums.sha256"), readdir(outdir)))
            println(file, bytes2hex(open(sha256, joinpath(outdir, name))), "  ", name)
        end
    end
    println("DSF_AUDIT_SUCCESS outdir=$outdir")
end

main()
