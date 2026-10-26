"""保留失败记录，从周期链检查点继续精化。"""

const PERIODIC_SOURCE = joinpath(@__DIR__,"dark_periodic_dmrg.jl")
Base.include(expr -> expr == :(ring_main()) ? nothing : expr, Main, PERIODIC_SOURCE)
const REFINE_RING_OUT = joinpath(ROOT,"results","novelty_20261004","effective_periodic_refined")

function refine_ring_main()
    ispath(REFINE_RING_OUT) && error("输出目录已存在，禁止覆盖")
    mkpath(REFINE_RING_OUT)
    start, limit = time(), 1800.
    source_rows = TOML.parsefile(joinpath(RING_OUT,"results.toml"))["rows"]
    save_toml(joinpath(REFINE_RING_OUT,"protocol.toml"),Dict(
        "cells"=>[12,16],"maxdims_N12"=>[512,768],"maxdims_N16"=>[256,512,768],
        "first_sweeps"=>24,"warm_sweeps"=>16,"threads"=>1,"wall_limit_seconds"=>limit,
        "source_checkpoint"=>"effective_periodic_dmrg/state_N12_D384.jld2",
        "energy_per_cell_change_gate"=>1e-8,"weight_relative_change_gate"=>.01,
        "variance_per_cell_gate"=>1e-8,"total_spin_squared_gate"=>1e-4,
        "max_abs_local_sz_gate"=>1e-4,"bond_energy_spread_gate"=>1e-5,
        "scalar_removal_identity_abs_gate"=>1e-10,
        "scope"=>"PBC effective model refinement only; original failed batch retained; no bulk extrapolation"))
    rows = Dict{String,Any}[]
    accepted_sizes = Int[]
    failure = ""
    try
        for n in (12,16)
            if n==12
                psi = load(joinpath(RING_OUT,"state_N12_D384.jld2"),"psi")
                sites = siteinds(psi)
                previous = last(filter(r->r["cells"]==12,source_rows))
                dims = (512,768)
            else
                sites = siteinds("PentamerQuartet",n;conserve_qns=true)
                psi = MPS(sites,i->isodd(i) ? "Up" : "Dn")
                previous = nothing
                dims = (256,512,768)
            end
            h,d,k,c,sp = ring_operators(sites)
            accepted = false
            for chi in dims
                sweeps = previous === nothing ? 24 : 16
                schedule = previous === nothing ? vcat([32,64,128],fill(chi,sweeps-3)) : fill(chi,sweeps)
                observer = DMRGObserver()
                println("START refined PBC N=$n chi=$chi")
                flush(stdout)
                _,psi = dmrg(h,psi;nsweeps=sweeps,maxdim=schedule,cutoff=1e-13,
                    noise=previous === nothing ? [1e-7,1e-8,1e-9,0.] : [0.],
                    eigsolve_tol=1e-13,eigsolve_krylovdim=5,
                    observer=TimedObserver(observer,start+limit),outputlevel=0)
                r = Dict{String,Any}(moments(psi,h,d,k,c))
                zz = correlation_matrix(psi,"Sz","Sz")
                pm = correlation_matrix(psi,"S+","S-")
                bonds = [C1^2*real(zz[i,mod1(i+1,n)]+pm[i,mod1(i+1,n)]) for i in 1:n]
                merge!(r,Dict("cells"=>n,"maxdim"=>chi,"actual_maxdim"=>maxlinkdim(psi),
                    "total_spin_squared"=>real(inner(sp,psi,sp,psi)),"bond_energies"=>bonds,
                    "bond_energy_spread"=>maximum(bonds)-minimum(bonds),
                    "energy_reconstruction_error"=>abs(sum(bonds)-r["energy_over_beta"]),
                    "scalar_removal_identity_error"=>abs(r["W_min"]-r["W_composite_perpendicular"]),
                    "sweep_energies"=>real.(energies(observer)),
                    "last_sweep_truncation"=>last(truncerrors(observer)),"elapsed_seconds"=>time()-start))
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
                accepted = all(r[key] for key in ("variance_pass","spin_pass","translation_pass","operator_pass","chi_pass"))
                r["accepted"] = accepted
                push!(rows,r)
                save_toml(joinpath(REFINE_RING_OUT,"results.toml"),Dict("rows"=>rows))
                jldsave(joinpath(REFINE_RING_OUT,"state_N$(n)_D$(chi).jld2");psi)
                println("DONE refined PBC N=$n chi=$chi Wmin=$(r["W_min"]) accepted=$accepted")
                flush(stdout)
                previous = r
                accepted && break
            end
            accepted || error("周期尺寸 $n 精化后仍未通过，停止扩大")
            push!(accepted_sizes,n)
        end
    catch err
        failure = sprint(showerror,err)
    finally
        save_toml(joinpath(REFINE_RING_OUT,"summary.toml"),Dict("all_gates_pass"=>isempty(failure),
            "accepted_sizes"=>accepted_sizes,"failure"=>failure,"elapsed_seconds"=>time()-start,"bulk_claim"=>false))
        files = vcat([abspath(@__FILE__),PERIODIC_SOURCE,BASELINE_SOURCE,
            joinpath(RING_OUT,"results.toml"),joinpath(RING_OUT,"state_N12_D384.jld2")],
            filter(isfile,readdir(REFINE_RING_OUT;join=true)))
        save_toml(joinpath(REFINE_RING_OUT,"sha256.toml"),Dict(relpath(p,ROOT)=>bytes2hex(sha256(read(p))) for p in files))
    end
    isempty(failure) || error(failure)
end

refine_ring_main()
