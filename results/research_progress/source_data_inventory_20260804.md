# Source-data inventory

状态：`pass`；条目：111。

## 动态证据分级

| 集合 | 分级 | 处理 |
|---|---|---|
| `high150_accepted` | `accepted_cv_point` | omega=1.50 已通过本地 validator，作为第七个 accepted-only CV 点。 |
| `accepted_only_anchor_7` | `accepted_only` | 七个频点 0.20, 0.25, 0.30, 0.35, 0.55, 1.00, 1.50；不含 low-005。 |
| `fig8_bounded` | `bounded_not_production` | Fig.8 仅呈现七点 overlay 与 low-005 失败标记；production dynamic gate=false。 |
| `low005_rejected` | `rejected_audit_only` | omega=0.05 residual=1.1767005759300015e-5 > 1e-5；保留失败证据，禁止混入 accepted-only 或 production。 |
| `round43_qpi_production` | `production_agreement_bounded_scope` | accepted11、validator 与 peak/weight 门通过；Agreement 仅限 alpha=0.23,beta=0.5,L=40,q=pi。 |
| `minimal_fullq_tooling` | `tooling_ready_compute_pending` | 六 cell 计划、非覆盖回传、独立 validator、dt/dt2 handoff 与四格式绘图已完成；真实 production 数据仍在计算。 |

## 分离验收

| 检查 | 结果 |
|---|---|
| `high150_accepted` | `pass` |
| `accepted_anchor_seven_points` | `pass` |
| `accepted_anchor_excludes_low005` | `pass` |
| `fig8_is_bounded` | `pass` |
| `fig8_marks_low005_rejected` | `pass` |
| `low005_rejected_audit_only` | `pass` |
| `round43_qpi_production` | `pass` |
| `minimal_fullq_tooling_ready` | `pass` |

## 哈希清单

