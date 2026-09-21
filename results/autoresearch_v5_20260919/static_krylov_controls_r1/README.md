# static_krylov_controls_r1

本目录仅是本地准备结果，未启动 Julia、SSH 或远端上传。

两 cell 为 alpha=-0.1、-0.175，beta=0.25、L=80；双初态 center/ferro_j2，Sz=0/1，64 sweeps，maxdim=1200，cutoff=1e-11，legacy noise，Krylov=8，maxiter=1，tol=1e-14。无 warmstart、128 晋级和 retry。

历史 StageA/Rx 生成器未批量修改；在依赖预检完成前不能直接复用新 Krylov hook。当前主 pilot 的 SOURCES 已补入 negative_dmrg_options.py。

实际 harness plan 已完成独立审计：`C:/Users/hh250/code/quantum.harness/scripts/parameter_scan.py` 生成了 2-cell `run_spec.json`，物理点与 shared settings 均与本目录生产 run-spec 一致。schema 差异与证明见 `harness_parameter_scan_preflight/schema_conversion.json`。未来准备器必须传入该 harness 生成的 run-spec；缺少时 fail-closed。
