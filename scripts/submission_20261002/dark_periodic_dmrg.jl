"""周期有效链检验：先对照精确解，再扩大尺寸。"""

const BASELINE_SOURCE = joinpath(@__DIR__, "dark_effective_dmrg.jl")
Base.include(expr -> expr == :(main()) ? nothing : expr, Main, BASELINE_SOURCE)
using JLD2

const RING_OUT = joinpath(ROOT, "results", "novelty_20261004", "effective_periodic_dmrg")

function ring_operators(sites)
    n = length(sites)
    iseven(n) || error("本批仅允许偶数周期链")
    hos, dos, kos, cos, pos = OpSum(), OpSum(), OpSum(), OpSum(), OpSum()
    scale = sqrt(5n)
    for i in 1:n
        dos += (-1)^(i-1)/scale, "Sz", i
        pos += 1., "S+", i
        j, sign = mod1(i+1,n), (-1)^(i-1)
        hos += C1^2, "Sz", i, "Sz", j
        hos += C1^2/2, "S+", i, "S-", j
        hos += C1^2/2, "S-", i, "S+", j
        kos += A0*sign/scale, "Sz", j
        kos += -A0*sign/scale, "Sz", i
        for (qop,sop,factor) in (("Qzz","Sz",1.),("Qz+","S-",.5),("Qz-","S+",.5))
            v = B0*sign*factor/scale
            kos += v, qop, i, sop, j
            kos += -v, sop, i, qop, j
            cos += v, qop, i, sop, j
            cos += -v, sop, i, qop, j
        end
    end
    return (MPO(os,sites) for os in (hos,dos,kos,cos,pos)) |> Tuple
end

