# static_krylov_k12_r1

仅本地 prepared_only 与 batch dry-run；未启动 Julia、SSH、上传或远端任务。

单点 alpha=-0.1、beta=0.25、L=80、n_units=16、Krylov=12；64 sweeps、maxdim=1200、cutoff=1e-11、threads=8、q_count=401；Sz=0/1，center 与 ferro_j2，保存 state 与 enriched diagnostics。

L10 smoke 证据路径：results/autoresearch_v5_20260920/static_krylov_k12_smoke_r1/a-0100-k12；该证据仅用于 parser/execution gate，声明 Julia 1.11.5，不替代远端要求 Julia 1.12.3。
