"""
脚本 05 server 版：用 TEBD 计算五聚体链的实空间-时间关联函数。
参数从 PENTAMER_* 环境变量读取，便于服务器上不改代码跑多组参数。
"""

using Pkg
Pkg.activate(dirname(@__DIR__))

include(joinpath(dirname(@__DIR__), "src", "PentamerChain.jl"))
using .PentamerChain
using ITensors
using ITensorMPS
using JLD2
using Printf

const N_UNITS = parse(Int, get(ENV, "PENTAMER_N_UNITS", "24"))
const ALPHA = parse(Float64, get(ENV, "PENTAMER_ALPHA", "1.0"))
const BETA = parse(Float64, get(ENV, "PENTAMER_BETA", "0.5"))
const TSTEP = parse(Float64, get(ENV, "PENTAMER_TSTEP", "0.01"))
const N_STEPS = parse(Int, get(ENV, "PENTAMER_N_STEPS", "4000"))
const DMRG_MAXDIM = parse(Int, get(ENV, "PENTAMER_DMRG_MAXDIM", "500"))
const TEBD_MAXDIM = parse(Int, get(ENV, "PENTAMER_TEBD_MAXDIM", "500"))
const DMRG_CUTOFF = parse(Float64, get(ENV, "PENTAMER_DMRG_CUTOFF", "1e-10"))
const TEBD_CUTOFF = parse(Float64, get(ENV, "PENTAMER_TEBD_CUTOFF", "1e-10"))
const NSWEEPS = parse(Int, get(ENV, "PENTAMER_NSWEEPS", "30"))
const OUTPUT_TAG = replace(
    strip(get(ENV, "PENTAMER_OUTPUT_TAG", "")),
    r"[^A-Za-z0-9_.-]" => "_",
)
const OUTPUT_SUFFIX = isempty(OUTPUT_TAG) ? "" : "_$(OUTPUT_TAG)"

function pentamer_bonds(n_units::Int; alpha::Real, beta::Real)
    j1 = 1.0
    j2 = alpha * j1
    j3 = beta * j1
    bonds = Tuple{Int, Int, Float64}[]

    for unit in 1:n_units
        s1 = 5 * (unit - 1) + 1
        s2 = s1 + 1
        s3 = s1 + 2
        s4 = s1 + 3
        s5 = s1 + 4

        append!(bonds, [(s1, s2, j2), (s2, s3, j1), (s3, s4, j1), (s4, s5, j2)])

        if unit < n_units
            push!(bonds, (s5, s5 + 1, j3))
        end
    end

    return bonds
end

function heisenberg_gate(sites, i::Int, j::Int, coupling::Real, tstep::Real)
    s1 = sites[i]
    s2 = sites[j]
    h = coupling * (
        op("Sz", s1) * op("Sz", s2) +
        0.5 * op("S+", s1) * op("S-", s2) +
        0.5 * op("S-", s1) * op("S+", s2)
    )
    return exp(-im * tstep / 2 * h)
end

function pentamer_tebd_gates(sites, n_units::Int; alpha::Real, beta::Real, tstep::Real)
    gates = ITensor[]
    for (i, j, coupling) in pentamer_bonds(n_units; alpha, beta)
        push!(gates, heisenberg_gate(sites, i, j, coupling, tstep))
    end

    append!(gates, reverse(gates))
    return gates
end

function local_sz_mpo(sites, site::Int)
    os = OpSum()
    os += 1.0, "Sz", site
    return MPO(os, sites)
end

