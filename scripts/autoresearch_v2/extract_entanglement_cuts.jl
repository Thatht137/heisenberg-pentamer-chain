"""从收敛 MPS 提取中心五类切口纠缠谱。"""

using Pkg
Pkg.activate(dirname(dirname(@__DIR__)))

using ITensors
using ITensorMPS
using JLD2
using Printf
using SHA

function schmidt_data(psi, bond::Int)
    orthogonalize!(psi, bond)
    left = bond == 1 ? (siteind(psi, bond),) : (linkind(psi, bond - 1), siteind(psi, bond))
    _, singular, _, _ = svd(psi[bond], left)
    index = first(inds(singular))
    values = Float64[]
    sectors = Float64[]
    position = 1
    for block in space(index)
        quantum_number, dimension = block
        for _ in 1:dimension
            push!(values, singular[position, position])
            push!(sectors, val(quantum_number, "Sz") / 2)
            position += 1
        end
    end
    probabilities = abs2.(values)
    order = sortperm(probabilities; rev=true)
    return probabilities[order] ./ sum(probabilities), sectors[order]
end

function main()
    length(ARGS) == 2 || error("用法: extract_entanglement_cuts.jl STATE OUTDIR")
    state_path = abspath(ARGS[1])
    outdir = abspath(ARGS[2])
    isfile(state_path) || error("找不到 MPS: $state_path")
    isdir(outdir) && !isempty(readdir(outdir)) && error("拒绝覆盖非空目录: $outdir")
    mkpath(outdir)
    loaded = load(state_path)
    psi = loaded["psi"]
    alpha = loaded["alpha"]
    beta = loaded["beta"]
    0.0 <= alpha <= 1.0 || error("禁止 alpha<0 或 alpha>1")
    total_sites = length(psi)
    center = total_sites ÷ 2
    bonds = (center - 2):(center + 2)
    rows = NamedTuple[]
    summaries = NamedTuple[]
    for bond in bonds
        probabilities, sectors = schmidt_data(copy(psi), bond)
        entropy = -sum(probability * log(probability) for probability in probabilities if probability > 0)
        entanglement = -log.(probabilities)
        push!(summaries, (
            alpha=alpha,
            beta=beta,
            L=total_sites,
            bond=bond,
            bond_class=mod(bond, 5),
            entropy=entropy,
            retained_probability=sum(probabilities[1:min(16, end)]),
            delta_12=length(entanglement) >= 2 ? entanglement[2] - entanglement[1] : NaN,
            delta_34=length(entanglement) >= 4 ? entanglement[4] - entanglement[3] : NaN,
        ))
        for level in 1:min(16, length(probabilities))
            push!(rows, (
                alpha=alpha,
                beta=beta,
                L=total_sites,
                bond=bond,
                bond_class=mod(bond, 5),
                level=level,
                schmidt_sz=sectors[level],
                probability=probabilities[level],
                entanglement_energy=entanglement[level],
            ))
        end
    end
    open(joinpath(outdir, "entanglement_spectrum.csv"), "w") do file
        println(file, join(keys(first(rows)), ','))
        for row in rows
            println(file, join(values(row), ','))
        end
    end
    open(joinpath(outdir, "cut_summary.csv"), "w") do file
        println(file, join(keys(first(summaries)), ','))
        for row in summaries
            println(file, join(values(row), ','))
        end
    end
    acceptance = Dict(
        "alpha" => alpha,
        "five_cut_classes" => length(unique(row.bond_class for row in summaries)) == 5,
        "finite_values" => all(isfinite(value) for row in summaries for value in values(row)),
        "minimum_retained_probability" => minimum(row.retained_probability for row in summaries),
        "source_state_sha256" => bytes2hex(open(sha256, state_path)),
    )
    jldsave(joinpath(outdir, "entanglement_spectrum.jld2"); rows, summaries, acceptance)
    open(joinpath(outdir, "acceptance.txt"), "w") do file
        for (key, value) in sort(collect(acceptance); by=first)
            println(file, key, "=", value)
        end
    end
    open(joinpath(outdir, "checksums.sha256"), "w") do file
        for name in sort(filter(!=("checksums.sha256"), readdir(outdir)))
            println(file, bytes2hex(open(sha256, joinpath(outdir, name))), "  ", name)
        end
    end
    println("ENTANGLEMENT_SUCCESS outdir=$outdir")
end

main()
