"""把 14:01 服务器资源和本机测试结果写入 HTML 报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results" / "research_progress" / "report.json"
SNAPSHOT = ROOT / "results" / "research_progress" / "server_resource_snapshot_20260803_1401.json"
TITLE = "2026-08-03 14:01 服务器占用与本机测试复核"


def build_section(snapshot: dict[str, object]) -> dict[str, object]:
    anchor = snapshot["anchor"]
    server = snapshot["server"]
    supervisor = snapshot["supervisor"]
    checks = snapshot["local_checks"]
    return {
        "title": TITLE,
        "note": "一次性只读服务器检查；未启动新的远端 Julia",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "有空闲核，但不并行第二个 Julia",
                "why": "服务器约有 64 个空闲核、可用内存 239 GiB；但当前直连 supervisor 的并行保护要求 anchor 结束前不能出现其他 Julia，否则会放弃自动 TEBD 接续。",
            },
            {
                "kind": "table",
                "columns": ["对象", "14:01 观测", "决定"],
                "rows": [
                    ["服务器资源", f"80 核；负载 {server['load_average']}；可用内存 {server['memory_available_gib']}/{server['memory_total_gib']} GiB", "资源不是瓶颈"],
                    ["L=80 CV anchor", f"Julia {anchor['julia_pid']}；运行 {anchor['elapsed']}；CPU {anchor['cpu_percent']}%（约 16.2 核）；第 16 次 sweep", "继续等待首个频点终态"],
                    ["线程与输出", f"OS 线程 {anchor['os_threads']}；points=0；status=running；stderr 为空", "判断为有效计算，不取消"],
                    ["supervisor / TEBD", f"{supervisor['last_log']}；TEBD status.json 不存在", "保留自动接续，不手动绕过"],
                    ["磁盘", f"/home 可用 {server['home_free_gib']} GiB（已用 {server['home_used_percent']}%）", "不新增大批次"],
                ],
                "widths": ["22%", "51%", "27%"],
            },
            {
                "kind": "verdict",
                "status": "good",
                "label": "本机轻量验证通过",
                "why": "Python 单元测试 21/21、目标目录 compileall 通过，heartbeat 图已重新生成；图表仅作运行诊断，不作为物理结果。",
            },
            {
                "kind": "table",
                "columns": ["本机项目", "结果", "说明"],
                "rows": [
                    ["生产入口回归", checks["python_unittest"], "progress、可恢复 CV、静态管线、oracle、TEBD 交叉验收"],
                    ["Python 语法", checks["python_compileall"], "scripts/autoresearch_v5 及现有报告脚本"],
                    ["heartbeat 图", checks["heartbeat_plot"], "10 个快照；CPU 约 1620–1625%；输出点仍为 0"],
                    ["本地 Julia 项目测试", "未运行（Windows ACL）", "Pkg 日志锁和 known_hosts 读取被拒绝；服务器 Julia 1.12.3 仍是生产验收环境"],
                ],
                "widths": ["25%", "20%", "55%"],
            },
            {
                "kind": "figures",
                "items": [
                    {
                        "src": "anchor_heartbeat_20260803.png",
                        "caption": "运行诊断图：L=80 anchor 的 CPU 心跳持续在约 16.2 核，10 个快照中没有 CV 输出点，TEBD 尚未启动。该图不承担谱函数或相图结论。",
                    }
                ],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["本轮动作", "未提交远端计算；本机完成 21/21 回归、compileall 和 heartbeat 图排版"],
                    ["可安全并行", "本机 Python 测试、离线分析、图表与 HTML 渲染；不启动第二个 Julia"],
                    ["下一远端动作", "anchor 终态后独立回传 -> validate_cv_run.py -> checksum -> supervisor 接 TEBD"],
                    ["范围", "0 <= alpha,beta <= 1；负 alpha 与 Fig. 9 排除"],
                ],
            },
            {
                "kind": "code",
                "title": "本轮证据",
                "text": "results/research_progress/server_resource_snapshot_20260803_1401.json\nfigures/anchor_heartbeat_20260803.sources.json\nscripts/autoresearch_v5/test_progress.py 等 5 个测试文件",
            },
            {
                "kind": "note",
                "label": "本地 Julia 边界",
                "style": "info",
                "text": "本机 Julia 1.11.5 的 Pkg.activate 被用户目录 ACL 阻断（manifest_usage.toml.pid/known_hosts）；这不改变已审计的服务器 Julia 1.12.3 结果，也不把本地失败写成模型失败。",
            },
            {
                "kind": "note",
                "label": "轮询纪律",
                "style": "pending",
                "text": "不做短间隔重复 SSH；等待 anchor 终态文件或 supervisor 出现 TEBD 启动事件后再检查。",
            },
        ],
    }


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    report["sections"] = [section for section in report["sections"] if section["title"] != TITLE]
    report["sections"].insert(0, build_section(snapshot))
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(REPORT), "section": TITLE}, ensure_ascii=False))


if __name__ == "__main__":
    main()
