"""保留低精度失败记录，提高有效长链保留态数并延长收敛。"""

# 复用首轮定义，跳过其固定入口，不改写历史源码。
const BASELINE_SOURCE = joinpath(@__DIR__, "dark_effective_dmrg.jl")
Base.include(expr -> expr == :(main()) ? nothing : expr, Main, BASELINE_SOURCE)
using JLD2

function refine_main()
    out = joinpath(ROOT,"results","novelty_20261004","effective_dmrg_refined")
    ispath(out) && error("输出目录已存在，禁止覆盖")
    mkpath(out)
    started = time()
    deadline = started+1200
    save_toml(joinpath(out,"protocol.toml"), Dict(
        "cells"=>[20,40], "maxdims"=>[128,192,256], "sweeps"=>[24,16,16],
        "reason"=>"first D=64,128 run failed variance, energy and local-spin gates; preserve failures",
        "boundary"=>"OBC", "total_sz"=>0, "cutoff"=>1e-13,
        "warm_start"=>"do not reduce maxdim when refining the previous state",
        "energy_per_cell_change_gate"=>1e-8, "Wmin_relative_change_gate"=>.01,
        "variance_per_cell_gate"=>1e-8, "max_abs_local_sz_gate"=>1e-4,
        "threads"=>1, "wall_limit_seconds"=>1200,
        "ITensors"=>string(pkgversion(ITensors)), "ITensorMPS"=>string(pkgversion(ITensorMPS)),
        "scope"=>"effective model only; no thermodynamic extrapolation"))
    rows = Dict{String,Any}[]
    for n in (20,40)
        sites = siteinds("PentamerQuartet",n;conserve_qns=true)
        h,d,k,c = operators(sites)
        psi = MPS(sites,i->isodd(i) ? "Up" : "Dn")
        previous_row = nothing
        for (chi, nsweeps) in ((128,24),(192,16),(256,16))
            observer = DMRGObserver()
            schedule = previous_row === nothing ? vcat([16,32,64,96],fill(chi,nsweeps-4)) : fill(chi,nsweeps)
            noise = previous_row === nothing ? [1e-7,1e-8,1e-9,0.] : [0.]
            println("START refined cells=$n chi=$chi sweeps=$nsweeps")
            flush(stdout)
            _,psi = dmrg(h,psi;nsweeps,maxdim=schedule,cutoff=1e-13,noise,
                         eigsolve_tol=1e-13,eigsolve_krylovdim=5,
                         observer=TimedObserver(observer,deadline),outputlevel=0)
            r = Dict{String,Any}(moments(psi,h,d,k,c))
            merge!(r,Dict("cells"=>n,"maxdim"=>chi,"actual_maxdim"=>maxlinkdim(psi),
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
            push!(rows,r)
            save_toml(joinpath(out,"results.toml"),Dict("rows"=>rows))
            jldsave(joinpath(out,"state_N$(n)_D$(chi).jld2");psi)
            println("DONE refined cells=$n chi=$chi Wmin=$(r["W_min"]) variance=$(r["variance_raw"]) Szmax=$(r["max_abs_local_sz"])")
            flush(stdout)
            previous_row = r
        end
    end
    high = filter(r->r["maxdim"]==256,rows)
    accepted = all(r["variance_pass"] && r["spin_symmetry_pass"] && r["chi_convergence_pass"] for r in high)
    save_toml(joinpath(out,"summary.toml"),Dict("all_gates_pass"=>accepted,
              "elapsed_seconds"=>time()-started,"bulk_claim"=>false))
    files = vcat([abspath(@__FILE__),abspath(BASELINE_SOURCE)],readdir(out;join=true))
    save_toml(joinpath(out,"sha256.toml"),Dict(relpath(p,ROOT)=>bytes2hex(sha256(read(p))) for p in files))
    accepted || error("精化后仍有未通过项，禁止当作收敛数据")
end

refine_main()
