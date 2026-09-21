"""把 TEBD 启动前哈希复核写入 HTML 报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
AUDIT = ROOT / "results/research_progress/tebd_preflight_recheck_20260803.json"
TITLE = "TEBD 启动前哈希与配置复核"


def build_section(audit: dict[str, object]) -> dict[str, object]:
    checks = audit["checks"]
    return {
        "title": TITLE,
        "note": "本地只读复核；不启动 TEBD",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good" if audit["status"] == "pass" else "bad",
                "label": "启动前门槛再次通过" if audit["status"] == "pass" else "启动前门槛存在缺口",
                "why": "Manifest、标准文档、Fourier live 脚本哈希与就绪审计一致；wrapper 保留正区 guard 和 raw/display 分离。",
            },
            {
                "kind": "table",
                "columns": ["检查", "结果", "用途"],
                "rows": [
                    ["Manifest SHA-256", "通过" if checks["manifest_hash"] else "失败", "防止远端依赖环境漂移"],
                    ["标准文档 SHA-256", "通过" if checks["standard_hash"] else "失败", "锁定数值验收门槛"],
                    ["Fourier live SHA-256", "通过" if checks["fourier_hash"] else "失败", "确保 raw spectrum 修正版未被覆盖"],
                    ["wrapper scope/raw guard", "通过" if checks["wrapper_scope_guard"] and checks["raw_display_separation"] else "失败", "限制正区并保留未截断矩阵"],
                ],
                "widths": ["28%", "20%", "52%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["目标", "alpha=0.23、beta=0.5、L=40、dt=0.025、tmax=15、q=81、omega=181"],
                    ["启动条件", "L=80 anchor 终态后才运行；当前不绕过 supervisor"],
                    ["证据", "results/research_progress/tebd_preflight_recheck_20260803.json"],
                ],
            },
            {
                "kind": "note",
                "label": "执行边界",
                "style": "pending",
                "text": "哈希通过只说明配置可启动，不代表 TEBD 已产生数据；生产结论仍需 dt/dt2、时间窗、非负性和 CV/TEBD 交叉门槛。",
            },
        ],
    }


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    sections = [section for section in report["sections"] if section["title"] != TITLE]
    index = next((i + 1 for i, section in enumerate(sections) if section["title"] == "TEBD 交叉检查就绪审计"), len(sections))
    sections.insert(index, build_section(audit))
    report["sections"] = sections
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(REPORT), "section": TITLE}, ensure_ascii=False))


if __name__ == "__main__":
    main()
