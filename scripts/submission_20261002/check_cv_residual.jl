"""显式构造 CV 残差，核对保存解与截断误差。"""

using ITensors, ITensorMPS, JLD2, LinearAlgebra, TOML, SHA
include(joinpath(@__DIR__, "..", "..", "src", "PentamerChain.jl"))
using .PentamerChain

BLAS.set_num_threads(1)
const START_TIME = time()

file_hash(path) = bytes2hex(open(sha256, path))

function checkpoint_budget(stage)
    println(stage, ": elapsed=", round(time() - START_TIME; digits=2),
            " peak_rss_bytes=", Sys.maxrss())
    flush(stdout)
    time() - START_TIME < 570 || error("本地核验超过时间预算")
end

function stable_norm(state)
    gauged = deepcopy(state)
    orthogonalize!(gauged, 1)
    return norm(gauged[1])
end

function difference_norm(a, b)
    return stable_norm(add(a, -b; alg="directsum"))
end

function verify_residual(H, x, b, coefficient, maxdim)
    source_norm = stable_norm(b)
    source_norm > 0 || error("源向量范数为零")
    checkpoint_budget("exact apply")
    hx = apply(H, x; alg="naive", truncate=false)
    exact_residual = add(coefficient * x, -hx, -b; alg="directsum")
    orthogonalize!(exact_residual, 1)
    exact_value = norm(exact_residual[1]) / source_norm
    checkpoint_budget("exact residual done")
    rows = Dict{String,Any}[]
    for cutoff in (1e-12, 1e-16)
        started = time()
        approximate_hx = apply(H, x; alg="naive", cutoff, maxdim)
        apply_error = difference_norm(approximate_hx, hx) / source_norm
        residual = add(coefficient * x, -approximate_hx, -b; alg="directsum")
        before_truncation = deepcopy(residual)
        truncate!(residual; cutoff, maxdim)
        add_error = difference_norm(residual, before_truncation) / source_norm
        value = stable_norm(residual) / source_norm
        actual_error = difference_norm(residual, exact_residual) / source_norm
        push!(rows, Dict(
            "cutoff" => cutoff, "maxdim" => maxdim,
            "relative_residual" => value,
            "apply_relative_error" => apply_error,
            "sum_relative_error" => add_error,
            "triangle_error_bound" => apply_error + add_error,
            "actual_relative_error" => actual_error,
            "elapsed_seconds" => time() - started,
        ))
        checkpoint_budget("cutoff $cutoff done")
        GC.gc()
    end
    return Dict(
        "source_norm" => source_norm,
        "relative_residual_no_truncation" => exact_value,
        "no_truncation_apply_maxdim" => maxlinkdim(hx),
        "no_truncation_residual_maxdim" => maxlinkdim(exact_residual),
        "truncation_checks" => rows,
        "accepted_under_1e_minus5" => exact_value < 1e-5,
        "norm_method" => "explicit direct-sum residual; QR gauge; center-tensor Frobenius norm",
    )
end

function smoke()
    sites = siteinds("S=1/2", 10)
    H = pentamer_chain_hamiltonian(sites, 2; alpha=0.23, beta=0.5)
    dense_h = reshape(Array(prod(H), prime.(sites)..., sites...), 1024, 1024)
    eigensystem = eigen(Hermitian(dense_h))
    ground = eigensystem.vectors[:, 1]
    energy = eigensystem.values[1]
    source_operator = OpSum()
    for j in 1:10
        source_operator += (-1.0)^j / sqrt(10), "Sz", j
    end
    dense_o = reshape(Array(prod(MPO(source_operator, sites)), prime.(sites)..., sites...), 1024, 1024)
    b = dense_o * ground
    coefficient = energy + 0.1 + 0.1im
    x = (coefficient * I - dense_h) \ b
    x_mps = MPS(ITensor(x, sites...), sites; cutoff=0.0)
    b_mps = MPS(ITensor(b, sites...), sites; cutoff=0.0)
    result = verify_residual(H, x_mps, b_mps, coefficient, 128)
    dense_residual = norm(coefficient * x - dense_h * x - b) / norm(b)
    result["dense_relative_residual"] = dense_residual
    result["relative_intensity_error"] = abs(inner(b_mps, x_mps) - dot(b, x)) / abs(dot(b, x))
    result["smoke_pass"] = result["relative_residual_no_truncation"] < 1e-10 &&
        result["relative_intensity_error"] < 1e-10
    result["L"] = 10
    return result
end

function saved_run(run_dir, eta, maxdim)
    ground_path = joinpath(run_dir, "ground_state.jld2")
    source_path = joinpath(run_dir, "source_state.jld2")
    solution_path = joinpath(run_dir, "checkpoint_latest.jld2")
    ground = load(ground_path)
    source = load(source_path)
    saved = load(solution_path)
    sites = ground["sites"]
    x, b = saved["solution"], source["source"]
    all(siteind(x, j) == sites[j] == siteind(b, j) for j in eachindex(sites)) ||
        error("保存态站点索引不匹配")
    saved["q_over_pi"] == source["q_over_pi"] || error("保存动量不匹配")
    H = pentamer_chain_hamiltonian(sites, ground["n_units"];
                                  alpha=ground["alpha"], beta=ground["beta"])
    coefficient = ground["energy"] + saved["omega"] + im * eta
    checkpoint_budget("saved states loaded")
    result = verify_residual(H, x, b, coefficient, maxdim)
    result["run_dir"] = abspath(run_dir)
    result["L"] = length(sites)
    result["alpha"] = ground["alpha"]
    result["beta"] = ground["beta"]
    result["eta"] = eta
    result["omega"] = saved["omega"]
    result["q_over_pi"] = saved["q_over_pi"]
    result["reported_relative_residual"] = saved["relative_residual"]
    result["reported_intensity"] = saved["intensity"]
    result["recomputed_intensity"] = -imag(inner(b, x)) / pi
    result["saved_solution_maxdim"] = maxlinkdim(x)
    result["solution_representation"] = "full complex correction vector; ((omega+E0+i*eta)I-H)x=b"
    result["source_definition"] = "sum_j exp(i*q*j) Sz_j ground / sqrt(L); stored historical source"
    result["input_sha256"] = Dict(basename(path) => file_hash(path)
                                  for path in (ground_path, source_path, solution_path))
    return result
end

function main()
    length(ARGS) in (2, 4) || error("参数: --smoke OUTDIR 或 RUN_DIR OUTDIR ETA MAXDIM")
    outdir = abspath(ARGS[2])
    isdir(outdir) && !isempty(readdir(outdir)) && error("拒绝覆盖非空输出目录")
    mkpath(outdir)
    result = ARGS[1] == "--smoke" ? smoke() :
        saved_run(abspath(ARGS[1]), parse(Float64, ARGS[3]), parse(Int, ARGS[4]))
    result["elapsed_seconds"] = time() - START_TIME
    result["peak_rss_bytes"] = Int(Sys.maxrss())
    result["julia_version"] = string(VERSION)
    result["julia_threads"] = Threads.nthreads()
    result["blas_threads"] = BLAS.get_num_threads()
    result["script_sha256"] = file_hash(@__FILE__)
    result["hamiltonian_sha256"] = file_hash(joinpath(@__DIR__, "..", "..", "src", "hamiltonian.jl"))
    result["new_correction_vector_solve"] = false
    open(joinpath(outdir, "verification.toml"), "w") do io
        TOML.print(io, result)
    end
    println("verification written: ", joinpath(outdir, "verification.toml"))
end

main()
