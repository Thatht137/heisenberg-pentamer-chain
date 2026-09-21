"""比较失败 run 在两种时间窗下的原始谱负权。"""

using JLD2
using Printf

run_dir = abspath(ARGS[1])
output = abspath(ARGS[2])
input_file = joinpath(run_dir, "correlation.jld2")
loaded = load(input_file)
data = loaded["result"]
tlist = data[1, :]
nlist = Int.(data[2, :])
rlist = data[3, :]
corr = data[4, :] .+ im .* data[5, :]
tuniq = sort(unique(tlist))
dt = tuniq[2] - tuniq[1]
tmax = maximum(tuniq)
total_sites = maximum(nlist)
center = loaded["center_site"]
space_window = 18
first_site = max(1, center - space_window)
last_site = min(total_sites, center + space_window)
keep = findall(i -> first_site <= nlist[i] <= last_site, eachindex(nlist))
times = tlist[keep]
distances = rlist[keep]
correlations = corr[keep]
edge = [t == first(tuniq) || t == last(tuniq) ? 0.5 : 1.0 for t in times]
qvals = collect(range(pi, 1.5pi; length=13))
omegavals = collect(range(0.0, 2.0; length=81))

function calculate(kind::String, eta::Float64)
    negative = 0.0
    positive = 0.0
    minimum_value = Inf
    maximum_value = -Inf
    for q in qvals, omega in omegavals
        acc = 0.0 + 0.0im
        for k in eachindex(times)
            window = kind == "sin2" ? sin(pi * times[k] / tmax)^2 : exp(-eta * times[k])
            acc += edge[k] * cis(omega * times[k] - q * distances[k]) * correlations[k] * window * dt
        end
        value = real(acc)
        minimum_value = min(minimum_value, value)
        maximum_value = max(maximum_value, value)
        if value < 0
            negative += -value
        else
            positive += value
        end
    end
    fraction = negative / max(negative + positive, 1e-30)
    return (negative, positive, fraction, minimum_value, maximum_value)
end

mkpath(dirname(output))
open(output, "w") do io
    println(io, "window,negative_abs,positive_sum,fraction,minimum,maximum,q_min_over_pi,q_max_over_pi,omega_min,omega_max,q_points,omega_points")
    for (label, kind, eta) in (("exp_eta_0.05", "exponential", 0.05), ("exp_eta_0.10", "exponential", 0.10), ("exp_eta_0.20", "exponential", 0.20), ("exp_eta_0.30", "exponential", 0.30), ("sin2", "sin2", 0.0))
        negative, positive, fraction, minimum_value, maximum_value = calculate(kind, eta)
        @printf(io, "%s,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%d,%d\n",
            label, negative, positive, fraction, minimum_value, maximum_value,
            first(qvals) / pi, last(qvals) / pi, first(omegavals), last(omegavals), length(qvals), length(omegavals))
    end
end
println("window sensitivity written: ", output)
