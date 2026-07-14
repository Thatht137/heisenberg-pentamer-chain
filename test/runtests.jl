"""
五聚体链实现的基础测试。
"""

using Pkg
Pkg.activate(dirname(@__DIR__))

include(joinpath(dirname(@__DIR__), "src", "PentamerChain.jl"))
using .PentamerChain
using ITensors
using ITensorMPS
using LinearAlgebra
using Test

@testset "PentamerChain" begin

    @testset "Utility functions" begin
        # 编码和解码应互为逆操作
        for idx in 1:32
            config = PentamerChain.index_to_config(idx, 5)
            @test PentamerChain.spin_basis_state(config) == idx
        end
    end

    @testset "Single pentamer Hamiltonian" begin
        # 均匀情形 J1=J2=1：矩阵应为厄米且维度正确
        H = pentamer_hamiltonian_matrix(1.0, 1.0)
        @test size(H) == (32, 32)
        @test issymmetric(Matrix(H))

        # Heisenberg 模型矩阵迹应为 0
        @test abs(tr(Matrix(H))) < 1e-12

        # 开边界均匀 5 格点链的基态能量
        vals = eigvals(Matrix(H))
        @test isapprox(vals[1], -1.92789; atol=0.001)
    end

    @testset "Total spin classification" begin
        S2 = total_spin_squared_matrix(5)
        @test size(S2) == (32, 32)
        @test issymmetric(Matrix(S2))

        # S^2 本征值应为 S(S+1)，其中 S=1/2, 3/2, 5/2
        s2_vals = eigvals(Matrix(S2))
        # 对应简并数分别为 10、16、6
        expected = vcat(fill(0.75, 10), fill(3.75, 16), fill(8.75, 6))
        sort!(expected)
        sort!(s2_vals)
        @test isapprox(s2_vals, expected; atol=1e-10)
    end

    @testset "Exact diagonalization" begin
        vals, _, spins = diagonalize_pentamer(1.0)
        @test length(vals) == 32
        @test length(spins) == 32

        # 均匀反铁磁链基态应在 S=1/2 扇区
        @test isapprox(spins[1], 0.5; atol=0.1)

        levels = classify_states(vals, spins)
        @test length(levels) >= 5  # 至少应有多个不同能级

        # 总简并度应覆盖完整 32 维空间
        total_deg = sum(l[3] for l in levels)
        @test total_deg == 32
    end

    @testset "Decoupled limit (J2=0)" begin
        # J2=0 时体系为 isolated(1) + trimer(2,3,4) + isolated(5)
        H = pentamer_hamiltonian_matrix(1.0, 0.0)
        vals = eigvals(Matrix(H))
        # 均匀三聚体基态能量为 -1.0
        @test isapprox(vals[1], -1.0; atol=0.001)
    end

    @testset "String order distance profile" begin
        sites = siteinds("S=1/2", 20; conserve_qns=false)
        psi = MPS(sites, fill("Up", 20))

        @test isapprox(
            string_correlator_units(psi, sites, 1, 4),
            -0.25;
            atol=1e-12,
        )

        profile = string_order_distance_profile(
            psi, sites, 4; margin=0)
        @test length(profile) == 3
        @test all(isapprox(row.O_mean, -0.25; atol=1e-12) for row in profile)
        @test [row.n_pairs for row in profile] == [3, 2, 1]
    end
end