function ring_main()
    ispath(RING_OUT) && error("输出目录已存在，禁止覆盖")
    mkpath(RING_OUT)
    started, limit = time(), 1800.
    save_toml(joinpath(RING_OUT,"protocol.toml"),Dict(
        "cells"=>[6,8,12,16,20],"maxdims"=>[128,256,384],
        "first_sweeps"=>24,"refinement_sweeps"=>16,"boundary"=>"PBC",
        "beta_scaled_out"=>true,"alpha"=>-(2+sqrt(7))/6,"q_over_pi"=>1,
        "threads"=>1,"wall_limit_seconds"=>limit,"cutoff"=>1e-13,
        "energy_per_cell_change_gate"=>1e-8,"weight_relative_change_gate"=>.01,
        "variance_per_cell_gate"=>1e-8,"total_spin_squared_gate"=>1e-4,
        "max_abs_local_sz_gate"=>1e-4,"bond_energy_spread_gate"=>1e-5,
        "scalar_removal_identity_abs_gate"=>1e-10,
        "ed_energy_abs_gate"=>1e-8,"ed_weight_relative_gate"=>1e-5,
        "stop_rule"=>"Stop enlargement at first size failing all gates by chi=384; no relaxed thresholds",
        "scope"=>"effective spin-3/2 chain only; no microscopic long-chain or thermodynamic-limit claim",
        "ITensors"=>string(pkgversion(ITensors)),"ITensorMPS"=>string(pkgversion(ITensorMPS))))
    exact = Dict(6=>(-1.8880277290395293,.00044329965909897714),
                 8=>(-2.4891014347488025,.0006490716874335754))
    rows = Dict{String,Any}[]
    accepted_sizes = Int[]
    failure = ""
    try
        for n in (6,8,12,16,20)
            sites = siteinds("PentamerQuartet",n;conserve_qns=true)
            h,d,k,c,sp = ring_operators(sites)
            psi = MPS(sites,i->isodd(i) ? "Up" : "Dn")
            previous = nothing
            accepted = false
            for chi in (128,256,384)
                time() > started+limit && error("达到周期链时间边界")
                sweeps = previous === nothing ? 24 : 16
                schedule = previous === nothing ? vcat([16,32,64],fill(chi,sweeps-3)) : fill(chi,sweeps)
                observer = DMRGObserver()
                println("START PBC cells=$n chi=$chi sweeps=$sweeps")
                flush(stdout)
                _,psi = dmrg(h,psi;nsweeps=sweeps,maxdim=schedule,cutoff=1e-13,
                    noise=previous === nothing ? [1e-7,1e-8,1e-9,0.] : [0.],
                    eigsolve_tol=1e-13,eigsolve_krylovdim=5,
                    observer=TimedObserver(observer,started+limit),outputlevel=0)
                r = Dict{String,Any}(moments(psi,h,d,k,c))
                r["total_spin_squared"] = real(inner(sp,psi,sp,psi))
                zz = correlation_matrix(psi,"Sz","Sz")
                pm = correlation_matrix(psi,"S+","S-")
                bonds = [C1^2*real(zz[i,mod1(i+1,n)]+pm[i,mod1(i+1,n)]) for i in 1:n]
                r["bond_energies"] = bonds
                r["bond_energy_spread"] = maximum(bonds)-minimum(bonds)
                r["energy_reconstruction_error"] = abs(sum(bonds)-r["energy_over_beta"])
                r["scalar_removal_identity_error"] = abs(r["W_min"]-r["W_composite_perpendicular"])
                merge!(r,Dict("cells"=>n,"maxdim"=>chi,"actual_maxdim"=>maxlinkdim(psi),
                    "sweep_energies"=>real.(energies(observer)),
                    "last_sweep_truncation"=>last(truncerrors(observer)),"elapsed_seconds"=>time()-started))
                r["variance_pass"] = abs(r["variance_raw"])/n<1e-8
                r["spin_pass"] = abs(r["total_spin_squared"])<1e-4 && r["max_abs_local_sz"]<1e-4
                r["translation_pass"] = r["bond_energy_spread"]<1e-5
                r["operator_pass"] = r["scalar_removal_identity_error"]<1e-10 && r["energy_reconstruction_error"]<1e-10
                r["chi_pass"] = false
                if previous !== nothing
                    r["energy_per_cell_change"] = abs(r["energy_over_beta"]-previous["energy_over_beta"])/n
                    r["weight_relative_change"] = abs(r["W_min"]/previous["W_min"]-1)
                    r["chi_pass"] = r["energy_per_cell_change"]<1e-8 && r["weight_relative_change"]<.01
                end
                r["ed_pass"] = true
                if haskey(exact,n)
                    r["ed_energy_error"] = abs(r["energy_over_beta"]-exact[n][1])
                    r["ed_weight_relative_error"] = abs(r["W_min"]/exact[n][2]-1)
                    r["ed_pass"] = r["ed_energy_error"]<1e-8 && r["ed_weight_relative_error"]<1e-5
                end
                accepted = all(r[key] for key in ("variance_pass","spin_pass","translation_pass","operator_pass","chi_pass","ed_pass"))
                r["accepted"] = accepted
                push!(rows,r)
                save_toml(joinpath(RING_OUT,"results.toml"),Dict("rows"=>rows))
                jldsave(joinpath(RING_OUT,"state_N$(n)_D$(chi).jld2");psi)
                println("DONE PBC cells=$n chi=$chi Wmin=$(r["W_min"]) variance=$(r["variance_raw"]) S2=$(r["total_spin_squared"]) accepted=$accepted")
                flush(stdout)
                previous = r
                accepted && break
            end
            accepted || error("周期尺寸 $n 未通过预设检查，停止扩大")
            push!(accepted_sizes,n)
        end
    catch err
        failure = sprint(showerror,err)
    finally
        save_toml(joinpath(RING_OUT,"summary.toml"),Dict("all_gates_pass"=>isempty(failure),
            "accepted_sizes"=>accepted_sizes,"failure"=>failure,"elapsed_seconds"=>time()-started,
            "bulk_claim"=>false))
        sources = vcat([abspath(@__FILE__),BASELINE_SOURCE],filter(isfile,readdir(RING_OUT;join=true)))
        save_toml(joinpath(RING_OUT,"sha256.toml"),Dict(relpath(p,ROOT)=>bytes2hex(sha256(read(p))) for p in sources))
    end
    isempty(failure) || error(failure)
end

ring_main()
