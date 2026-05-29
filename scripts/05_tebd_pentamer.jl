"""
脚本 05：用 TEBD 计算五聚体链的实空间-时间关联函数。

输出数据用于后续傅里叶变换得到 S^zz(q, omega)。
"""

using Pkg
Pkg.activate(dirname(@__DIR__))

include(joinpath(dirname(@__DIR__), "src", "PentamerChain.jl"))
using .PentamerChain
using ITensors
using ITensorMPS
using JLD2
using Printf

const N_UNITS = 24
const ALPHA = 1.0
const BETA = 0.5
const TSTEP = 0.01
const N_STEPS = 4000
const DMRG_MAXDIM = 800
const TEBD_MAXDIM = 600
const DMRG_CUTOFF = 1e-10
const TEBD_CUTOFF = 1e-9
const NSWEEPS = 30

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

        # 胞内键：两端 J2，中间 J1。
        append!(bonds, [(s1, s2, j2), (s2, s3, j1), (s3, s4, j1), (s4, s5, j2)])

        # 胞间键：当前五聚体末端连到下一个五聚体起点。
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
    println("五聚体链 TEBD 动力学计算")
    println("=" ^ 60)
    println("N_units = ", n_units)
    println("Total sites L = ", total_sites)
    println("alpha = J2/J1 = ", alpha)
    println("beta  = J3/J1 = ", beta)

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

    gates = pentamer_tebd_gates(sites, n_units; alpha, beta, tstep)
    psi0 = deepcopy(psi_gs)

    sz_center = local_sz_mpo(sites, center)
    sp_psi = noprime(apply(sz_center, psi0))

    data = Matrix{Float64}(undef, 4, n_steps * total_sites)
    col = 1

    println("\nComputing C(n,t) = <GS|Sz_n exp[-i(H-E0)t] Sz_center|GS>")
    for step in 1:n_steps
        time = step * tstep
        sp_psi = apply(gates, sp_psi; cutoff=tebd_cutoff, maxdim=tebd_maxdim)
        @printf("t = %.4f, max linkdim = %d\n", time, maximum(linkdims(sp_psi)))

        for site in 1:total_sites
            sz_site = local_sz_mpo(sites, site)
            corr = inner(psi0', sz_site, sp_psi) * exp(im * energy * time)

            data[1, col] = time
            data[2, col] = site
            data[3, col] = real(corr)
            data[4, col] = imag(corr)
            col += 1
        end

        if step % 10 == 0
            GC.gc()
        end
    end

    data_dir = joinpath(dirname(@__DIR__), "data")
    mkpath(data_dir)
    filename = joinpath(
        data_dir,
        "NDSF_pentamer_alpha=$(alpha)_beta=$(beta)_L=$(total_sites).jld2",
    )

    jldsave(filename;
        result=data,
        energy,
        alpha,
        beta,
        n_units,
        total_sites,
        center_site=center,
        tstep,
        n_steps,
    )

    println("\nData saved to ", filename)
    return filename
end

calculate_dynamics_pentamer()
