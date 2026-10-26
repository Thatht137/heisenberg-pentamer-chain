"""复用周期基态，检验同一微观对照参数下的复合残余。"""

const PERIODIC_SOURCE = joinpath(@__DIR__,"dark_periodic_dmrg.jl")
Base.include(expr -> expr == :(ring_main()) ? nothing : expr, Main, PERIODIC_SOURCE)
using DelimitedFiles
const FOLDED_OUT = joinpath(ROOT,"results","novelty_20261004","rank_folded_mps")

function folded_operators(sites,coeff)
    n = length(sites)
    q = coeff["q_over_pi"]*pi
    abs(exp(5im*q*n)-1)<1e-10 || error("动量与周期长度不相容")
    lefta = complex(coeff["a_left_real"],coeff["a_left_imag"])
    leftb = complex(coeff["b_left_real"],coeff["b_left_imag"])
    righta = complex(coeff["a_right_real"],coeff["a_right_imag"])
    rightb = complex(coeff["b_right_real"],coeff["b_right_imag"])
    dos,kos,cos = OpSum(),OpSum(),OpSum()
    scale = sqrt(5n)
    for i in 1:n
        j=mod1(i+1,n)
        wi,wj=exp(5im*q*(i-1))/scale,exp(5im*q*(j-1))/scale
        dos += wi,"Sz",i
        kos += wi*lefta,"Sz",j
        kos += wj*righta,"Sz",i
        for (qop,sop,factor) in (("Qzz","Sz",1.),("Qz+","S-",.5),("Qz-","S+",.5))
            kos += wi*leftb*factor,qop,i,sop,j
            kos += wj*rightb*factor,sop,i,qop,j
            cos += wi*leftb*factor,qop,i,sop,j
            cos += wj*rightb*factor,sop,i,qop,j
        end
    end
    return MPO(dos,sites),MPO(kos,sites),MPO(cos,sites)
end

function folded_main()
    ispath(FOLDED_OUT) && error("输出目录已存在，禁止覆盖")
    coeffpath=joinpath(ROOT,"results","novelty_20261004","rank_even_effective","local_probe_coefficients.csv")
    values,header=readdlm(coeffpath,',',Float64;header=true)
    r=findfirst(==(1.5),values[:,1])
    coeff=Dict(String(header[i])=>values[r,i] for i in eachindex(header))
    refined=joinpath(ROOT,"results","novelty_20261004","effective_periodic_refined")
    rawrows=TOML.parsefile(joinpath(refined,"results.toml"))["rows"]
    candidates=filter(row->row["cells"]==12 && row["accepted"],rawrows)
    isempty(candidates) && error("尚无通过的十二胞周期基态")
    targetchi=last(candidates)["maxdim"]
    specs=[(6,256,joinpath(RING_OUT,"state_N6_D256.jld2"),true),
           (12,384,joinpath(RING_OUT,"state_N12_D384.jld2"),false),
           (12,targetchi,joinpath(refined,"state_N12_D$(targetchi).jld2"),true)]
    mkpath(FOLDED_OUT)
    save_toml(joinpath(FOLDED_OUT,"protocol.toml"),Dict(
        "cells"=>[6,12],"q_over_pi"=>coeff["q_over_pi"],"alpha"=>coeff["alpha"],
        "wavefunction_reuse"=>"All leading uniform spin-3/2 Hamiltonians differ only by positive c1(alpha)^2, so their ground-state vectors coincide",
        "complex_probe"=>true,"real_retuning"=>true,
        "ed_N6_weight_relative_gate"=>1e-5,"N12_weight_relative_change_gate"=>.01,
        "overlap_imaginary_gate"=>1e-8,"scalar_identity_abs_gate"=>1e-9,
        "threads"=>1,"wall_limit_seconds"=>900,
        "scope"=>"effective model at same roots as microscopic N3 test; not microscopic L=60 result"))
    rows=Dict{String,Any}[]
    started=time()
    for (n,chi,path,accepted) in specs
        time()-started<900 || error("探针测量超过预算，停止新增测量")
        psi=load(path,"psi")
        normalize!(psi)
        d,k,c=folded_operators(siteinds(psi),coeff)
        md,mk,mc=[inner(psi',op,psi) for op in (d,k,c)]
        dd=real(inner(d,psi,d,psi))-abs2(md)
        kk=real(inner(k,psi,k,psi))-abs2(mk)
        cc=real(inner(c,psi,c,psi))-abs2(mc)
        dk=inner(d,psi,k,psi)-conj(md)*mk
        dc=inner(d,psi,c,psi)-conj(md)*mc
        weight=kk-real(dk)^2/dd
        composite=cc-real(dc)^2/dd
        row=Dict{String,Any}("cells"=>n,"chi"=>chi,"ground_state_accepted"=>accepted,
            "W_linear"=>dd,"W_fixed_over_beta2"=>kk,"W_min_over_beta2"=>weight,
            "lambda_real"=>real(dk)/dd,"lambda_imag"=>imag(dk)/dd,
            "kappa"=>-real(dk)/dd/coeff["A_prime"],
            "W_composite_perpendicular"=>composite,"scalar_identity_error"=>abs(weight-composite),
            "max_probe_mean_abs"=>max(abs(md),abs(mk),abs(mc)),"elapsed_seconds"=>time()-started)
        row["operator_pass"]=abs(row["lambda_imag"])<1e-8 && row["scalar_identity_error"]<1e-9
        if n==6
            row["ed_relative_error"]=abs(weight/.0664115915710436-1)
            row["ed_pass"]=row["ed_relative_error"]<1e-5
            row["ed_pass"] || error("复动量 MPO 未通过六胞 ED 检查")
        end
        if n==12 && accepted
            previous=last(filter(x->x["cells"]==12,rows))
            row["weight_relative_change"]=abs(weight/previous["W_min_over_beta2"]-1)
            row["weight_convergence_pass"]=row["weight_relative_change"]<.01
        end
        push!(rows,row)
        save_toml(joinpath(FOLDED_OUT,"results.toml"),Dict("rows"=>rows))
        println(row)
        flush(stdout)
    end
    passed=all(r["operator_pass"] for r in rows) && last(rows)["weight_convergence_pass"]
    save_toml(joinpath(FOLDED_OUT,"summary.toml"),Dict("all_gates_pass"=>passed,"bulk_claim"=>false,
        "elapsed_seconds"=>time()-started))
    files=vcat([abspath(@__FILE__),PERIODIC_SOURCE,BASELINE_SOURCE,coeffpath,
        joinpath(refined,"results.toml")],[x[3] for x in specs],filter(isfile,readdir(FOLDED_OUT;join=true)))
    save_toml(joinpath(FOLDED_OUT,"sha256.toml"),Dict(relpath(p,ROOT)=>bytes2hex(sha256(read(p))) for p in files))
    passed || error("同参数长链探针检查未通过")
end

folded_main()