function calculate_dynamics_pentamer(;
    n_units::Int=N_UNITS,
    alpha::Real=ALPHA,
    beta::Real=BETA,
    tstep::Real=TSTEP,
    n_steps::Int=N_STEPS,
    dmrg_maxdim::Int=DMRG_MAXDIM,
    tebd_maxdim::Int=TEBD_MAXDIM,
    dmrg_cutoff::Real=DMRG_CUTOFF,
    tebd_cutoff::Real=TEBD_CUTOFF,
    nsweeps::Int=NSWEEPS,
)
    total_sites = 5 * n_units
    center = div(total_sites, 2)

    println("=" ^ 60)
    println("五聚体链 TEBD 动力学计算 (server 版)")
    println("=" ^ 60)
    println("N_units = ", n_units)
    println("Total sites L = ", total_sites)
    println("alpha = J2/J1 = ", alpha)
    println("beta  = J3/J1 = ", beta)
    println("DMRG maxdim = ", dmrg_maxdim, ", cutoff = ", dmrg_cutoff, ", sweeps = ", nsweeps)
    println("TEBD maxdim = ", tebd_maxdim, ", cutoff = ", tebd_cutoff)
    println("tstep = ", tstep, ", n_steps = ", n_steps)
    flush(stdout)

    energy, psi_gs, sites, _ = compute_ground_state(;
        N_units=n_units,
        alpha,
        beta,
        maxdim=dmrg_maxdim,
        cutoff=dmrg_cutoff,
        nsweeps,
    )

    @printf("\nGround state energy = %.12f\n", energy)
    println("Total Sz = ", sum(expect(psi_gs, "Sz")))
    flush(stdout)

    gates = pentamer_tebd_gates(sites, n_units; alpha, beta, tstep)
    psi0 = deepcopy(psi_gs)

    sz_center = local_sz_mpo(sites, center)
    sp_psi = noprime(apply(sz_center, psi0))

    sz_ops = [local_sz_mpo(sites, site) for site in 1:total_sites]
    data = Matrix{Float64}(undef, 5, n_steps * total_sites)
    col = 1

    data_dir = joinpath(dirname(@__DIR__), "data")
    mkpath(data_dir)
    checkpoint_file = joinpath(
        data_dir,
        "CKPT_pentamer_alpha=$(alpha)_beta=$(beta)_L=$(total_sites)$(OUTPUT_SUFFIX).jld2",
    )

    start_step = 1
    if isfile(checkpoint_file)
        println("\n检测到 checkpoint，尝试恢复...")
        ckpt = load(checkpoint_file)
        parameters_match =
            ckpt["alpha"] == alpha &&
            ckpt["beta"] == beta &&
            ckpt["n_steps"] == n_steps &&
            get(ckpt, "tstep", NaN) == tstep &&
            get(ckpt, "tebd_maxdim", -1) == tebd_maxdim &&
            get(ckpt, "tebd_cutoff", NaN) == tebd_cutoff
        if parameters_match
            saved_step = ckpt["last_step"]
            saved_data = ckpt["data"]
            println("Checkpoint at step $(saved_step)/$(n_steps)，重新演化到断点...")
            for step in 1:saved_step
                sp_psi = apply(gates, sp_psi; cutoff=tebd_cutoff, maxdim=tebd_maxdim)
                if step % 100 == 0
                    @printf("  快进 step %d/%d\n", step, saved_step)
                end
            end
            data[:, 1:saved_step*total_sites] .= saved_data[:, 1:saved_step*total_sites]
            col = saved_step * total_sites + 1
            start_step = saved_step + 1
            println("恢复完成，从 step $(start_step) 继续。")
        else
            println("Checkpoint 参数不匹配，从头开始。")
        end
    end

    t_start = time_ns()
    println("\nComputing C(n,t) = <GS|Sz_n exp[-i(H-E0)t] Sz_center|GS>")
    flush(stdout)
    for step in start_step:n_steps
        t = step * tstep
        sp_psi = apply(gates, sp_psi; cutoff=tebd_cutoff, maxdim=tebd_maxdim)

        pct = step / n_steps * 100
        elapsed = (time_ns() - t_start) / 1e9
        eta = elapsed / (step - start_step + 1) * (n_steps - step)
        @printf("step %4d/%d (%.1f%%)  t=%.4f  linkdim=%d  elapsed=%.0fs  ETA=%.0fs\n",
            step, n_steps, pct, t, maximum(linkdims(sp_psi)), elapsed, eta)
        flush(stdout)

        for site in 1:total_sites
            distance = site - center
            corr = inner(psi0', sz_ops[site], sp_psi) * exp(im * energy * t)

            data[1, col] = t
            data[2, col] = site
            data[3, col] = distance
            data[4, col] = real(corr)
            data[5, col] = imag(corr)
            col += 1
        end

        if step % 10 == 0
            GC.gc()
        end

        if step % 100 == 0
            jldsave(checkpoint_file;
                data,
                last_step=step,
                alpha,
                beta,
                n_steps,
                tstep,
                tebd_maxdim,
                tebd_cutoff,
            )
            @printf("  [checkpoint saved at step %d]\n", step)
            flush(stdout)
        end
    end

    filename = joinpath(
        data_dir,
        "NDSF_pentamer_alpha=$(alpha)_beta=$(beta)_L=$(total_sites)$(OUTPUT_SUFFIX).jld2",
    )

    jldsave(filename;
        result=data,
        energy,
        alpha,
        beta,
        n_units,
        total_sites,
        center_site=center,
        columns=["time", "site", "distance", "real_corr", "imag_corr"],
        tstep,
        n_steps,
        dmrg_maxdim,
        tebd_maxdim,
        dmrg_cutoff,
        tebd_cutoff,
        nsweeps,
        output_tag=OUTPUT_TAG,
    )

    println("\nData saved to ", filename)
    isfile(checkpoint_file) && rm(checkpoint_file)
    return filename
end

if abspath(PROGRAM_FILE) == @__FILE__
    calculate_dynamics_pentamer()
end
