"""
脚本 06 server 版：把五聚体链 TEBD 关联函数变换为 S^zz(q, omega)。
参数从 PENTAMER_* 环境变量读取。
"""

using JLD2
using LinearAlgebra
using DelimitedFiles
using Printf

const ALPHA = parse(Float64, get(ENV, "PENTAMER_ALPHA", "1.0"))
const BETA = parse(Float64, get(ENV, "PENTAMER_BETA", "0.5"))
const N_UNITS = parse(Int, get(ENV, "PENTAMER_N_UNITS", "24"))
const Q_POINTS = parse(Int, get(ENV, "PENTAMER_Q_POINTS", "200"))
const OMEGA_POINTS = parse(Int, get(ENV, "PENTAMER_OMEGA_POINTS", "400"))
const Q_MIN = 0.0
const Q_MAX = 2π
const OMEGA_MIN = 0.0
const OMEGA_MAX = parse(Float64, get(ENV, "PENTAMER_OMEGA_MAX", "3.0"))
const SPACE_WINDOW = parse(Int, get(ENV, "PENTAMER_SPACE_WINDOW", "30"))
const TIME_WINDOW = lowercase(strip(get(ENV, "PENTAMER_TIME_WINDOW", "sin2")))
const WINDOW_ETA = parse(Float64, get(ENV, "PENTAMER_WINDOW_ETA", "0.1"))
const MAP_U0 = 5.0
const OUTPUT_TAG = replace(
    strip(get(ENV, "PENTAMER_OUTPUT_TAG", "")),
    r"[^A-Za-z0-9_.-]" => "_",
)
const OUTPUT_SUFFIX = isempty(OUTPUT_TAG) ? "" : "_$(OUTPUT_TAG)"

function default_input_file()
    total_sites = 5 * N_UNITS
    return joinpath(
        dirname(@__DIR__),
        "data",
        "NDSF_pentamer_alpha=$(ALPHA)_beta=$(BETA)_L=$(total_sites)$(OUTPUT_SUFFIX).jld2",
    )
end

function time_window(time::Real, tmax::Real; kind::AbstractString=TIME_WINDOW, eta::Real=WINDOW_ETA)
    if kind == "sin2"
        return sin(π * time / tmax)^2
    elseif kind == "exponential"
        eta > 0 || error("指数时间窗要求 eta > 0")
        return exp(-eta * time)
    end
    error("不支持的时间窗：$(kind)")
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

function fourier_transform_tebd(;
    input_file::AbstractString=default_input_file(),
    q_points::Int=Q_POINTS,
    omega_points::Int=OMEGA_POINTS,
    q_min::Real=Q_MIN,
    q_max::Real=Q_MAX,
    omega_min::Real=OMEGA_MIN,
    omega_max::Real=OMEGA_MAX,
    space_window::Int=SPACE_WINDOW,
    window_kind::AbstractString=TIME_WINDOW,
    window_eta::Real=WINDOW_ETA,
    map_u0::Real=MAP_U0,
)
    if !isfile(input_file)
        error("找不到输入文件：$(input_file)。请先运行 05_tebd_pentamer_server.jl。")
    end

    loaded = load(input_file)
    data = loaded["result"]

    tlist = data[1, :]
    nlist = Int.(data[2, :])
    total_sites = maximum(nlist)
    center = haskey(loaded, "center_site") ? loaded["center_site"] : div(total_sites, 2)
    if size(data, 1) >= 5
        rlist = data[3, :]
        corr = data[4, :] .+ im .* data[5, :]
    else
        rlist = nlist .- center
        corr = data[3, :] .+ im .* data[4, :]
    end
    tuniq = sort(unique(tlist))
    first(tuniq) == 0.0 || error("关联数据缺少 t=0，不能执行生产傅里叶变换")
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
    println("Time window = ", window_kind, ", eta = ", window_eta)

    qvals = collect(range(q_min, q_max; length=q_points))
    omegavals = collect(range(omega_min, omega_max; length=omega_points))
    spectrum = zeros(Float64, q_points, omega_points)

    for iq in 1:q_points
        q = qvals[iq]
        @printf("q progress: %d/%d\n", iq, q_points)
        flush(stdout)

        for iw in 1:omega_points
            omega = omegavals[iw]
            acc = 0.0 + 0.0im

            for idx in eachindex(corr)
                site = nlist[idx]
                if site < first(sites) || site > last(sites)
                    continue
                end

                time = tlist[idx]
                distance = rlist[idx]
                phase = exp(im * (omega * time - q * distance))
                edge_weight = time == first(tuniq) || time == last(tuniq) ? 0.5 : 1.0
                acc += edge_weight * phase * corr[idx] *
                       time_window(time, tmax; kind=window_kind, eta=window_eta) * dt
            end

            spectrum[iq, iw] = real(acc)
        end
    end

    raw_spectrum = copy(spectrum)
    spectrum .= max.(raw_spectrum, 0.0)
    mapped = map_intensity(spectrum; u0=map_u0)

    data_dir = joinpath(dirname(@__DIR__), "data")
    mkpath(data_dir)

    output_file = joinpath(
        data_dir,
        "Sqw_tebd_pentamer_alpha=$(ALPHA)_beta=$(BETA)$(OUTPUT_SUFFIX).jld2",
    )
    csv_file = joinpath(
        data_dir,
        "Sqw_tebd_pentamer_alpha=$(ALPHA)_beta=$(BETA)$(OUTPUT_SUFFIX).csv",
    )
    raw_csv_file = joinpath(
        data_dir,
        "Sqw_tebd_pentamer_alpha=$(ALPHA)_beta=$(BETA)_raw$(OUTPUT_SUFFIX).csv",
    )

    jldsave(output_file;
        spectrum,
        raw_spectrum,
        mapped,
        qvals,
        omegavals,
        input_file,
        space_window,
        window_kind,
        window_eta,
        t0_included=true,
        time_integration="trapezoid",
        map_u0,
        output_tag=OUTPUT_TAG,
    )
    writedlm(csv_file, mapped, ',')
    writedlm(raw_csv_file, raw_spectrum, ',')

    println("Fourier transform finished.")
    println("Spectrum saved to ", output_file)
    println("Mapped CSV saved to ", csv_file)
    println("Raw CSV saved to ", raw_csv_file)

    return output_file
end

if abspath(PROGRAM_FILE) == @__FILE__
    fourier_transform_tebd()
end
