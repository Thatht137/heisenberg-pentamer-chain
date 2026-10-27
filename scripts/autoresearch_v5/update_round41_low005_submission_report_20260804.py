"""登记代理分工与 round41 启动事实。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results" / "research_progress"
REPORT = RUN / "report.json"
RECORD = RUN / "round41_qpi_cv_low005_submission_20260804.json"
SCHEDULE = RUN / "automation_schedule_20260804.json"
POLICY_TITLE = "2026-08-04 代理执行规范（Sol / Luna）"
SCHEDULE_TITLE = "2026-08-04 计算 ETA 与一次性只读检查安排"
RUN_TITLE = "2026-08-04 round41 q=pi 低频 CV smoke 已启动"


def policy_section() -> dict[str, object]:
    return {
        "title": POLICY_TITLE,
        "note": "固定分工记录；详细规范见 docs/agent_execution_standard.md。",
        "blocks": [
            {
                "kind": "table",
                "columns": ["角色", "固定职责", "操作边界"],
                "rows": [
                    ["Sol 主进程", "思考、研究决策、任务排序、结果验收", "不直接运行命令、改文件或连接服务器"],
                    ["Luna 5.6 subagent", "文件、命令、测试、服务器、回传和报告操作", "不自行改变物理范围、验收门或论文结论"],
                ],
                "widths": ["20%", "43%", "37%"],
            },
            {
                "kind": "list",
                "title": "固定闭环",
                "items": [
                    "Sol 先定义物理范围、资源预算和验收门。",
                    "Luna 完成可审计预检、执行、PID/进度记录和本地 QA。",
                    "Sol 根据原始事实决定接受、隔离、补算或降级；Luna 执行下一步。",
                ],
            },
            {
                "kind": "note",
                "label": "永久范围",
                "style": "info",
                "text": "仅 0<=alpha,beta<=1；排除负 alpha 与参考 Fig.9；未经明确授权不写入 paper/。",
            },
        ],
    }


def run_section(record: dict[str, object]) -> dict[str, object]:
    launch = record["launch"]
    preflight = record["preflight"]
    verify = record["post_launch_verification"]
    low = verify["low005"]
    high = verify["high150"]
    params = record["parameters"]
    return {
        "title": RUN_TITLE,
        "note": "仅记录提交与一次性启动核验；运行中不反复轮询，不把运行状态写成数值结论。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "round41 已启动，尚未验收",
                "why": "omega=0.05 是对 TEBD 主峰的独立高预算 smoke；需自然终态和 residual<=1e-5 后才可进入 accepted-only 组装。",
            },
            {
                "kind": "table",
                "columns": ["任务", "资源与 PID", "一次性核验", "状态"],
                "rows": [
                    [
                        "round31 high-150",
                        f"Julia {high['julia_pid']}；--threads={high['julia_command_threads']}；RSS {high['rss_kib'] / 1024**2:.2f} GiB",
                        f"CPU {high['cpu_percent']}%；OS threads {high['os_thread_count']}",
                        "仍活跃",
                    ],
                    [
                        "round41 low-005",
                        f"Python {low['python_pid']} / Julia {low['julia_pid']}；--threads={low['julia_command_threads']}；nice {low['niceness']}",
                        f"CPU {low['cpu_percent']}%；RSS {low['rss_kib'] / 1024**2:.2f} GiB；{low['progress']['phase']}",
                        "running，0/1 点",
                    ],
                ],
                "widths": ["19%", "36%", "31%", "14%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["参数", f"alpha=0.23, beta=0.5, L=40, q=pi, eta=0.1, omega=0.05；Ddmrg={params['dmrg_maxdim']}，Dcv={params['cv_maxdim']}，nsweeps={params['nsweeps']}"],
                    ["资源上限", "Julia=4；OPENBLAS/OMP/MKL=1；外层 nice=15；不下载依赖"],
                    ["预检", f"Julia {preflight['julia_version']}；Manifest 和 CV 脚本哈希一致；可用内存 {preflight['server']['available_memory_gib']} GiB；磁盘 {preflight['server']['available_disk_gib']} GiB"],
                    ["远端输出", str(record['target']['cell_dir'])],
                    ["本地记录", "results/research_progress/round41_qpi_cv_low005_submission_20260804.json"],
                ],
            },
            {
                "kind": "list",
                "title": "终态后的固定顺序",
                "items": list(record["acceptance_order"]),
            },
            {
                "kind": "note",
                "label": "解释边界",
                "style": "pending",
                "text": str(record["interpretation_boundary"]),
            },
        ],
    }


def schedule_section(schedule: dict[str, object]) -> dict[str, object]:
    checks = schedule["required_schedule"]
    rows = []
    for check in checks:
        automation = check.get("automation_id") or "未创建"
        if check.get("existing_automation_id"):
            automation += f"；现有 {check['existing_automation_id']} 未更新"
        rows.append([
            check["name"],
            check["requested_time_cst"],
            automation,
            "终态：checksum -> 非覆盖回传 -> validator -> accepted-only -> CV--TEBD -> HTML；运行：只记资源/ETA",
        ])
    return {
        "title": SCHEDULE_TITLE,
        "note": "每个计算都必须有安排、ETA 和一次性只读检查；禁止高频轮询。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "定时监测尚未生效",
                "why": "update 与 view 都超时；未写入 automation.toml，不能把计划时间误报为已经自动执行。",
            },
            {
                "kind": "table",
                "columns": ["计算", "请求检查时间", "automation", "到点动作"],
                "rows": rows,
                "widths": ["22%", "21%", "23%", "34%"],
            },
            {
                "kind": "note",
                "label": "运行纪律",
                "style": "pending",
                "text": "按既定时间核对计算状态，并记录检查结果。",
            },
            {
                "kind": "kv",
                "pairs": [
                    ["机器可读记录", "results/research_progress/automation_schedule_20260804.json"],
                    ["范围", str(schedule["policy"]["scope"])],
                    ["角色", "Sol 决策/验收；Luna 5.6 操作"],
                ],
            },
        ],
    }


def main() -> None:
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    schedule = json.loads(SCHEDULE.read_text(encoding="utf-8"))
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    retained = [
        section
        for section in report["sections"]
        if section.get("title") not in {POLICY_TITLE, SCHEDULE_TITLE, RUN_TITLE}
    ]
    report["sections"] = [policy_section(), schedule_section(schedule), run_section(record), *retained]
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "recorded", "sections": [POLICY_TITLE, SCHEDULE_TITLE, RUN_TITLE]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
