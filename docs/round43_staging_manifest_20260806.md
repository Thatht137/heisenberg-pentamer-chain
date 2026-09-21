# Round43 本地暂存清单

生成时间：`2026-08-06T09:08:29+08:00`

本地文件已提升到项目目录；服务器当前不可连接，尚未上传，round43 尚未启动。

| 动作 | 目标 | SHA-256 | 提升策略 |
|---|---|---|---|
| unchanged | `scripts/autoresearch_v5/cv_dsf_resumable.jl` | `ce3fddb48ad141387d0276c73b982e0fb229b037123ff13e10bc3da75e828d61` | reviewed patch |
| unchanged | `scripts/autoresearch_v5/run_cv_dsf_resumable.py` | `8156b934b63890ff4e655c933c9c8a397921fa62811cb4dad10a7e7c3bc323cb` | reviewed patch |
| unchanged | `scripts/autoresearch_v5/test_resumable_wrapper.py` | `e944068c995dfba67288cc7adfda3e2b18538f6be92cfd82845b11bf093f2af4` | reviewed patch |
| unchanged | `scripts/autoresearch_v5/test_round43_launchers.py` | `930a0296548226a58b8cfbe9e40852c0887ab24b1a324e24484796f22780702c` | reviewed patch |
| unchanged | `scripts/autoresearch_v5/launch_round43_qpi_cv_lowfreq_desc_20260805.sh` | `0b461efe8de914b6ec9a48ed02239e61d7f2105ab72457ebbdb5a2b1707baecd` | reviewed patch |
| unchanged | `scripts/autoresearch_v5/resume_round43_qpi_cv_low000_20260805.sh` | `45f1fc9b8b88dec3847248b86335e26c0d23ccc59fd5a5fde95fbc1aa75c95c1` | reviewed patch |
| unchanged | `scripts/autoresearch_v5/render_bounded_manuscript_20260805.py` | `60366734db58de9e15bc51e9ffd869e6f9800daddb1fdd8510b466a43300b5ef` | reviewed patch |
| unchanged | `scripts/autoresearch_v5/render_research_progress.py` | `c579de655cfd3f935a65a7e792b16df4d750e4069ad12cb8b7ad7cdcb5d17ee9` | reviewed patch |
| unchanged | `docs/round43_compute_plan_20260805.md` | `dc0524d2b4039f606ba85719a68f9a1574d0b36e3ace3947827a93ef3eae7294` | reviewed patch |
| unchanged | `results/research_progress/bounded_manuscript_20260805.html` | `ce0779aaae11e23c9823ce730f14d45053d62e7d15cecea4279f683462762215` | reviewed patch |
| unchanged | `results/research_progress/bounded_manuscript_20260805.qa.json` | `7706bc7a22e237edae618d3ae35a5f1e77d6609ae341a7d06ddd87921d7356ff` | reviewed patch |

## 已通过验收

- Python 单元测试：12/12。
- Python 编译、Julia 静态语法、两个 launcher 的 bash 语法：通过。
- bounded manuscript：六图内嵌及七项证据边界 QA 通过。

## 服务器恢复后的顺序

1. 上传脚本并核对双端 SHA-256。
2. 确认无 Julia 后启动阶段 A，6 小时后只读检查一次。
3. 四点 residual 全部不超过 `1e-5` 才启动阶段 B，2 小时后只读检查一次。
4. 终态 checksum、非覆盖回传、本地 checksum、validator、accepted-only 组装、CV–TEBD 分析、HTML 更新。
