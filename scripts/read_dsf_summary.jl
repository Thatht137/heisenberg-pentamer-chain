using JLD2

file = joinpath("data", "dsf_spectrum.jld2")

jldopen(file, "r") do f
    println("keys = ", collect(keys(f)))

    S = f["S_qw"]
    q = f["q_points"]
    w = f["omega_range"]

    println("size(S_qw) = ", size(S))
    println("q length = ", length(q), ", omega length = ", length(w))
    println("alpha = ", f["alpha"])
    println("beta = ", f["beta"])
    println("N_units = ", f["N_units"])
    println("eta = ", f["eta"])

    m = maximum(S)
    idx = argmax(S)

    println("max = ", m)
    println("max index = ", idx)
    println("q at max = ", q[idx[1]])
    println("omega at max = ", w[idx[2]])

    println("min = ", minimum(S))
    println("has NaN = ", any(isnan, S))
    println("has Inf = ", any(isinf, S))
end
