"""以既有张量网络库独立验证并扩大有效四重态链。"""

using ITensors, ITensorMPS, LinearAlgebra, TOML, SHA, Printf
BLAS.set_num_threads(1)

const ROOT = dirname(dirname(@__DIR__))
const OUT = joinpath(ROOT, "results", "novelty_20261004", "effective_dmrg")
const TZ = Matrix(Diagonal([1.5, 0.5, -0.5, -1.5]))
const TP = [0.0 sqrt(3) 0 0; 0 0 2 0; 0 0 0 sqrt(3); 0 0 0 0]
const TM = transpose(TP) |> Matrix
const C1 = (25 + 4sqrt(7)) / 108
# 系数来自已检验的局域谱分解。
const A0 = -0.12123576954254475
const B0 = 0.1236117648014558

ITensors.space(::SiteType"PentamerQuartet"; conserve_qns=true) =
    conserve_qns ? [QN("Sz", m)=>1 for m in (3, 1, -1, -3)] : 4
ITensors.op(::OpName"Sz", ::SiteType"PentamerQuartet") = TZ
ITensors.op(::OpName"S+", ::SiteType"PentamerQuartet") = TP
ITensors.op(::OpName"S-", ::SiteType"PentamerQuartet") = TM
ITensors.op(::OpName"Qzz", ::SiteType"PentamerQuartet") = TZ*TZ-1.25I
ITensors.op(::OpName"Qz+", ::SiteType"PentamerQuartet") = (TZ*TP+TP*TZ)/2
ITensors.op(::OpName"Qz-", ::SiteType"PentamerQuartet") = (TZ*TM+TM*TZ)/2
ITensors.state(::StateName"Up", ::SiteType"PentamerQuartet") = [1., 0, 0, 0]
ITensors.state(::StateName"Dn", ::SiteType"PentamerQuartet") = [0., 0, 0, 1]

struct TimedObserver <: AbstractObserver
    inner::DMRGObserver
    deadline::Float64
end
function ITensorMPS.measure!(obs::TimedObserver; kwargs...)
    time() > obs.deadline && error("达到有效链 DMRG 时间边界")
    return ITensorMPS.measure!(obs.inner; kwargs...)
end
ITensorMPS.checkdone!(::TimedObserver; kwargs...) = false

function operators(sites)
    n = length(sites)
    hos, dos, kos, cos = OpSum(), OpSum(), OpSum(), OpSum()
    scale = sqrt(5n)
    for i in 1:n
        dos += (-1)^(i-1)/scale, "Sz", i
    end
    for i in 1:n-1
        j, sign = i+1, (-1)^(i-1)
        hos += C1^2, "Sz", i, "Sz", j
        hos += C1^2/2, "S+", i, "S-", j
        hos += C1^2/2, "S-", i, "S+", j
        kos += A0*sign/scale, "Sz", j
        kos += -A0*sign/scale, "Sz", i
        for (qop, sop, factor) in (("Qzz", "Sz", 1.), ("Qz+", "S-", .5), ("Qz-", "S+", .5))
            value = B0*sign*factor/scale
            kos += value, qop, i, sop, j
            kos += -value, sop, i, qop, j
            cos += value, qop, i, sop, j
            cos += -value, sop, i, qop, j
        end
    end
    return MPO(hos, sites), MPO(dos, sites), MPO(kos, sites), MPO(cos, sites)
end

