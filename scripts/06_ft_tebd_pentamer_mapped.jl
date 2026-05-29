"""
脚本 06：把五聚体链 TEBD 关联函数变换为 S^zz(q, omega)。

输入来自 scripts/05_tebd_pentamer.jl 的 JLD2 文件。
"""

using Pkg
Pkg.activate(dirname(@__DIR__))

using JLD2
using LinearAlgebra
using DelimitedFiles
using Printf

const ALPHA = 1.0
const BETA = 0.5
const N_UNITS = 24
const Q_POINTS = 200
const OMEGA_POINTS = 400
const Q_MIN = 0.0
const Q_MAX = 2π
const OMEGA_MIN = 0.0
const OMEGA_MAX = 3.0
const SPACE_WINDOW = 30
const MAP_U0 = 5.0

function default_input_file()
    total_sites = 5 * N_UNITS
    return joinpath(
        dirname(@__DIR__),
        "data",
        "NDSF_pentamer_alpha=$(ALPHA)_beta=$(BETA)_L=$(total_sites).jld2",
    )
end

function time_window(time::Real, tmax::Real)
    return sin(π * time / tmax)^2
end

function map_intensity(spectrum::AbstractArray; u0::Real=MAP_U0)
    mapped = similar(spectrum)
    logu0 = log10(u0)

    for i in eachindex(spectrum)
        if spectrum[i] <= u0
            mapped[i] = spectrum[i]
        else
            mapped[i] = u0 + log10(spectrum[i]) - logu0
        end
    end

    return mapped
end

function save_heatmap_if_available(qvals, omegavals, spectrum, save_path::AbstractString)
    try
        @eval using Plots
        plt = Plots.heatmap(
            qvals,
            omegavals,
            spectrum',
            xlabel="q",
            ylabel="omega",
            title="Szz(q, omega)",
            color=:viridis,
            xticks=([0, π / 2, π, 3π / 2, 2π], ["0", "π/2", "π", "3π/2", "2π"]),
        )
        Plots.savefig(plt, save_path)
        println("Heatmap saved to ", save_path)
        return true
    catch err
        println("Plots 未安装或不可用，跳过图片保存。")
        println("错误信息：", err)
        return false
    end
end

function fourier_transform_tebd(;
    input_file::AbstractString=default_input_file(),
    q_points::Int=Q_POINTS,
    omega_points::Int=OMEGA_POINTS,
    q_min::Real=Q_MIN,
    q_max::Real=Q_MAX,
    omega_min::Real=OMEGA_MIN,
    omega_max::Real=OMEGA_MAX,
    space_window::Int=SPACE_WINDOW,
    map_u0::Real=MAP_U0,
)
    if !isfile(input_file)
        error("找不到输入文件：$input_file。请先运行 scripts/05_tebd_pentamer.jl。")
    end

    loaded = load(input_file)
    data = loaded["result"]

    tlist = data[1, :]
    nlist = Int.(data[2, :])
    corr = data[3, :] .+ im .* data[4, :]

    total_sites = maximum(nlist)
    center = haskey(loaded, "center_site") ? loaded["center_site"] : div(total_sites, 2)
    tuniq = sort(unique(tlist))
    dt = tuniq[2] - tuniq[1]
    tmax = maximum(tuniq)

    first_site = max(1, center - space_window)
    last_site = min(total_sites, center + space_window)
    sites = first_site:last_site

    println("Correlation data loaded.")
    println("Total points = ", length(corr))
    println("L = ", total_sites, ", center = ", center)
    println("dt = ", dt, ", tmax = ", tmax)
    println("Using spatial window: ", sites)

    qvals = collect(range(q_min, q_max; length=q_points))
    omegavals = collect(range(omega_min, omega_max; length=omega_points))
    spectrum = zeros(Float64, q_points, omega_points)

    for iq in 1:q_points
        q = qvals[iq]
        @printf("q progress: %d/%d\n", iq, q_points)

        for iw in 1:omega_points
            omega = omegavals[iw]
            acc = 0.0 + 0.0im

            for idx in eachindex(corr)
                site = nlist[idx]
                if site < first(sites) || site > last(sites)
                    continue
                end

                time = tlist[idx]
                phase = exp(im * (omega * time - q * (site - center)))
                acc += phase * corr[idx] * time_window(time, tmax) * dt
            end

            spectrum[iq, iw] = real(acc)
        end
    end

    spectrum .= max.(spectrum, 0.0)
    mapped = map_intensity(spectrum; u0=map_u0)

    data_dir = joinpath(dirname(@__DIR__), "data")
    fig_dir = joinpath(dirname(@__DIR__), "figures")
    mkpath(data_dir)
    mkpath(fig_dir)

    output_file = joinpath(data_dir, "Sqw_tebd_pentamer_alpha=$(ALPHA)_beta=$(BETA).jld2")
    csv_file = joinpath(data_dir, "Sqw_tebd_pentamer_alpha=$(ALPHA)_beta=$(BETA).csv")
    fig_file = joinpath(fig_dir, "Sqw_tebd_pentamer_alpha=$(ALPHA)_beta=$(BETA).png")

    jldsave(output_file;
        spectrum,
        mapped,
        qvals,
        omegavals,
        input_file,
        space_window,
        map_u0,
    )
    writedlm(csv_file, mapped, ',')

    println("Fourier transform finished.")
    println("Spectrum saved to ", output_file)
    println("Mapped CSV saved to ", csv_file)
    save_heatmap_if_available(qvals, omegavals, mapped, fig_file)

    return output_file
end

fourier_transform_tebd()
