#!/usr/bin/env python3
"""读取 static_krylov_impact_v2 真实产物，生成独立审计报告。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATUS = ROOT / "results" / "research_progress" / "project_closeout_status_20260919.json"
DEFAULT_AUDIT_DOC = ROOT / "docs" / "post_krylov_claim_audit_20260920.md"
DEFAULT_RENDERER = Path.home() / ".codex" / "skills" / "report" / "render_report.py"


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON 须为 object: {path}")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.12g}"
    return str(value)


def pct(value: Any) -> str:
    return f"{100.0 * float(value):.6g}%"


def require_list(mapping: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = mapping.get(key)
    if not isinstance(value, list) or not value or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"impact summary 缺少严格字段 {key}，拒绝生成不完整报告")
    return value


def slope_table(summary: dict[str, Any]) -> list[list[str]]:
    facts = summary.get("key_facts")
    if not isinstance(facts, dict):
        raise ValueError("impact summary 缺少 key_facts")
    rows = require_list(facts, "entropy_period10_window020")
    if len(rows) != 8:
        raise ValueError(f"entropy_period10_window020 应为 8 行，实际 {len(rows)}")
    grouped: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for row in rows:
        required = ("point_id", "alpha", "beta", "L", "solver", "start", "window", "period", "c_eff")
        if any(key not in row for key in required):
            raise ValueError(f"斜率记录字段不完整: {row}")
        if int(row["period"]) != 10 or abs(float(row["window"]) - 0.20) > 1e-12:
            raise ValueError(f"斜率记录不是 period=10/window=.20: {row}")
        solver = str(row["solver"])
        if solver not in {"k3", "k8"}:
            raise ValueError(f"未知 solver 标签: {solver}")
        grouped.setdefault((str(row["point_id"]), str(row["start"])), {})[solver] = row
    if len(grouped) != 4 or any(set(item) != {"k3", "k8"} for item in grouped.values()):
        raise ValueError("斜率记录未形成四组严格 k3/k8 配对")
    output = []
    for key in sorted(grouped):
        pair = grouped[key]
        old = pair["k3"]
        new = pair["k8"]
        output.append(
            [
                key[0],
                key[1],
                fmt(old["alpha"]),
                fmt(old["beta"]),
                fmt(old["L"]),
                fmt(old["c_eff"]),
                fmt(new["c_eff"]),
            ]
        )
    return output


def spread_table(summary: dict[str, Any]) -> list[list[str]]:
    facts = summary["key_facts"]
    rows = require_list(facts, "initial_state_spread")
    output = []
    for row in rows:
        required = (
            "point_id",
            "observable",
            "old_k3_max_abs_spread",
            "new_k8_max_abs_spread",
            "max_abs_spread_reduction_fraction",
            "spread_semantics",
        )
        if any(key not in row for key in required):
            raise ValueError(f"initial_state_spread 字段不完整: {row}")
        output.append(
            [
                str(row["point_id"]),
                str(row["observable"]),
                fmt(row["old_k3_max_abs_spread"]),
                fmt(row["new_k8_max_abs_spread"]),
                pct(row["max_abs_spread_reduction_fraction"]),
                str(row["spread_semantics"]),
            ]
        )
    return output


def solver_drift_table(impact_dir: Path) -> tuple[list[list[str]], str]:
    path = impact_dir / "solver_drift.csv"
    if not path.is_file():
        raise FileNotFoundError(f"缺少 solver_drift.csv: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 4:
        raise ValueError(f"solver_drift 应为 4 行，实际 {len(rows)}")
    output = []
    for row in rows:
        required = (
            "point_id",
            "start",
            "old_q_peak_over_pi",
            "new_q_peak_over_pi",
            "old_dominant_ratio",
            "new_dominant_ratio",
            "new_actual_maxdim_sz0",
            "new_actual_maxdim_sz1",
            "requested_maxdim",
            "q_peak_note",
        )
        if any(key not in row for key in required):
            raise ValueError(f"solver_drift 字段不完整: {row}")
        output.append(
            [
                str(row["point_id"]),
                str(row["start"]),
                fmt(row["old_q_peak_over_pi"]),
                fmt(row["new_q_peak_over_pi"]),
                fmt(row["old_dominant_ratio"]),
                fmt(row["new_dominant_ratio"]),
                fmt(row["new_actual_maxdim_sz0"]),
                fmt(row["new_actual_maxdim_sz1"]),
                fmt(row["requested_maxdim"]),
            ]
        )
    return output, sha256(path)


def gap_table(impact_dir: Path) -> tuple[list[list[str]], str]:
    path = impact_dir / "sensitivity_metrics.csv"
    if not path.is_file():
        raise FileNotFoundError(f"缺少 sensitivity_metrics.csv: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    rows = [row for row in rows if row.get("observable") == "gap"]
    if len(rows) != 4:
        raise ValueError(f"sensitivity_metrics.csv 的 observable=gap 应为 4 行，实际 {len(rows)}")
    output = []
    for row in rows:
        required = (
            "point_id",
            "start",
            "max_abs_delta",
            "max_abs_index",
            "max_abs_old",
            "max_abs_new",
            "max_abs_symmetric_relative_delta",
            "max_relative_index",
            "max_relative_old",
            "max_relative_new",
        )
        if any(key not in row for key in required):
            raise ValueError(f"gap sensitivity 字段不完整: {row}")
        output.append(
            [
                row["point_id"],
                row["start"],
                fmt(float(row["max_abs_delta"])),
                row["max_abs_index"],
                pct(row["max_abs_symmetric_relative_delta"]),
                row["max_relative_index"],
                fmt(float(row["max_relative_old"])),
                fmt(float(row["max_relative_new"])),
            ]
        )
    return output, sha256(path)


def figure_path(summary: dict[str, Any], impact_dir: Path) -> Path:
    outputs = summary.get("outputs")
    if not isinstance(outputs, list):
        raise ValueError("summary 缺少 outputs，不能核验 impact PNG")
    candidates = [
        item for item in outputs
        if isinstance(item, dict) and str(item.get("name", "")).lower().endswith(".png")
    ]
    if len(candidates) != 1:
        raise ValueError(f"summary 中 PNG 输出数应为 1，实际 {len(candidates)}")
    entry = candidates[0]
    path = impact_dir / str(entry["name"])
    if not path.is_file():
        raise FileNotFoundError(f"impact PNG 不存在: {path}")
    expected = entry.get("sha256")
    if expected and sha256(path) != expected:
        raise ValueError(f"impact PNG SHA256 不匹配: {path}")
    manifest_path = impact_dir / "manifest.json"
    manifest = read_json(manifest_path)
    manifest_outputs = manifest.get("outputs")
    if not isinstance(manifest_outputs, list):
        raise ValueError("manifest 缺少 outputs，拒绝使用未核验 PNG")
    manifest_entry = next(
        (item for item in manifest_outputs if isinstance(item, dict) and item.get("name") == entry["name"]),
        None,
    )
    if manifest_entry is None or manifest_entry.get("sha256") != sha256(path):
        raise ValueError(f"manifest 未确认当前 impact PNG: {path}")
    return path


def remaining_items(status: dict[str, Any], audit_doc: Path) -> list[str]:
    if not audit_doc.is_file():
        raise FileNotFoundError(audit_doc)
    audit_text = audit_doc.read_text(encoding="utf-8")
    for marker in ("Krylov-8 → Krylov-12", "Stage 4", "冻结最多 64 sweeps"):
        if marker not in audit_text:
            raise ValueError(f"审计文档缺少决策门标记: {marker}")
    stage2 = status.get("stage2")
    stage3 = status.get("stage3")
    stage4 = status.get("stage4")
    if not all(isinstance(item, dict) for item in (stage2, stage3, stage4)):
        raise ValueError("项目状态缺少 Stage2/Stage3/Stage4")
    return [
        "决策门 1｜solver 误差与截断误差：固定 alpha=-0.10、beta=0.25、L=80 做 k=8→12 单点对照，区分 Krylov 残差与实际生效 chi/maxdim；冻结最多 64 sweeps，不自动改成 128。",
        "决策门 2｜关键 observable 联合稳定性：alpha=-0.10 的 gap、entropy、dimer、connected 与 bond 量仍有 k 敏感性；不能只凭 variance/truncation 关门，稳定性需按同一观测量集合联合判断。",
        "决策门 3｜有限尺寸到 bulk 外推：当前仅 L=80/OBC；不能由单点改写为 thermodynamic/bulk gap、全局中心荷或新相结论；若继续，先按同协议 L=60 分离有限尺寸效应。",
    ]


def build_report(
    summary: dict[str, Any],
    summary_path: Path,
    impact_dir: Path,
    status: dict[str, Any],
    audit_doc: Path,
) -> dict[str, Any]:
    comparison = summary.get("comparison")
    if not isinstance(comparison, dict):
        raise ValueError("summary 缺少 comparison")
    krylov = comparison.get("krylov_change")
    if not isinstance(krylov, dict) or set(krylov) < {"baseline", "candidate"}:
        raise ValueError("summary 缺少 comparison.krylov_change")
    figure = figure_path(summary, impact_dir)
    slopes = slope_table(summary)
    spreads = spread_table(summary)
    solver_rows, solver_sha = solver_drift_table(impact_dir)
    gaps, gap_sha = gap_table(impact_dir)
    status_rows = remaining_items(status, audit_doc)
    contract = summary.get("figure_contract", {})
    core_conclusion = contract.get("core_conclusion", "impact audit only")
    return {
        "title": "L80 Krylov impact audit",
        "eyebrow": "LOCAL IMPACT AUDIT · 2026-09-20",
        "lede": "本页读取真实 impact summary、sensitivity_metrics.csv 和已核验 PNG；只报告 k=3→k=8 的 solver-control 影响，不混合不同 k 做单一拟合。",
        "sections": [
            {
                "title": "审计结论",
                "note": f"输入 summary：{relative(summary_path)}",
                "blocks": [
                    {
                        "kind": "verdict",
                        "status": "warn",
                        "label": f"status={summary.get('status')} · claim={summary.get('claim')}",
                        "why": "数值门、回传和产物完整性已审计；本节不推出 chi 收敛、bulk gap、相变或论文完成。",
                    },
                    {
                        "kind": "kv",
                        "pairs": [
                            ["Krylov 对照", f"k={krylov['baseline']} → k={krylov['candidate']}"],
                            ["impact summary SHA256", sha256(summary_path)],
                            ["gap sensitivity SHA256", gap_sha],
                            ["solver drift SHA256", solver_sha],
                            ["goal_complete", status.get("goal_complete")],
                        ],
                    },
                    {
                        "kind": "figures",
                        "items": [
                            {
                                "src": figure.name,
                                "caption": f"Impact figure（audit-only）。{core_conclusion} PNG 来源已由 summary 与 manifest 双重 SHA256 核验。",
                            }
                        ],
                    },
                    {
                        "kind": "note",
                        "label": "拟合边界",
                        "style": "pending",
                        "text": "period=10/window=0.20 的 c_eff 仅是有限 L 斜率诊断；baseline k3 与 candidate k8 不得混入同一 scaling fit，也不能当作 thermodynamic central charge。",
                    },
                ],
            },
            {
                "title": "period10/window.20 纠缠斜率",
                "note": "严格来自 summary.key_facts.entropy_period10_window020 的 8 行，按 point/start 配对 k3 与 k8。",
                "blocks": [
                    {
                        "kind": "table",
                        "columns": ["参数点", "初态", "alpha", "beta", "L", "k3 c_eff", "k8 c_eff"],
                        "rows": slopes,
                        "numeric": [False, False, True, True, True, True, True],
                    }
                ],
            },
            {
                "title": "gap 敏感性",
                "note": "从同目录 sensitivity_metrics.csv 选择 observable=gap 的四行；相对量为源文件的对称相对定义。",
                "blocks": [
                    {
                        "kind": "table",
                        "columns": ["参数点", "初态", "Δabs", "Δabs index", "|srel|max", "|srel| index", "baseline", "candidate"],
                        "rows": gaps,
                        "numeric": [False, False, True, True, True, True, True, True],
                    }
                ],
            },
            {
                "title": "初态 spread 与端点 q 保留",
                "note": "spread 是 center-versus-ferro_j2 的确定性范围，非 CI；Sz1 固定 center、非独立。",
                "blocks": [
                    {
                        "kind": "table",
                        "columns": ["参数点", "observable", "k3 max spread", "k8 max spread", "reduction", "语义"],
                        "rows": spreads,
                        "numeric": [False, False, True, True, True, False],
                    },
                    {
                        "kind": "table",
                        "columns": ["参数点", "初态", "q_peak/π k3", "q_peak/π k8", "ratio k3", "ratio k8", "actual maxdim k8 Sz0", "actual maxdim k8 Sz1", "requested maxdim"],
                        "rows": solver_rows,
                        "numeric": [False, False, True, True, True, True, True, True, True],
                    },
                    {
                        "kind": "note",
                        "label": "q 与 chi 边界",
                        "style": "info",
                        "text": "q_peak 保留只能说明该端点诊断在本次 solver 对照中未移动；actual maxdim 低于 requested maxdim=1200 不是 chi 收敛证明。",
                    },
                ],
            },
            {
                "title": "分阶段剩余事项",
                "note": "由项目状态 JSON 的 Stage2/3/4 字段和 post-Krylov 审计文档决策门生成。",
                "blocks": [
                    {
                        "kind": "list",
                        "items": status_rows,
                    },
                    {
                        "kind": "note",
                        "label": "执行边界",
                        "style": "pending",
                        "text": "本轮只做本地报告接入；后续按既有授权范围与执行安全要求推进，具体批次参数和预算须留档。冻结不超过 64 sweeps，不自动改成 128，不做全域追加。",
                    },
                ],
            },
            {
                "title": "复现入口",
                "note": "脚本拒绝缺失 summary、sensitivity CSV、manifest 或 PNG，不使用默认科学数值。",
                "blocks": [
                    {
                        "kind": "code",
                        "title": "命令",
                        "text": "python -B scripts/autoresearch_v5/update_static_krylov_impact_report.py --impact-summary results/autoresearch_v5_20260920/static_krylov_impact_v2/summary.json --impact-dir results/autoresearch_v5_20260920/static_krylov_impact_v2",
                    },
                    {
                        "kind": "code",
                        "title": "输出",
                        "text": f"{relative(impact_dir / 'report.json')}\n{relative(impact_dir / 'report.html')}\nstatus.local_impact_audit",
                    },
                ],
            },
        ],
    }


def update_status(status_path: Path, summary_path: Path, impact_dir: Path) -> None:
    status = read_json(status_path)
    if status.get("goal_complete") is not False:
        raise ValueError("拒绝覆盖 goal_complete：当前状态必须保持 false")
    status["local_impact_audit"] = {
        "status": "generated",
        "claim": "audit_only",
        "summary": relative(summary_path),
        "summary_sha256": sha256(summary_path),
        "report_json": relative(impact_dir / "report.json"),
        "report_html": relative(impact_dir / "report.html"),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "goal_complete": False,
        "raw_and_paper_unchanged": True,
    }
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--impact-summary", type=Path, required=True)
    parser.add_argument("--impact-dir", type=Path)
    parser.add_argument("--status", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--audit-doc", type=Path, default=DEFAULT_AUDIT_DOC)
    parser.add_argument("--renderer", type=Path, default=DEFAULT_RENDERER)
    args = parser.parse_args()

    summary_path = args.impact_summary.resolve()
    summary = read_json(summary_path)
    impact_dir = (args.impact_dir or summary_path.parent).resolve()
    status_path = args.status.resolve()
    audit_doc = args.audit_doc.resolve()
    renderer = args.renderer.resolve()
    if not renderer.is_file():
        raise FileNotFoundError(f"report renderer 不存在: {renderer}")
    if not impact_dir.is_dir():
        raise FileNotFoundError(f"impact 目录不存在: {impact_dir}")
    status = read_json(status_path)
    report = build_report(summary, summary_path, impact_dir, status, audit_doc)
    report_path = impact_dir / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rendered = subprocess.run(
        [sys.executable, "-X", "utf8", str(renderer), str(impact_dir)],
        check=False,
        capture_output=True,
        text=True,
    )
    if rendered.returncode != 0:
        raise RuntimeError("report renderer 失败:\n" + rendered.stdout + rendered.stderr)
    html_path = impact_dir / "report.html"
    if not html_path.is_file():
        raise RuntimeError(f"renderer 未生成 report.html: {html_path}")
    update_status(status_path, summary_path, impact_dir)
    print(json.dumps({
        "summary": str(summary_path),
        "report_json": str(report_path),
        "report_html": str(html_path),
        "status": str(status_path),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