| 路径 | 字节 | SHA-256 |
|---|---:|---|
| `docs/claim_evidence_matrix.md` | 5377 | `c48d6256a9ab29fd2e7e2da5799f24895bee4bd050dc8d0f37fbd9238b28d358` |
| `docs/delivery_plan_to_20260810.md` | 5087 | `36022a826803cc665dff0d50db6d41b826a35824fa377602e3ac452e9543179b` |
| `docs/dynamic_figure_contract.example.json` | 528 | `ffd374ef27401cd703ab2939444df81d139964ef787dee6b7c91b489b7d18ef8` |
| `docs/figure_plan.md` | 4307 | `37ae0035f8f333fbc78b4ab93ff679cedc268ca9f69775fda6c36830b3c381aa` |
| `docs/local_delivery_manifest_20260804.md` | 8021 | `62d90371562125f945846bc93f0a8dc6f7086793d6b437f6bbb4f77326359757` |
| `docs/pentamer_reproduction_standard.md` | 21964 | `aa06eaf6d816b40161e1d493a4c8a800aeac33d8a190eb8312e1ddba90fd7ce8` |
| `docs/reproducibility_commands_20260804.md` | 6229 | `cc18cd7f9b65be781a48299aaf5571b166b37e8309ed006015b9ffb12e2103ae` |
| `docs/supplementary_materials_plan_20260804.md` | 2095 | `9daedd90d26cc96df7d94160e5e996cbff71013a59884afe9ebfec15b6d06d2e` |
| `figures/paper_fig1_model_local_multiplets_20260804.pdf` | 45951 | `f29762a782e2e04d07ac4b3cabf60e62f8f427c7ab0718da7d3b20e7e6d30e2e` |
| `figures/paper_fig1_model_local_multiplets_20260804.png` | 128312 | `61c2101c26759946babdbf97971be562715aab8a71b5bfa99e6eef6be92de7c5` |
| `figures/paper_fig1_model_local_multiplets_20260804.sources.json` | 1180 | `077c54d01cfaee30f8c62db3ae0b3dd64bccdfc8a903a59edc47855b06b37856` |
| `figures/paper_fig1_model_local_multiplets_20260804.svg` | 27240 | `75f77a8bdfeac5ae62dfb0a2773101b25d57b0db1188abfdc7e1bb856ea75486` |
| `figures/paper_fig1_model_local_multiplets_20260804.tiff` | 526262 | `e1785bbb56bfbcbef42a131f2637d59946585e4b9795d1760c8f7a4ee545006a` |
| `figures/paper_fig2_level_flow_qpi_filter_20260804.pdf` | 55586 | `3cd8b523e16f1c955e413e18798d992ca35904c976c7af92b8c10aa08b9aa3e1` |
| `figures/paper_fig2_level_flow_qpi_filter_20260804.png` | 212248 | `b3c86ff2cb5539ebdf513c89f93ec3d62a56f868c0dab31707aebaefa0781a7c` |
| `figures/paper_fig2_level_flow_qpi_filter_20260804.sources.json` | 1176 | `3c68d9c021133366fd5e24cddaad9f5f4bff47594ce3b5c6e2624d1b4bb39ebc` |
| `figures/paper_fig2_level_flow_qpi_filter_20260804.svg` | 55124 | `b2bc5d1cc1c83189b878d1f8ddd9473de06b1de57d4cee489a299d8b3f8c9938` |
| `figures/paper_fig2_level_flow_qpi_filter_20260804.tiff` | 645580 | `9bfb99fc1998539fb43542629ba4c04b7c0120f55525d8c26e234bec794be048` |
| `figures/paper_fig3_positive_groundstate_diagnostics_20260804.pdf` | 54088 | `a3d18ade49da60dabca03e89bd7db1a004f65cc778b92a2c3862c35e7a1cb064` |
| `figures/paper_fig3_positive_groundstate_diagnostics_20260804.png` | 312916 | `ec289aec3bf422f7ca82e3439491387b499f826842650654ab619cf033a0efb0` |
| `figures/paper_fig3_positive_groundstate_diagnostics_20260804.sources.json` | 1245 | `89f1b808acd2eae9aad58e233e6f0b2dae2c1a672abcbb78219ee5bbd216d45f` |
| `figures/paper_fig3_positive_groundstate_diagnostics_20260804.svg` | 53879 | `6a10cbd12549fa28e93b6d6288a1c7387d07a3044dc7c27f5e6235478f4f4e05` |
| `figures/paper_fig3_positive_groundstate_diagnostics_20260804.tiff` | 1269196 | `2cf965be974ef6a7b1b24d08e384b82ede073bbff4eea1319f04f44c06327899` |
| `figures/paper_fig4_entanglement_spectrum_20260804.pdf` | 51816 | `92f5a525f6805eeea4d43814db0396c3869e7a6cda664e2829efd45393c352be` |
| `figures/paper_fig4_entanglement_spectrum_20260804.png` | 162866 | `5bd5f9a702eb05f8583bf5ad5acf586698c6472e0207c28642577a66fa07cb62` |
| `figures/paper_fig4_entanglement_spectrum_20260804.sources.json` | 1701 | `0b2b7bfca805eebb3a1e89b0a45b709da56bdcf617905e8400601dbb823e651d` |
| `figures/paper_fig4_entanglement_spectrum_20260804.svg` | 86039 | `7fc28cdf8ba744dc8ff0bf2346e4d2a08bebba41ba585d558fff96d8fffc5095` |
| `figures/paper_fig4_entanglement_spectrum_20260804.tiff` | 972760 | `943295a582fbff04a378ed0c2f6a0f472f51ee4e016386cc3f465eb2cf475d23` |
| `figures/paper_fig5_effective_chain_selection_rules_20260804.pdf` | 65589 | `c91a72c4232a74014aaa615dd8a85427e272a9e4d0ffd32c91a8e9ec408c688f` |
| `figures/paper_fig5_effective_chain_selection_rules_20260804.png` | 355013 | `0c3ad00c2333695038360ec49e7d62dc2a2d3a9e1beeded899ef0f24be1527dd` |
| `figures/paper_fig5_effective_chain_selection_rules_20260804.sources.json` | 1581 | `cbd62093ae1786760f7794a176aaa2851143bbfac57c9e682932cb1d7f7e4c41` |
| `figures/paper_fig5_effective_chain_selection_rules_20260804.svg` | 82423 | `3fdcdc8876a88e74fe25cdcbf7d5d2cf5c88e13a2af35c26b9fccc57cb46b8af` |
| `figures/paper_fig5_effective_chain_selection_rules_20260804.tiff` | 1387814 | `37f66a6f53da1ec582da3950424cd8eede5f1a56249433afa1a75e806d635413` |
| `figures/paper_fig8_bounded_cv_tebd_20260805.pdf` | 46891 | `f78b23f1b321a96329cf1ede84e4bd7a30fd5bf10421ec1beafdbaafa5d842f4` |
| `figures/paper_fig8_bounded_cv_tebd_20260805.png` | 136468 | `f0d2c452d669a6327da006b824a765d5b0f633075a02e8e8e0d0a6ee3ad44fe0` |
| `figures/paper_fig8_bounded_cv_tebd_20260805.sources.json` | 2931 | `74d24e8b8cb2bca315cb358f16aa41409a16929a9f068dea6aaa8efa72f0443f` |
| `figures/paper_fig8_bounded_cv_tebd_20260805.svg` | 22115 | `407dda1bc0ececac5dc3ee95f58c6ee29024278f21ea56b82128900e993a3079` |
| `figures/paper_fig8_bounded_cv_tebd_20260805.tiff` | 444002 | `2d87240fcfbead604729153210738be41a7c3e6351a168d7529756f45e50cf6c` |
| `figures/round43_fig8_final_20260806_v2.pdf` | 50045 | `09c6bdbf6c539e0543a4bb7eefaf6454648af5ac14babb4d861fb0dac143f206` |
| `figures/round43_fig8_final_20260806_v2.png` | 150973 | `f73385a635e37ceebc54c575dfbaef72534f663c8d67cb2af55af0ffed1f7fc4` |
| `figures/round43_fig8_final_20260806_v2.qa.json` | 316 | `2e3d7a6d90e402f16ff8f3e7532712c981ae6d8cc2fb0c3cbb263d154757d98e` |
| `figures/round43_fig8_final_20260806_v2.source.csv` | 984 | `8ac1305882ebbcfe9485dcd8e676513522cc867c73da275d2db5d78eff84f2ae` |
| `figures/round43_fig8_final_20260806_v2.sources.json` | 2809 | `9f93cefd0a0b91ebe74cd9fddce228960521b615508c6ec070dee038bdf22b3e` |
| `figures/round43_fig8_final_20260806_v2.svg` | 24275 | `1ffaca3910cd2a22e8a467492b5be2cc39e36f4f4a13b25cdb033f5c2dfd634f` |
| `figures/round43_fig8_final_20260806_v2.tiff` | 465312 | `6b6402e4223214b576527aa263315d411e42e875cbdf694f7d1fb7c28f9cf0fe` |
| `results/autoresearch_v5_20260805/round40_cv_tebd_accepted7_analysis/cross-method-check.csv` | 346 | `95b158fc4b164c5b6b701bc5ba33ad52403cc227a7dd0749b8eff853ddfe5e98` |
| `results/autoresearch_v5_20260805/round40_cv_tebd_accepted7_analysis/cross-method-check.json` | 2891 | `1235f90bf671f1e3c954858ff016c1eb3fcace8a60c9d1e09eb2bdbc15c8fc0d` |
| `results/autoresearch_v5_20260805/round40_qpi_cv_anchor_assembly_accepted/checksums.sha256` | 161 | `a3121f23ca2db1f7fe0dbd2322c2d7406a43d0157752fbbfffb3be1b7119e64b` |
| `results/autoresearch_v5_20260805/round40_qpi_cv_anchor_assembly_accepted/manifest.json` | 3216 | `da34e3db8e0c77d582472cc4e30e8638bdc05368f27497e41671a1707af1aa3e` |
| `results/autoresearch_v5_20260805/round40_qpi_cv_anchor_assembly_accepted/spectrum.csv` | 1299 | `c6153072b260e8745c1aea62edf33e36b9cdb51adbfa788bad5de9d607847d54` |
| `results/autoresearch_v5_20260805/round40_qpi_cv_high150_fetch/cell-l40-qpi-high-150/checksums.sha256` | 792 | `bc4b9f0ce5201f6a1141114f0e4ee4c684f4805c1884a60456e62f47342e5087` |
| `results/autoresearch_v5_20260805/round40_qpi_cv_high150_fetch/cell-l40-qpi-high-150/manifest.json` | 2733 | `ada854ee1dfae7ef053e714cfa70eac27496858f2638d05d193a0050ab4e593d` |
| `results/autoresearch_v5_20260805/round40_qpi_cv_high150_fetch/cell-l40-qpi-high-150/metrics.csv` | 537 | `ce4912db96c58abc89869560608f0f373b4bd60641736ca999178e1eb5e4d3f0` |
| `results/autoresearch_v5_20260805/round40_qpi_cv_high150_fetch/cell-l40-qpi-high-150/progress.json` | 477 | `2451308863841363e114b0e0385c1a8fea2159804c9f3d5a4fc486eedf845abf` |
| `results/autoresearch_v5_20260805/round40_qpi_cv_high150_fetch/cell-l40-qpi-high-150/resource.log` | 1069 | `04d4ca2d2ca215841c00526771b20c22efd38d31f9124423e7381cbfa221093c` |
| `results/autoresearch_v5_20260805/round40_qpi_cv_high150_fetch/cell-l40-qpi-high-150/spectrum.csv` | 145 | `d5ad7eabae2208cc484616e9b35c9cd9bad8bdcd635250a55438b475fd7d14d3` |
| `results/autoresearch_v5_20260805/round40_qpi_cv_high150_fetch/cell-l40-qpi-high-150/spectrum.jld2` | 8205 | `1cb6d20fa33a86c6b17c3d85cad0f3d9b62af33c80c9ee9e9a9192faa77b8569` |
| `results/autoresearch_v5_20260805/round40_qpi_cv_high150_fetch/cell-l40-qpi-high-150/status.json` | 169 | `8973e23012b23593ce0303eb169b4374583310f7be8aba93e1c969df99d689f5` |
| `results/autoresearch_v5_20260805/round40_qpi_cv_high150_fetch/cell-l40-qpi-high-150/stderr.log` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `results/autoresearch_v5_20260805/round40_qpi_cv_high150_fetch/cell-l40-qpi-high-150/stdout.log` | 1547 | `2b16a9738f03a0929b8a8e4f8b95c4219300e39b193ba905b3023c28f9851147` |
| `results/autoresearch_v5_20260805/round40_qpi_cv_high150_fetch/cell-l40-qpi-high-150/sweep_history.csv` | 825 | `f8a1de8f1ae8e99446eb15d6372ca4e3d58288e242cb373430cd34c5ffab269d` |
| `results/autoresearch_v5_20260805/round41_qpi_cv_low005_retry_fetch_20260805_2212/cell-l40-qpi-retry-005/checksums.sha256` | 792 | `4101b8950e555c1b52f28b389b3b327d946e59137ae44d9ce64015b8645b353e` |
| `results/autoresearch_v5_20260805/round41_qpi_cv_low005_retry_fetch_20260805_2212/cell-l40-qpi-retry-005/manifest.json` | 2738 | `ce955f885f770e2e6d035aaaa3e993fcba2b1c3fa1c454e30c5782ff7d1fe246` |
| `results/autoresearch_v5_20260805/round41_qpi_cv_low005_retry_fetch_20260805_2212/cell-l40-qpi-retry-005/metrics.csv` | 538 | `3ed8d6b30f853ceabb862c7ff85939fc808a2a57155e8348f1e93f7199908e88` |
| `results/autoresearch_v5_20260805/round41_qpi_cv_low005_retry_fetch_20260805_2212/cell-l40-qpi-retry-005/progress.json` | 477 | `a2b6dd9a9b9db4e8ba05d8582491e43fd5712b5d71be64c8623b7b33f0e09799` |
| `results/autoresearch_v5_20260805/round41_qpi_cv_low005_retry_fetch_20260805_2212/cell-l40-qpi-retry-005/resource.log` | 1072 | `9102787f9750086637bde2ced5b327ea1e8542170b64bf197dc5075ad3849d18` |
| `results/autoresearch_v5_20260805/round41_qpi_cv_low005_retry_fetch_20260805_2212/cell-l40-qpi-retry-005/spectrum.csv` | 145 | `878fcb866b9872122efbe99d2a9d999529c37b98bca4014d61cb64da54724639` |
| `results/autoresearch_v5_20260805/round41_qpi_cv_low005_retry_fetch_20260805_2212/cell-l40-qpi-retry-005/spectrum.jld2` | 8205 | `55f5015c1c932d236a45bff8f6c0d7ef42e2943b600a08d090b8d7b09bcdaaeb` |
| `results/autoresearch_v5_20260805/round41_qpi_cv_low005_retry_fetch_20260805_2212/cell-l40-qpi-retry-005/status.json` | 170 | `b1bd14c1cc757d8ca27a44558143609c3508af4fedfda8bc634bbb5e210ec726` |
| `results/autoresearch_v5_20260805/round41_qpi_cv_low005_retry_fetch_20260805_2212/cell-l40-qpi-retry-005/stderr.log` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `results/autoresearch_v5_20260805/round41_qpi_cv_low005_retry_fetch_20260805_2212/cell-l40-qpi-retry-005/stdout.log` | 1901 | `8d6bc4c630a2d0aa6a2645247a42e0ae277b03e4c445a6007c2880bea98afc69` |
| `results/autoresearch_v5_20260805/round41_qpi_cv_low005_retry_fetch_20260805_2212/cell-l40-qpi-retry-005/sweep_history.csv` | 1025 | `b0ed03daf570ceb914f30abfb7f14a56944e48a0d0dc6d068c6e4a2312cf9a90` |
| `results/autoresearch_v5_20260806/round43_handoff_final_v2/accepted11/manifest.json` | 3248 | `2f826c2f19b403fb42c83b36694c2e91aaeed2ef8b6d54f9b61c9f44b5f5aa7c` |
| `results/autoresearch_v5_20260806/round43_handoff_final_v2/checksums.sha256` | 568 | `193156bd74b7d8ceaba2dd29d554a34df3c462aa19bd57e41c7af8ee0e3ff4ee` |
| `results/autoresearch_v5_20260806/round43_handoff_final_v2/cross_method/cross-method-check.json` | 3289 | `583cb4b449bf4b8341e69055915e4e8c595d13010414cea6fc5217f87875e484` |
| `results/autoresearch_v5_20260806/round43_handoff_final_v2/handoff_summary.json` | 2130 | `c99943636fc2ae3bd598f4e5ab55bf9420de0488b8edb8133bc6ccfa356c6498` |
| `results/research_progress/bounded_delivery_audit_20260805.json` | 3095 | `81e151a1f2e3d02c3ba442e28240f49aa58590fdd3d604a542f896945b38f9ab` |
| `results/research_progress/cv_sparse_anchor_table_20260804.csv` | 459 | `9623c2c00d7045a17fbfe49c9ad01ac7c6b75caa762da48ef232383990793c65` |
| `results/research_progress/cv_sparse_anchor_table_20260804.json` | 3043 | `60382be47229a862dbb780b3d4f6058e4bc732494e2dd6729adef6e3e70dcc5b` |
| `results/research_progress/dynamic_gate_freeze_20260805.json` | 1494 | `9c94233d0a6f6c4104404cbc8b792fa9ccabfbef452dde33f5e82eff83ba879c` |
| `results/research_progress/fig8_bounded_source_data_20260805.csv` | 784 | `863bd964f40b7daa0da7153c68fce7a004c39a6268fda49aa63d936839499794` |
| `results/research_progress/minimal_fullq_campaign_20260807/campaign_plan.json` | 4647 | `b84afd69fefeef80e52742965e7930801126de23301d3fef921b399fb110b98d` |
| `results/research_progress/minimal_fullq_campaign_20260807/launch_campaign.sh` | 5426 | `96c1a7bdd8283226fe5f4c019e9b85e6b9071fc5fef88098a8965b88d59a243a` |
| `results/research_progress/minimal_fullq_campaign_status_20260807.json` | 1622 | `0b4ba9b9320953f08ee93b2f9a1fc6cae3a5b6ddc1e9c9d1bfcef2b95567e62c` |
| `results/research_progress/qpi_cv_extension_remote_snapshot_20260804_now.json` | 16496 | `7c55bf723d8114947b918819c97334ccde46229d99141e47922d25d7b82d3bf7` |
| `results/research_progress/reproducibility_command_audit_20260805.json` | 861 | `e535339ed65f93ff6033998281a076a5c482ea39d9b499e6d12085ce3f731e11` |
| `results/research_progress/research_completion_dashboard_20260804.json` | 1133 | `677660cedef067bc60a0a4d2625560cdb336ed25a9c5f5618143775930dd39ee` |
| `results/research_progress/round31_high150_fetch_receipt_20260805.json` | 1026 | `34dbf11fad294985bb4a74706d52f7f44bfc5fe26f9872dc3ee582ce7356b580` |
| `results/research_progress/round31_high150_terminal_check_20260805_2053.json` | 2264 | `daf310b102ae35c3fe5b99e7c1691edd6e7dfb81c26ab2b6f6362712683d10a3` |
| `results/research_progress/round31_high150_validator_20260805.json` | 724 | `2d2fb9490538482c42aae9634c36bf85e2c1819d02029d7c6d2f869ca1c17d50` |
| `results/research_progress/round41_low005_retry_fetch_receipt_20260805.json` | 1119 | `1c2a7636ff2c52863940b0f774fc556301fb2cf0d274f675a50b647bfbae9525` |
| `results/research_progress/round41_low005_retry_validator_20260805.json` | 1111 | `afbbb121d0ffffaccd06ec4f64d09f75c61a94349512cd2c2ec0074499bf9b28` |
| `results/research_progress/round41_qpi_cv_low005_fetch_receipt_20260805.json` | 1951 | `c854e0e9e3563c6c97503d8434975da8be71ab923e06046bf731d7e061af9d2e` |
| `results/research_progress/round41_qpi_cv_low005_terminal_assessment_20260805.json` | 2346 | `740726af65a76f3a5f01f5495625005cc285d7021f2e5f9a9da1421e2ab20889` |
| `results/research_progress/round41_qpi_cv_low005_validator_20260805.json` | 1067 | `c317495db157716a6fbb1ff3558ccbeb101a3fa4fcc4a8634995f7716960f321` |
| `scripts/autoresearch_v5/analyze_cv_tebd_crosscheck.py` | 13659 | `420f74bb373c9e1896cb42f71fbe904a92275a37f8ca5167abb1abb72befb2f5` |
| `scripts/autoresearch_v5/assemble_qpi_cv_anchors.py` | 6982 | `c62c005c8c0410339eac14ff8f9b2f9585de0f27b7b5e7dc5df8365be6e14a87` |
| `scripts/autoresearch_v5/audit_bounded_delivery_20260805.py` | 6753 | `893096e62e91929ac5fc31ca31a53e5bc975a5b04c08c1223f4081f70f23bf55` |
| `scripts/autoresearch_v5/audit_minimal_fullq_local_readiness.py` | 3374 | `e80de11b4ca84932c4e07809fdd5566c3a9484886495cf2e893765f468eea860` |
| `scripts/autoresearch_v5/audit_reproducibility_commands_20260805.py` | 5281 | `e9d41bacaef7f58f07885111250f1f09306b8f7bc2e3cd989dedd96e55de9364` |
| `scripts/autoresearch_v5/build_source_data_inventory_20260804.py` | 14749 | `2f269ed699a4422945b52aa86e9c1a8bcedafa8a56a5b4e8bc81ce1a936ec546` |
| `scripts/autoresearch_v5/fetch_fullq_tebd_run.py` | 8360 | `8f2dbac706097f41df9eaa7a171d97e5b4d96352e8440b2968012e035a7d7a3d` |
| `scripts/autoresearch_v5/finalize_minimal_fullq_handoff.py` | 4825 | `6fb6dcb5eb84b1dd8f29cfee34cfe8e9bcce7a0df6b5b479f09b6cd50abb042f` |
| `scripts/autoresearch_v5/plot_dynamic_figures_production.py` | 7680 | `985914954064c29b1c2f2ffda28768f6d0bd1af062e33daeb6b7b5ad8ad460e5` |
| `scripts/autoresearch_v5/plot_fig8_bounded_seven_point_20260805.py` | 7936 | `d1886a4a76a1b8d31119584bfe24c5c92d0528a3c71a2ec0dc773a8bad3d6fd4` |
| `scripts/autoresearch_v5/plot_minimal_fullq_campaign.py` | 11495 | `ff365dae2c96115974cbdc6dd3a2367317462eac1c0d5862459374e524c28f05` |
| `scripts/autoresearch_v5/plot_paper_static_figures_20260804.py` | 20436 | `d5cb83a9a81ccaa63bf992342a2ab3c7f77db38a87afabe3446ac12e6f1015e8` |
| `scripts/autoresearch_v5/test_minimal_fullq_campaign.py` | 7107 | `534b5563872e530b0a931e381a1e748cf7274f5d4784c0e1db79fb390e1a5569` |
| `scripts/autoresearch_v5/update_minimal_fullq_campaign_report_20260807.py` | 5222 | `97443aefb232382c58bcdde50cf6d32909f05e100146e749ecf4f48802becb45` |
| `scripts/autoresearch_v5/validate_cv_run.py` | 8386 | `c07c80d3789a753b494026d39d5396b24103148f3d60941bc3d3d6725cd2abc2` |
| `scripts/autoresearch_v5/validate_fullq_tebd_run.py` | 7267 | `285ae996c26b625da5b6168d7281dae31c6e57202911e1f0761158bb66442884` |

> low-005 仅作为失败审计记录；它不属于 accepted11。round43 production 与七点 bounded Fig.8 独立保留，full-q 数据未终态前不得生成 production Fig.6/7。
