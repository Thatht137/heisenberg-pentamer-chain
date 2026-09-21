#!/usr/bin/env python3
"""生成 static Krylov k12 gate 的只读、版本化报告。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATUS = ROOT / "results/research_progress/project_closeout_status_20260919.json"
DEFAULT_OUT = ROOT / "results/autoresearch_v5_20260920/static_krylov_k12_gate_report_v1"


class GateReportError(ValueError):
    """输入或输出门禁错误。"""


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise GateReportError(f"找不到 JSON: {path}") from exc
    except json.JSONDecodeError as exc:
        raise GateReportError(f"JSON 无法解析: {path}: {exc}") from exc


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _pick(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return default


def _json_text(value: Any) -> str:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(", ", ": "))
    if value is None:
        return "未提供"
    if isinstance(value, bool):
        return "是" if value else "否"
    return str(value)


def _relative_or_text(value: Any, root: Path) -> str:
    if not isinstance(value, str):
        return _json_text(value)
    candidate = Path(value)
    if candidate.is_absolute():
        try:
            return str(candidate.resolve().relative_to(root.resolve()))
        except ValueError:
            return str(candidate)
    return value


def _find_mapping(source: Mapping[str, Any], aliases: Iterable[str]) -> Any:
    for key in aliases:
        value = source.get(key)
        if isinstance(value, (Mapping, list)):
            return value
    for container_key in ("k12_gate", "terminal", "finalize", "summary", "results"):
        child = source.get(container_key)
        if isinstance(child, Mapping):
            for key in aliases:
                value = child.get(key)
                if isinstance(value, (Mapping, list)):
                    return value
    return None


def load_gate_source(
    state: str,
    status_json: Path = DEFAULT_STATUS,
    terminal_summary: Path | None = None,
) -> tuple[dict[str, Any], Path]:
    """读取当前状态或未来终态摘要，不启动任何计算。"""
    if state == "prepared-only":
        source = _mapping(_read_json(status_json))
        gate = source.get("k12_gate")
        if not isinstance(gate, Mapping):
            raise GateReportError(f"状态文件缺少 k12_gate: {status_json}")
        return dict(gate), status_json

    if terminal_summary is None:
        raise GateReportError("terminal 状态需要 --terminal-summary")
    source = _mapping(_read_json(terminal_summary))
    gate = source.get("k12_gate")
    if isinstance(gate, Mapping):
        return dict(gate), terminal_summary
    # 允许 future finalizer 直接输出 gate 摘要，或包在 terminal/finalize/summary 下。
    if any(key in source for key in ("parameters", "validator", "comparison", "validation", "manifest_sha256")):
        return dict(source), terminal_summary
    for key in ("terminal", "finalize", "summary", "results"):
        child = source.get(key)
        if isinstance(child, Mapping):
            if isinstance(child.get("k12_gate"), Mapping):
                return dict(child["k12_gate"]), terminal_summary
            if any(k in child for k in ("parameters", "validator", "comparison", "validation", "manifest_sha256")):
                return dict(child), terminal_summary
    raise GateReportError(f"终态摘要缺少 k12 gate 字段: {terminal_summary}")


def _result_value(gate: Mapping[str, Any], aliases: Iterable[str], state: str) -> Any:
    if state == "prepared-only":
        return {"status": "not_run", "detail": "prepared-only：尚未执行远端 validator/comparison"}
    value = _find_mapping(gate, aliases)
    if value is not None:
        return value
    return {
        "status": "not_run" if state == "prepared-only" else "not_provided",
        "detail": (
            "prepared-only：尚未执行远端 validator/comparison"
            if state == "prepared-only"
            else "terminal summary 未提供 validator/comparison 结果"
        ),
    }


def _result_rows(value: Any) -> list[list[str]]:
    if isinstance(value, Mapping):
        return [[str(key), _json_text(item)] for key, item in value.items()]
    if isinstance(value, list):
        return [["items", _json_text(value)]]
    return [["result", _json_text(value)]]


def _status_label(state: str, gate: Mapping[str, Any]) -> tuple[str, str, str]:
    status = str(_pick(gate, "status", "state", default="unknown"))
    claim = str(_pick(gate, "claim", "interpretation", default="audit_only"))
    if state == "prepared-only":
        return "warn", "PREPARED ONLY · AUDIT ONLY", f"当前状态为 {status}；未上传、未启动远端 k12。"
    if status == "terminal_accepted" or str(_pick(gate, "accepted", "passed", default="")).lower() in {"true", "pass", "passed", "success"}:
        return "good", "TERMINAL SUMMARY · AUDIT ONLY", f"终态摘要为 {status}；仍受 {claim} 边界约束。"
    return "warn", "TERMINAL SUMMARY · REVIEW", f"终态摘要为 {status}；需按 validator/comparison 结果继续审计。"


def build_report(gate: Mapping[str, Any], state: str, source_path: Path, root: Path = ROOT) -> dict[str, Any]:
    """把 gate 摘要映射为通用 report.json 文档。"""
    if state not in {"prepared-only", "terminal"}:
        raise GateReportError(f"未知 state: {state}")
    gate = dict(gate)
    parameters = _mapping(gate.get("parameters"))
    smoke = _mapping(_pick(gate, "local_smoke_pass", "local_smoke", "smoke", default={}))
    upload = _mapping(_pick(gate, "upload_rejected_external_review", "upload", "remote", default={}))
    server = _mapping(gate.get("server_snapshot"))
    eta = _mapping(gate.get("eta"))
    severity, label, why = _status_label(state, gate)
    validator = _result_value(
        gate,
        ("validator", "validators", "validation", "validation_result", "validation_results", "validator_result", "validator_results"),
        state,
    )
    comparison = _result_value(
        gate,
        ("comparison", "compare", "comparison_audit", "comparison_result", "comparison_results", "comparison_audit_current"),
        state,
    )

    parameter_rows = []
    for key in (
        "alpha", "beta", "L", "n_units", "eigsolve_krylovdim", "nsweeps", "maxdim", "cutoff", "threads", "q_count",
        "init_modes", "save_state", "enriched_diagnostics", "concurrency", "retry_policy", "warmstart", "no_128",
    ):
        parameter_rows.append([key, _json_text(parameters.get(key, "未提供"))])

    source_text = _relative_or_text(str(source_path), root)
    manifest = _relative_or_text(_pick(gate, "release_manifest", "manifest", default="未提供"), root)
    run_spec = _relative_or_text(_pick(gate, "run_spec", "spec", default="未提供"), root)
    smoke_artifact = _relative_or_text(_pick(smoke, "artifact", "path", default="未提供"), root)

    next_gate = (
        [
            "取得明确外传授权后，执行非覆盖 upload 与远端 preflight；本地报告不执行该动作。",
            "远端仅运行单点 L80/k12；回收后先过逐文件 hash、validator 与 comparison，再决定是否进入下一门。",
            "在独立验证完成前，不把 k12 gate 转写为新相、热力学 c=1 或论文结论。",
        ]
        if state == "prepared-only"
        else [
            "保留 audit_only：逐项复核终态 validator、comparison 和回收文件 hash。",
            "若所有审计门通过，再由主流程决定是否申请下一点；本报告不授权扩大计算或改变论文结论。",
        ]
    )

    report = {
        "schema_version": 1,
        "title": "Static Krylov k12 Gate",
        "eyebrow": f"LOCAL GATE · {label}",
        "url": "",
        "lede": "独立 k12 单点门禁记录；本页只呈现可追溯的准备/终态证据，不作物理结论。",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "metadata": {"state": state, "source": source_text, "claim": _pick(gate, "claim", default="audit_only")},
        "sections": [
            {
                "title": "Gate 状态",
                "blocks": [
                    {"kind": "verdict", "status": severity, "label": label, "why": why},
                    {
                        "kind": "kv",
                        "pairs": [
                            ["state", state],
                            ["status", _json_text(_pick(gate, "status", "state", default="未提供"))],
                            ["claim", _json_text(_pick(gate, "claim", default="audit_only"))],
                            ["package_ready", _json_text(_pick(gate, "package_ready", default="未提供"))],
                            ["launch_ready", _json_text(_pick(gate, "launch_ready", default="未提供"))],
                            ["goal_complete", _json_text(_pick(gate, "goal_complete", default="未提供"))],
                            ["source", source_text],
                        ],
                    },
                ],
            },
            {"title": "运行参数", "blocks": [{"kind": "table", "columns": ["参数", "值"], "rows": parameter_rows}]},
            {
                "title": "本地 smoke 与 preflight",
                "blocks": [
                    {
                        "kind": "kv",
                        "pairs": [
                            ["artifact", smoke_artifact],
                            ["status", _json_text(_pick(smoke, "status", default="未提供"))],
                            ["Julia", _json_text(_pick(smoke, "julia_version", default="未提供"))],
                            ["role", _json_text(_pick(smoke, "role", default="parser/execution evidence only"))],
                            ["not_remote_validation", _json_text(_pick(smoke, "not_remote_validation", default=True))],
                            ["preflight", _relative_or_text(_pick(smoke, "preflight", default="未提供"), root)],
                            ["dry_run", _json_text(_pick(smoke, "dry_run", default="未提供"))],
                            ["unit_tests", _json_text(_pick(smoke, "unit_tests", default="未提供"))],
                            ["remote Julia required", _json_text(_pick(gate, "remote_julia_version_required", default="1.12.3"))],
                        ],
                    },
                    {"kind": "note", "label": "证据边界", "style": "warning", "text": "L10 smoke 的 Julia 1.11.5 只证明 parser/execution；不替代远端 Julia 1.12.3 验证。"},
                ],
            },
            {
                "title": "Manifest / hash / provenance",
                "blocks": [
                    {
                        "kind": "kv",
                        "pairs": [
                            ["release_manifest", manifest],
                            ["manifest_sha256", _json_text(_pick(gate, "manifest_sha256", "manifest_sha", default="未提供"))],
                            ["run_spec", run_spec],
                            ["run_spec_sha256", _json_text(_pick(gate, "run_spec_sha256", "spec_sha256", default="未提供"))],
                            ["payload files", _json_text(_pick(gate, "payload_file_count", default="未提供"))],
                            ["control files", _json_text(_pick(gate, "control_manifest_file_count", default="未提供"))],
                            ["total files", _json_text(_pick(gate, "total_file_count", default="未提供"))],
                            ["payload bytes", _json_text(_pick(gate, "payload_bytes", default="未提供"))],
                        ],
                    }
                ],
            },
            {
                "title": "Validator 与 comparison",
                "blocks": [
                    {"kind": "table", "columns": ["validator 字段", "值"], "rows": _result_rows(validator)},
                    {"kind": "table", "columns": ["comparison 字段", "值"], "rows": _result_rows(comparison)},
                    {"kind": "note", "label": "解释", "style": "info", "text": "prepared-only 阶段不执行 validator/comparison；terminal 阶段只转录已经独立完成的终态验收与比较，不在报告生成器中重算。"},
                ],
            },
            {
                "title": "Upload / remote state",
                "blocks": [
                    {
                        "kind": "kv",
                        "pairs": [
                            ["upload status", _json_text(_pick(upload, "status", default="未提供"))],
                            ["upload performed", _json_text(_pick(upload, "upload_performed", default=_pick(gate, "upload_performed", default=False)))],
                            ["ssh/scp performed", _json_text(_pick(upload, "ssh_or_scp_performed", default=False))],
                            ["partial side effects", _json_text(_pick(upload, "partial_side_effects", default=False))],
                            ["no remote side effects", _json_text(_pick(gate, "no_remote_side_effects", default="未提供"))],
                            ["remote Julia", _json_text(_pick(gate, "remote_julia_version_required", default="1.12.3"))],
                            ["server snapshot", _json_text(server)],
                            ["ETA / timeout", _json_text(eta)],
                        ],
                    },
                    {"kind": "note", "label": "远端边界", "style": "warning", "text": "本报告不会上传、SSH、启动 Julia 或修改远端状态。"},
                ],
            },
            {
                "title": "Audit-only 边界与下一门",
                "blocks": [
                    {
                        "kind": "list",
                        "title": "本报告不声称",
                        "items": ([
                            "不从这个单点引入新相，也不据此宣称全域单相。",
                            "不把 k8→k12 稳定等同于热力学极限、中心荷或完整有限尺寸标度。",
                            "不改变既有相图证据边界；本门只关闭 Krylov 子空间稳定性问题。",
                        ] if state == "terminal" else [
                            "不引入新相，不宣称全域单相。",
                            "不宣称热力学 c=1 或全局收敛。",
                            "不替代论文/原始数据验收，也不改变 goal_complete=false。",
                        ]),
                    },
                    {"kind": "list", "title": "下一门", "items": next_gate},
                ],
            },
        ],
    }
    return report


def write_report(report: Mapping[str, Any], out_dir: Path) -> Path:
    """只允许写入新的空目录，避免覆盖既有发布包。"""
    if out_dir.exists():
        if not out_dir.is_dir():
            raise GateReportError(f"输出路径不是目录: {out_dir}")
        if any(out_dir.iterdir()):
            raise GateReportError(f"拒绝覆盖非空输出目录: {out_dir}")
    else:
        out_dir.mkdir(parents=True, exist_ok=False)
    path = out_dir / "report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return path


def _resolve(root: Path, value: str | None, default: Path | None = None) -> Path:
    path = Path(value) if value else (default or root)
    return path if path.is_absolute() else root / path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", choices=("prepared-only", "terminal"), default="prepared-only")
    parser.add_argument("--status-json", default=str(DEFAULT_STATUS))
    parser.add_argument("--terminal-summary")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    status_json = _resolve(root, args.status_json, DEFAULT_STATUS)
    terminal_summary = _resolve(root, args.terminal_summary) if args.terminal_summary else None
    out_dir = _resolve(root, args.out, DEFAULT_OUT)
    try:
        gate, source = load_gate_source(args.state, status_json, terminal_summary)
        report = build_report(gate, args.state, source, root)
        path = write_report(report, out_dir)
    except GateReportError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"status": "pass", "state": args.state, "report_json": str(path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
