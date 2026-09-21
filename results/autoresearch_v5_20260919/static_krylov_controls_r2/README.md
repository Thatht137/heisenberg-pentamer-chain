# static_krylov_controls_r2

仅本地准备与 batch dry-run；未启动 Julia、SSH 或远端上传。r1 历史目录不变。

两 cell：alpha=-0.1、-0.175，beta=0.25，L=80/n_units=16；Sz=0/1，center 与 ferro_j2，64 sweeps，maxdim=1200，cutoff=1e-11，legacy noise，Krylov=8，maxiter=1，tol=1e-14，保存 state 与 enriched diagnostics。

本版本记录 enriched 解析修复 scripts/autoresearch_v5/negative_static_cell.jl SHA256=291eb369d5441b53d4abafd36d8469e107f4c1d91622ed33478912228ed3635f；依赖补齐：src/utils.jl, src/exact_diag.jl, src/dmrg_solver.jl, src/spectral.jl。实际 harness plan 来源与哈希见 provenance.json。
