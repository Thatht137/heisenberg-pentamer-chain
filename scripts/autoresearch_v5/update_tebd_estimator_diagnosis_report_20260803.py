"""把 TEBD 谱估计器诊断和今日结论写入报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
DIAGNOSIS = ROOT / "results/research_progress/tebd_estimator_diagnosis_20260803.json"
TITLE = "2026-08-03 18:10 TEBD 失败影响与今日完成判定"
LEGACY_TITLE = "2026-08-03 TEBD 失败影响与今日完成判定"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    diagnosis = json.loads(DIAGNOSIS.read_text(encoding="utf-8"))
    eta01 = diagnosis["results"]["eta_0_1"]
    eta02 = diagnosis["results"]["eta_0_2"]
    sections = [section for section in report["sections"] if section["title"] not in (TITLE, LEGACY_TITLE)]
    sections.insert(
        1,
        {
            "title": TITLE,
            "note": "基于已回传的 tmax=15 原始时域数据做离线全网格诊断；不替代 round24 manifest",
            "blocks": [
                {
                    "kind": "verdict",
                    "status": "good",
                    "label": "今日原定目标完成，TEBD 失败影响局部",
                    "why": "L=80 CV anchor 已通过 8/8 独立验收，交付就绪保持 7/9；TEBD 失败只阻断 dt/dt2 和最终动态准入，不影响正区相图、ED、有效理论及已验收 CV。",
                },
                {
                    "kind": "table",
                    "columns": ["诊断", "eta=0.1", "eta=0.2", "结论"],
                    "rows": [
                        ["全网格负点", f"{eta01['negative_points']}/{eta01['total_points']}", f"{eta02['negative_points']}/{eta02['total_points']}", "加宽窗口仍不能修复全 q"],
                        ["含负值 q 行", f"{eta01['q_rows_with_negative']}/81", f"{eta02['q_rows_with_negative']}/81", "不是少数边缘噪点"],
                        ["镜像 RMS", f"{eta01['mirror_rms']:.3f}", f"{eta02['mirror_rms']:.3f}", "单中心 OBC 源破坏 q 镜像"],
                        ["镜像平均后最小值", f"{eta01['symmetrized_minimum']:.3f}", f"{eta02['symmetrized_minimum']:.3f}", "简单对称化仍失败"],
                        ["q=pi 最小值", f"{eta01['qpi_minimum']:.3f}", f"{eta02['qpi_minimum']:.3f}", "eta=0.2 时 q=pi 可非负，但不能外推全 q"],
                    ],
                    "widths": ["24%", "20%", "20%", "36%"],
                },
                {
                    "kind": "kv",
                    "pairs": [
                        ["根因判断", "有限 OBC 的单中心源空间和不是严格的全格点 O_q 自相关，因此不保证全动量谱正定"],
                        ["排除项", "不是 TEBD/Fourier 崩溃；不是只靠镜像平均或把负值裁成 0 就能修复"],
                        ["可保留用途", "同一 q=pi、eta 和 /pi 归一化下的受限诊断；仍需 dt/dt2 与 CV 覆盖门"],
                        ["不可接受用途", "全 q 生产热图、裁剪后的伪非负谱或最终动态主结论"],
                    ],
                },
                {
                    "kind": "list",
                    "title": "下一轮最小方法修复",
                    "items": [
                        "对少量目标动量直接构造 O_q|GS>，演化其自相关，使谱测度按构造正定。",
                        "显式处理 t=0，并与 CV 的 1/pi 归一化一致。",
                        "先做 q=pi 的 dt/dt2、eta/tmax 和 CV 主峰/权重验收，通过后才扩展其他 q。",
                        "不重新提交全 q 网格，不使用更大展宽掩盖未收敛结构。",
                    ],
                },
                {
                    "kind": "code",
                    "title": "诊断证据",
                    "text": "results/research_progress/tebd_estimator_diagnosis_20260803.json\nscripts/autoresearch_v5/diagnose_tebd_windows.jl\nscripts/autoresearch_v5/analyze_cv_tebd_crosscheck.py",
                },
            ],
        },
    )
    report["sections"] = sections
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03 18:10 CST"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"section": TITLE, "readiness": "7/9"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
