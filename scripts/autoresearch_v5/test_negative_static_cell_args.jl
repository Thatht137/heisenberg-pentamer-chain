using Test

const SOURCE = joinpath(@__DIR__, "negative_static_cell.jl")
include(SOURCE)

function parse_probe(extra)
    empty!(ARGS)
    append!(ARGS, [
        "dummy", "-0.1", "0.25", "2", "64", "16", "1e-11", "center",
        "0", "8", "401", "1", extra...
    ])
    return parse_args()
end

@testset "negative static 参数解析" begin
    c12 = parse_probe(String[])
    @test !c12.enriched_diagnostics
    @test c12.eigsolve_krylovdim == 3

    c14 = parse_probe(["legacy", "20260811"])
    @test !c14.enriched_diagnostics
    @test c14.eigsolve_krylovdim == 3

    c15 = parse_probe(["legacy", "20260811", "1"])
    @test c15.enriched_diagnostics
    @test c15.eigsolve_krylovdim == 3

    c16_on = parse_probe(["legacy", "20260811", "1", "8"])
    @test c16_on.enriched_diagnostics
    @test c16_on.eigsolve_krylovdim == 8

    c16_off = parse_probe(["legacy", "20260811", "0", "8"])
    @test !c16_off.enriched_diagnostics
    @test c16_off.eigsolve_krylovdim == 8
end
