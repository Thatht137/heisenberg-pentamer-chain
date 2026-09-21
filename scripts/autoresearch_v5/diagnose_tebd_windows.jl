using JLD2
using LinearAlgebra

path = ARGS[1]
data = load(path)["result"]
times = data[1, :]
distances = data[3, :]
corr = data[4, :] .+ im .* data[5, :]
tmax = maximum(times)
tuniq = sort(unique(times))
dt = tuniq[2] - tuniq[1]
q = π
omegas = collect(range(0.0, 3.0; length=181))

function evaluate(label, window)
    values = Float64[]
    for omega in omegas
        acc = 0.0 + 0.0im
        for i in eachindex(corr)
            acc += exp(im * (omega * times[i] - q * distances[i])) * corr[i] * window(times[i]) * dt
        end
        push!(values, real(acc))
    end
    println(label, " min=", minimum(values), " max=", maximum(values), " negatives=", count(<(0.0), values), "/", length(values))
end

evaluate("sin2", t -> sin(π * t / tmax)^2)
for ratio in (2.0, 3.0, 4.0, 6.0)
    tau = tmax / ratio
    evaluate("gaussian_tau_tmax/$(ratio)", t -> exp(-0.5 * (t / tau)^2))
    evaluate("exponential_tau_tmax/$(ratio)", t -> exp(-t / tau))
end

function evaluate_grid(label, window; q_points::Int=81, space_window::Int=18)
    qvals = collect(range(0.0, 2π; length=q_points))
    time_index = Dict(value => index for (index, value) in enumerate(tuniq))
    cq = zeros(ComplexF64, q_points, length(tuniq))
    for index in eachindex(corr)
        abs(distances[index]) <= space_window || continue
        it = time_index[times[index]]
        for iq in eachindex(qvals)
            cq[iq, it] += exp(-im * qvals[iq] * distances[index]) * corr[index]
        end
    end

    values = zeros(Float64, q_points, length(omegas))
    for iq in eachindex(qvals), iw in eachindex(omegas)
        acc = 0.0 + 0.0im
        for it in eachindex(tuniq)
            acc += exp(im * omegas[iw] * tuniq[it]) * cq[iq, it] * window(tuniq[it]) * dt
        end
        values[iq, iw] = real(acc)
    end
    minimum_index = argmin(values)
    rows_with_negative = count(iq -> minimum(values[iq, :]) < 0.0, eachindex(qvals))
    mirrored = reverse(values; dims=1)
    symmetrized = 0.5 .* (values .+ mirrored)
    qpi_index = argmin(abs.(qvals .- π))
    mirror_rms = norm(values .- mirrored) / max(norm(values), eps())
    println(
        label,
        " min=", minimum(values),
        " max=", maximum(values),
        " negatives=", count(<(0.0), values), "/", length(values),
        " q_rows_with_negative=", rows_with_negative, "/", length(qvals),
        " min_q=", qvals[minimum_index[1]],
        " min_omega=", omegas[minimum_index[2]],
        " mirror_rms=", mirror_rms,
        " sym_min=", minimum(symmetrized),
        " sym_negatives=", count(<(0.0), symmetrized), "/", length(symmetrized),
        " qpi_min=", minimum(values[qpi_index, :]),
        " qpi_negatives=", count(<(0.0), values[qpi_index, :]), "/", length(omegas),
    )
end

if length(ARGS) >= 2 && ARGS[2] == "full"
    evaluate_grid("full_exponential_eta_0.1", t -> exp(-0.1 * t))
    evaluate_grid("full_exponential_eta_0.2", t -> exp(-0.2 * t))
end