function moments(psi, h, d, k, c)
    normalize!(psi)
    energy = real(inner(psi', h, psi))
    variance = real(inner(h, psi, h, psi))-energy^2
    md, mk, mc = [real(inner(psi', op, psi)) for op in (d,k,c)]
    dd = real(inner(d,psi,d,psi))-md^2
    kk = real(inner(k,psi,k,psi))-mk^2
    cc = real(inner(c,psi,c,psi))-mc^2
    dk = real(inner(d,psi,k,psi))-md*mk
    dc = real(inner(d,psi,c,psi))-md*mc
    return Dict("energy_over_beta"=>energy, "variance_raw"=>variance,
                "W_linear"=>dd, "W_dark_over_beta2"=>kk,
                "lambda_integrated"=>dk/dd, "W_min"=>kk-dk^2/dd,
                "W_composite_perpendicular"=>cc-dc^2/dd,
                "max_abs_local_sz"=>maximum(abs.(expect(psi,"Sz"))),
                "total_sz"=>sum(real.(expect(psi,"Sz"))))
end

function save_toml(path, value)
    open(path, "w") do io
        TOML.print(io, value)
    end
end

function main()
    ispath(OUT) && error("输出目录已存在，禁止覆盖")
    mkpath(OUT)
    started = time()
    deadline = started+900
    save_toml(joinpath(OUT,"protocol.toml"), Dict(
        "cells"=>[6,10,20,40], "maxdims"=>[64,128], "sweeps"=>12,
        "boundary"=>"OBC", "total_sz"=>0, "cutoff"=>1e-12,
        "energy_per_cell_change_gate"=>1e-8, "Wmin_relative_change_gate"=>.01,
        "variance_per_cell_gate"=>1e-8, "max_abs_local_sz_gate"=>1e-4,
        "pilot_energy_abs_gate"=>1e-8, "pilot_weight_relative_gate"=>1e-5,
        "threads"=>1, "wall_limit_seconds"=>900,
        "ITensors"=>string(pkgversion(ITensors)), "ITensorMPS"=>string(pkgversion(ITensorMPS)),
        "a0"=>A0, "b0"=>B0, "c1"=>C1,
        "scope"=>"effective model only; no thermodynamic extrapolation; small-size ED oracle first"))
    exact = Dict(6=>(-1.6019098819863347, .0009213480338434413),
                 10=>(-2.8229355425373894, .0010171514115051837))
    rows = Dict{String,Any}[]
    for n in (6,10,20,40)
        sites = siteinds("PentamerQuartet", n; conserve_qns=true)
        h,d,k,c = operators(sites)
        psi = MPS(sites, i->isodd(i) ? "Up" : "Dn")
        previous_row = nothing
        for chi in (64,128)
            observer = DMRGObserver()
            schedule = [min(chi,x) for x in (16,32,48,64,chi,chi,chi,chi,chi,chi,chi,chi)]
            println("START cells=$n maxdim=$chi")
            flush(stdout)
            _, psi = dmrg(h, psi; nsweeps=12, maxdim=schedule, cutoff=1e-12,
                          noise=[1e-7,1e-8,1e-9,0.], eigsolve_tol=1e-12,
                          observer=TimedObserver(observer,deadline), outputlevel=0)
            r = Dict{String,Any}(moments(psi,h,d,k,c))
            merge!(r, Dict("cells"=>n, "maxdim"=>chi, "actual_maxdim"=>maxlinkdim(psi),
                         "last_sweep_truncation"=>last(truncerrors(observer)),
                         "sweep_energies"=>real.(energies(observer)),
                         "elapsed_seconds"=>time()-started))
            r["variance_pass"] = abs(r["variance_raw"])/n < 1e-8
            r["spin_symmetry_pass"] = r["max_abs_local_sz"] < 1e-4
            if previous_row !== nothing
                r["energy_per_cell_change"] = abs(r["energy_over_beta"]-previous_row["energy_over_beta"])/n
                r["Wmin_relative_change"] = abs(r["W_min"]/previous_row["W_min"]-1)
                r["chi_convergence_pass"] = r["energy_per_cell_change"] < 1e-8 && r["Wmin_relative_change"] < .01
            end
            if haskey(exact,n)
                r["ed_energy_error"] = abs(r["energy_over_beta"]-exact[n][1])
                r["ed_weight_relative_error"] = abs(r["W_min"]/exact[n][2]-1)
                r["ed_pass"] = r["ed_energy_error"] < 1e-8 && r["ed_weight_relative_error"] < 1e-5
            end
            push!(rows,r)
            save_toml(joinpath(OUT,"results.toml"),Dict("rows"=>rows))
            println("DONE cells=$n chi=$chi Wmin=$(r["W_min"]) variance=$(r["variance_raw"]) Szmax=$(r["max_abs_local_sz"])")
            flush(stdout)
            previous_row = r
        end
        if haskey(exact,n) && !previous_row["ed_pass"]
            error("小尺寸独立检验未通过，停止扩大")
        end
    end
    high = filter(r->r["maxdim"]==128,rows)
    accepted = all(r["variance_pass"] && r["spin_symmetry_pass"] && r["chi_convergence_pass"] for r in high)
    save_toml(joinpath(OUT,"summary.toml"),Dict("all_gates_pass"=>accepted,
              "elapsed_seconds"=>time()-started, "bulk_claim"=>false))
    files = vcat([abspath(@__FILE__)], readdir(OUT;join=true))
    save_toml(joinpath(OUT,"sha256.toml"), Dict(relpath(p,ROOT)=>bytes2hex(sha256(read(p))) for p in files))
    accepted || error("至少一个尺寸尚未满足收敛标准")
end

main()
