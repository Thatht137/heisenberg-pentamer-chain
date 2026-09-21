#!/usr/bin/env python3
"""把服务器只读预检追加到长期报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results" / "research_progress" / "report.json"
PREFLIGHT = ROOT / "results" / "autoresearch_v5_20260731" / "round11_server_preflight" / "preflight.json"
SECTION_TITLE = "服务器只读预检"


def build_section(data: dict[str, object]) -> dict[str, object]:
    target = data["target"]
    checks = data["read_only_checks"]
    planned = data["planned_upload_after_confirmation"]
    return {
        "title": SECTION_TITLE,
        "note": "2026-07-31 · 只读 SSH 预检；没有上传、启动或下载",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good",
                "label": "服务器环境与本地项目契约一致",
                "why": "主机、Julia 1.12.3、Manifest SHA-256 和三份核心源文件哈希均通过；当前无 Julia 任务。",
            },
            {
                "kind": "table",
                "columns": ["检查项", "结果", "含义"],
                "rows": [
                    ["目标", f"{target['user']}@{target['host']}:{target['port']} ({target['hostname']})", "账户和主机已明确"],
                    ["Julia", checks["julia_version"], "符合服务器固定版本"],
                    ["Manifest", checks["manifest_sha256"][:16] + "…", "与本地完全一致"],
                    ["源文件哈希", "3 / 3 match", "Hamiltonian 与测量代码未漂移"],
                    ["当前 Julia 进程", str(checks["julia_processes"]), "没有既有任务冲突"],
                    ["负载 / 资源", f"load1={checks['load_average_1m']}; {checks['logical_cores']} cores; {checks['memory_available_gib']} GiB available", "小型 oracle 可排队"],
                    ["磁盘", f"{checks['home_disk_available_gib']} GiB available ({checks['home_disk_used_percent']}% used)", "不会触及本任务的空间上限"],
                ],
                "widths": ["24%", "38%", "38%"],
            },
            {
                "kind": "table",
                "columns": ["待确认动作", "范围", "状态"],
                "rows": [
                    ["上传", "3 个新增 CV 恢复脚本；目标 scripts/autoresearch_v5/", "待确认"],
                    ["启动", "L=10，alpha=0.23，beta=0.5，q=pi，首段 1 个频率点", "待确认"],
                    ["资源", "8 threads，nice=10，预计 5–10 min，1–2 GiB", "已预览"],
                    ["网络", "JULIA_PKG_OFFLINE=true；禁止下载和包安装", "已固定"],
                ],
                "widths": ["20%", "55%", "25%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["新 CV 文件远端状态", "均不存在，因此确认后只新增文件，不覆盖旧脚本"],
                    ["旧 CV 恢复目录", "不存在；不会误恢复或覆盖历史任务"],
                    ["新静态 36-cell 目录", "尚不存在；静态任务另行确认，不与 CV 首段合并"],
                    ["预检证据", "results/autoresearch_v5_20260731/round11_server_preflight/preflight.json"],
                ],
            },
            {
                "kind": "code",
                "title": "确认后的唯一启动入口",
                "text": planned["command"],
            },
            {
                "kind": "note",
                "label": "安全边界",
                "style": "pending",
                "text": "本页只记录只读预检。上传、启动和结果回传仍需要用户明确确认；确认前不会执行任何远端写操作。",
            },
        ],
    }


def update_log(report: dict[str, object]) -> None:
    section = next(item for item in report["sections"] if item["title"] == "进展日志")
    table = next(block for block in section["blocks"] if block.get("kind") == "table")
    row = [
        "2026-07-31", "服务器只读预检", "直连服务器身份、资源、Julia、Manifest 与源文件哈希检查",
        "c104-ysu；Julia 1.12.3；Manifest match；无既有 Julia 任务；待确认", "完成",
    ]
    for index, old in enumerate(table["rows"]):
        if old and old[1] == row[1]:
            table["rows"][index] = row
            return
    table["rows"].append(row)


def main() -> None:
    data = json.loads(PREFLIGHT.read_text(encoding="utf-8"))
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    report["sections"] = [item for item in report["sections"] if item["title"] != SECTION_TITLE]
    insert_at = next(
        (index for index, item in enumerate(report["sections"]) if item["title"] == "数值验收"),
        len(report["sections"]),
    )
    report["sections"].insert(insert_at, build_section(data))
    update_log(report)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已更新 {REPORT}")


if __name__ == "__main__":
    main()
