"""记录本机 Julia 环境的只读复核。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
TITLE = "2026-08-04 Julia 环境复核：默认 depot 权限边界"


def main() -> None:
    evidence = ROOT / "results/research_progress/julia_environment_recheck_20260804.json"
    result = {
        "checked_at": "2026-08-04",
        "julia_version": "1.11.5",
        "project": "D:/Project/1x5_Heisenberg_Pentamer/Project.toml",
        "default_depot": "C:/Users/hh250/.julia",
        "status": "runtime_present_but_default_depot_readonly_in_sandbox",
        "observations": [
            "Pkg.status failed to create manifest_usage.toml.pid (EACCES)",
            "PentamerChain precompile failed to create compiled cache pidfile (EACCES)",
            "compiled-modules=no import reached ITensors but known_hosts read was denied (EACCES)",
        ],
        "safe_workaround": "use an explicit writable project-local JULIA_DEPOT_PATH for local smoke checks",
        "remote_impact": "none; no server process or remote file changed",
        "scope": {"negative_alpha_excluded": True, "fig9_excluded": True},
    }
    evidence.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "这是本机权限边界记录，不是服务器 Julia 任务失败，也没有修改用户目录权限。",
        "blocks": [
            {"kind": "verdict", "status": "warn", "label": "Julia 运行时存在；默认 depot 在当前沙箱不可写", "why": "Julia 1.11.5 与项目 Project.toml 可定位，但 Pkg/预编译锁和 ITensors 的 known_hosts 访问被 EACCES 阻断。"},
            {"kind": "table", "columns": ["检查", "结果", "解释"], "rows": [["Julia", "1.11.5", "版本可执行"], ["项目", "Project.toml 可定位", "工作目录正确"], ["默认 depot", "EACCES", "C:/Users/hh250/.julia 对当前沙箱只读"], ["远端影响", "无", "未连接服务器、未修改远端"]], "widths": ["24%", "24%", "52%"]},
            {"kind": "kv", "pairs": [["证据", "results/research_progress/julia_environment_recheck_20260804.json"], ["安全做法", "本地 smoke 使用项目内可写 JULIA_DEPOT_PATH；服务器继续使用已上传环境"], ["范围", "0 <= alpha,beta <= 1；排除负 alpha 与 Fig. 9"]]},
            {"kind": "note", "label": "当前决定", "style": "pending", "text": "不把本机 EACCES 当作远端计算失败；不在本机下载包或修改全局权限。服务器恢复后仍优先完成 round31 回传和数值验收。"},
        ],
    }
    report["sections"] = [s for s in report["sections"] if s.get("title") != TITLE]
    report["sections"].insert(2, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · JULIA ENVIRONMENT AUDIT"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"title": TITLE, "status": result["status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
