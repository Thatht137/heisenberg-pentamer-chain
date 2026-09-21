#!/usr/bin/env python3
"""将近零点 8-spin oracle 的真实输出整理为离线中文报告。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUT_DEFAULT = ROOT / "results" / "autoresearch_v5_20260919" / "near_zero_alpha_oracle_v2"
OUTPUT_DEFAULT = ROOT / "results" / "autoresearch_v5_20260919" / "near_zero_alpha_mechanism_report_v2"
RENDERER_DEFAULT = Path.home() / ".codex" / "skills" / "report" / "render_report.py"

VALIDATION_GATE_KEYS = (
    "alpha0_multiplets",
    "bit_vs_full_construction",
    "dimensions",
    "eigen_normalization",
    "eigen_orthogonality",
    "eigen_residuals",
    "hermiticity",
    "nonzero_su2_multiplets",
    "three_spin_projection",
    "total_sz",
    "two_spin_benchmark",
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} 必须是 JSON 对象")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "通过" if value else "未通过"
    if isinstance(value, float):
        return str(value) if not math.isfinite(value) else f"{value:.8g}"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return str(value)


def scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def rows_from_mapping(mapping: dict[str, Any]) -> list[list[str]]:
    return [[str(key), fmt(value), "—"] for key, value in mapping.items()]


def rows_from_records(records: list[dict[str, Any]], columns: list[str]) -> list[list[str]]:
    return [[fmt(record.get(column)) for column in columns] for record in records]


def table(title: str, columns: list[str], rows: list[list[Any]]) -> dict[str, Any]:
    return {
        "kind": "card",
        "title": title,
        "blocks": [{
            "kind": "table",
            "columns": [str(item) for item in columns],
            "rows": [[fmt(item) for item in row] for row in rows],
        }],
    }


def verify_checksums(input_dir: Path, checksum_path: Path) -> dict[str, str]:
    """只接受输入目录内的三件结果文件，避免路径歧义。"""
    verified: dict[str, str] = {}
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        parts = text.split(maxsplit=1)
        if len(parts) != 2 or len(parts[0]) != 64:
            raise ValueError(f"无法解析 checksum 行：{line}")
        expected, relative = parts[0].lower(), parts[1].lstrip("* ").replace("\\", "/")
        if relative not in {"spec.json", "oracle_points.csv", "summary.json"}:
            raise ValueError(f"checksum 含非结果输入路径：{relative}")
        candidate = input_dir / relative
        if not candidate.is_file():
            raise FileNotFoundError(f"checksum 指向的文件不存在：{relative}")
        actual = sha256(candidate)
        if actual != expected:
            raise ValueError(f"checksum 不匹配：{relative}")
        verified[relative] = actual
    required = {"spec.json", "oracle_points.csv", "summary.json"}
    if set(verified) != required:
        raise ValueError(f"checksums 必须且只能覆盖 spec/points/summary：{sorted(set(verified) ^ required)}")
    return verified


def verify_backend_hashes(summary: dict[str, Any]) -> dict[str, str]:
    backend = summary.get("backend")
    if not isinstance(backend, dict):
        raise ValueError("summary.backend 缺失，不能验证 backend 源码/test hash")
    paths = {
        "script_sha256": ROOT / "scripts" / "autoresearch_v5" / "validate_near_zero_alpha_oracle.py",
        "test_sha256": ROOT / "scripts" / "autoresearch_v5" / "test_near_zero_alpha_oracle.py",
    }
    verified: dict[str, str] = {}
    for key, path in paths.items():
        expected = backend.get(key)
        if not isinstance(expected, str) or not path.is_file():
            raise ValueError(f"缺少 backend hash 或文件：{key} / {path}")
        actual = sha256(path)
        if actual != expected:
            raise ValueError(f"backend hash 不匹配：{path}")
        verified[str(path.relative_to(ROOT)).replace("\\", "/")] = actual
    return verified


def read_points(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        required = {"point_role", "alpha", "beta", "gap_over_alpha2", "predicted_gap_over_alpha2", "prediction_relative_error"}
        if not required.issubset(fields):
            raise ValueError(f"oracle_points.csv 缺少明确列：{sorted(required - set(fields))}")
        return fields, [dict(row) for row in reader]


def validate_spec(spec: dict[str, Any]) -> None:
    model = spec.get("model")
    if not isinstance(model, dict) or model.get("bond_pattern") != "[1,1,alpha,beta,alpha,1,1]" or model.get("sites") != 8:
        raise ValueError("spec.model 不是预注册的 8-spin trimer-dimer-trimer 构造")


def require_schema(summary: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    required = ("validation_gates", "validation_gate_pass", "matrix_and_eigen_checks", "benchmarks", "alpha0_checks", "prediction", "point_counts")
    missing = [key for key in required if key not in summary]
    if missing:
        raise ValueError(f"summary.json 缺少最终 schema 字段：{', '.join(missing)}")
    if summary.get("schema") != "near_zero_alpha_oracle/v2":
        raise ValueError("summary.schema 不是 near_zero_alpha_oracle/v2")
    gates = summary["validation_gates"]
    if not isinstance(gates, dict) or set(gates) != set(VALIDATION_GATE_KEYS) or any(type(gates[key]) is not bool for key in VALIDATION_GATE_KEYS):
        raise ValueError("validation_gates 必须恰好包含 11 个固定键，且每个值必须是 bool")
    if summary["validation_gate_pass"] is not True or summary.get("status") != "pass" or not all(gates.values()):
        raise ValueError("summary 总验证门未通过，拒绝生成 pass 报告")
    counts = summary["point_counts"]
    if not isinstance(counts, dict) or counts.get("total") != 47 or counts.get("grid_total") != 45 or counts.get("finite_alpha_controls") != 2:
        raise ValueError("summary.point_counts 不是预期的 47 行（45 grid + 2 finite-alpha control）")
    prediction = summary["prediction"]
    if not isinstance(prediction, dict) or "asymptotic_gate" not in prediction:
        raise ValueError("summary.prediction.asymptotic_gate 缺失")
    asymptotic = prediction["asymptotic_gate"]
    if not isinstance(asymptotic, dict) or asymptotic.get("all_pass") is not True or not isinstance(asymptotic.get("groups"), list) or len(asymptotic["groups"]) != 6:
        raise ValueError("summary.prediction.asymptotic_gate 必须 all_pass=true 且含 6 组")
    return (
        summary["validation_gates"],
        summary["matrix_and_eigen_checks"],
        summary["benchmarks"],
        summary["alpha0_checks"],
        prediction,
    )


def gate_rows(value: Any) -> list[list[str]]:
    if isinstance(value, dict):
        return rows_from_mapping(value)
    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        keys = sorted({key for item in value for key in item})
        return rows_from_records(value, keys)
    return [["值", fmt(value), "—"]]


def benchmark_rows(value: dict[str, Any]) -> list[list[str]]:
    rows = []
    projection = value.get("three_spin_projection", {})
    if isinstance(projection, dict):
        rows.append(["three_spin_projection", fmt(projection.get("max_coefficient_error")), fmt(projection.get("max_projection_matrix_residual")), fmt(projection.get("ground_energy")), fmt(projection.get("ground_degeneracy"))])
    two_spin = value.get("two_spin", {})
    if isinstance(two_spin, dict):
        rows.append(["two_spin", fmt(two_spin.get("max_abs_error")), fmt(two_spin.get("hermiticity_error")), "—", "—"])
    return rows


def alpha0_rows(value: dict[str, Any]) -> list[list[str]]:
    rows = []
    for beta, record in sorted(value.items(), key=lambda item: float(item[0])):
        if not isinstance(record, dict):
            continue
        rows.append([beta, fmt(record.get("pass")), fmt(record.get("energy_error")), fmt(record.get("s2_multiplet_error")), fmt(record.get("full_ground_degeneracy"))])
    return rows


def percent(value: Any) -> str:
    try:
        return f"{100.0 * float(value):.2f}%"
    except (TypeError, ValueError):
        return fmt(value)


def merge_control_rows(records: list[dict[str, Any]], points: list[dict[str, str]]) -> list[dict[str, Any]]:
    merged = []
    for record in records:
        try:
            alpha = float(record["alpha"])
            beta = float(record["beta"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("finite_alpha_controls 缺少 alpha/beta") from exc
        match = next((row for row in points if abs(float(row["alpha"]) - alpha) < 1e-12 and abs(float(row["beta"]) - beta) < 1e-12), None)
        if match is None:
            raise ValueError(f"finite_alpha_control 未在 oracle_points.csv 找到：alpha={alpha}, beta={beta}")
        merged.append({
            "alpha": match["alpha"],
            "beta": match["beta"],
            "gap_sz1_minus_sz0": match["gap_sz1_minus_sz0"],
            "gap_over_alpha2": match["gap_over_alpha2"],
            "predicted_gap_over_alpha2": match["predicted_gap_over_alpha2"],
            "prediction_relative_error": match["prediction_relative_error"],
            "asymptotic_gate_applicable": match["asymptotic_gate_applicable"],
        })
    return merged


def make_report(summary: dict[str, Any], spec: dict[str, Any], fields: list[str], points: list[dict[str, str]], verified: dict[str, str], backend_hashes: dict[str, str]) -> dict[str, Any]:
    validation, matrix, benchmarks, alpha0, prediction = require_schema(summary)
    asymptotic = prediction["asymptotic_gate"]
    groups = asymptotic.get("groups")
    if not isinstance(groups, list) or not all(isinstance(item, dict) for item in groups):
        raise ValueError("summary.prediction.asymptotic_gate.groups 必须是记录列表")
    group_columns = ["beta", "sign", "smallest_alpha", "smallest_abs_relative_error", "second_abs_relative_error", "small_alpha_improves_by_25pct", "pass"]
    group_rows = rows_from_records(groups, group_columns)
    finite_controls = prediction.get("finite_alpha_controls")
    if not isinstance(finite_controls, list) or not all(isinstance(item, dict) for item in finite_controls):
        raise ValueError("summary.prediction.finite_alpha_controls 必须是记录列表")
    finite_controls = merge_control_rows(finite_controls, points)
    control_columns = ["alpha", "beta", "gap_sz1_minus_sz0", "gap_over_alpha2", "predicted_gap_over_alpha2", "prediction_relative_error", "asymptotic_gate_applicable"]
    report_status = summary["validation_gate_pass"] is True
    verdict_status = "good" if report_status else "warn"
    grid_columns = ["point_role", "alpha", "beta", "gap_sz1_minus_sz0", "gap_over_alpha2", "predicted_gap_over_alpha2", "prediction_relative_error"]
    control_note = "；".join(f"α={item.get('alpha')}、β={item.get('beta')} 的预测相对误差 {percent(item.get('prediction_relative_error'))}" for item in finite_controls)
    return {
        "title": "近零 α 交换机制：8-spin oracle 独立检验",
        "eyebrow": "AUTORESEARCH V5 · 2026-09-19 · NUMPY ORACLE",
        "lede": "本报告只整合通过输入 checksum 与源码/test hash 的实际结果；局部受控交换不外推为新相或全域单相。",
        "sections": [
            {"title": "范围与结构", "note": "8-spin oracle 的结构先于数值结论。", "blocks": [
                {"kind": "verdict", "status": "warn", "label": "局部机制检验，不是相图判定", "why": "[1,1,α,β,α,1,1] 是 trimer–dimer–trimer，不是两个完整五聚体。"},
                {"kind": "table", "columns": ["项目", "口径"], "rows": [
                    ["键序列", "[1,1,α,β,α,1,1]；8 个 spin-1/2，OBC"],
                    ["定义", str(prediction.get("definition", "gap=E0(Sz=1)-E0(Sz=0) in this 8-spin oracle only"))],
                    ["后端", "Python + NumPy；不声称使用 XDiag"],
                    ["未覆盖", "新相、全域单相、完整链形状因子；全链验证仍待完成"],
                ]},
                {"kind": "equation", "tex": r"\Delta_8/\alpha^2\to2/(9\beta)"},
                {"kind": "text", "text": "若实际 gate 通过，该式仅支持固定 β>0、足够小 |α| 的局部受控交换；不证明新相或全域单相。"},
            ]},
            {"title": "数值 gates 与构造校验", "note": "validation_gates 是总门；任一失败都不升级为 pass。", "blocks": [
                table("最终 validation_gates", ["gate", "值", "备注"], gate_rows(validation)),
                table("两构造与本征残差", ["项目", "值", "备注"], rows_from_mapping(matrix)),
                table("三自旋投影与两自旋基准", ["benchmark", "最大系数误差", "投影残差/厄米误差", "基态能量", "简并度"], benchmark_rows(benchmarks)),
                table("alpha=0 checks", ["β", "pass", "能量误差", "S² 多重态误差", "基态简并度"], alpha0_rows(alpha0)),
            ]},
            {"title": "最小 |α|：β 与 α 正负两侧", "note": "读取 prediction.asymptotic_gate.groups 的实际记录。", "blocks": [
                table("每个 β 与 α 正负两侧的最小 α / ratio", ["β", "α侧", "最小|α|", "最小相对误差", "次小相对误差", "改善≥25%", "gate"], group_rows),
                {"kind": "text", "text": f"渐近 gate 总状态：{fmt(asymptotic.get('all_pass'))}；仅适用于 {fmt(asymptotic.get('criteria', {}).get('applies_only_to'))}。"},
            ]},
            {"title": "全 grid 误差与渐近适用域", "note": f"oracle_points.csv 原样读取 {len(points)} 行；不删点、不用拟合替代原始表。", "blocks": [
                table("有限 α 控制点", ["α", "β", "gap", "gap/α²", "预测系数", "相对误差", "适用渐近门"], rows_from_records(finite_controls, control_columns)),
                {"kind": "note", "label": "有限 α 控制点不适用渐近式", "style": "pending", "text": f"当前 DMRG 相关控制点的预测相对误差为 {control_note}；公式 gap/α² 不能直接用于这些有限 α 点。"},
                table("全 grid 核心列", ["点型", "α", "β", "gap", "gap/α²", "预测系数", "相对误差"], [[row.get(field, "") for field in grid_columns] for row in points]),
                table("全 grid QA 汇总", ["QA 项", "值"], [["总点数", summary["point_counts"].get("total")], ["grid 点数", summary["point_counts"].get("grid_total")], ["最大本征残差", matrix.get("max_all_residual")], ["最大归一化误差", matrix.get("max_all_norm_error")], ["最大正交误差", matrix.get("max_all_orthogonality_error")]]),
                {"kind": "note", "label": "渐近适用域", "text": f"{fmt(asymptotic.get('criteria', {}).get('applies_only_to'))}；finite_alpha_control 不套 2% 渐近门。"},
            ]},
            {"title": "结论边界与可复现入口", "note": "局部 8-spin 检验不替代完整链动力学和形状因子验证。", "blocks": [
                {"kind": "verdict", "status": verdict_status, "label": "局部 gap/α² 检验已按总门汇总" if report_status else "总门未通过或未达到 pass", "why": "即使 asymptotic_gate 通过，也只支持局部受控交换，不证明新相或全域单相。"},
                {"kind": "verdict", "status": "warn", "label": "形状因子全链验证仍待完成", "why": "8-spin trimer–dimer–trimer 不能替代完整链的动量折叠、谱权和形状因子验证。"},
                {"kind": "list", "title": "不支持的外推", "items": ["不由局部拟合命名新相。", "不由局部 oracle 证明全域单相。", "不把 NumPy 结果写成 XDiag。", "不把 8-spin 构造当作两个完整五聚体。"]},
                {"kind": "kv", "pairs": [
                    ["输入 hash", "; ".join(f"{key}={value}" for key, value in sorted(verified.items()))],
                    ["backend/test hash", "; ".join(f"{key}={value}" for key, value in sorted(backend_hashes.items()))],
                    ["报告脚本", "scripts/autoresearch_v5/report_near_zero_alpha_oracle.py"],
                    ["离线渲染", "report.html 由 skills/report/render_report.py 生成"],
                ]},
            ]},
        ],
    }


def write_output(report: dict[str, Any], output_dir: Path, input_dir: Path, verified: dict[str, str], backend_hashes: dict[str, str], summary: dict[str, Any], fields: list[str], renderer: Path) -> dict[str, Any]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"拒绝覆盖已有非空目录：{output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not renderer.is_file():
        raise FileNotFoundError(f"找不到 report renderer：{renderer}")
    command = [sys.executable, "-B", "-X", "utf8", str(renderer), str(output_dir)]
    subprocess.run(command, check=True)
    html_path = output_dir / "report.html"
    manifest = {
        "schema_version": 1,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_dir": str(input_dir.relative_to(ROOT)).replace("\\", "/"),
        "summary_status": summary.get("status"),
        "checksums_verified": True,
        "input_files": {**{name: {"sha256": digest} for name, digest in sorted(verified.items())}, **{name: {"sha256": digest} for name, digest in sorted(backend_hashes.items())}},
        "oracle_points_columns": fields,
        "output_files": {"report.json": sha256(report_path), "report.html": sha256(html_path)},
        "render_command": command,
        "backend_note": "数值结果由 NumPy oracle 提供；本报告未使用或声称使用 XDiag。",
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "checksums.sha256").write_text("".join(f"{sha256(path)}  {path.name}\n" for path in (report_path, html_path, manifest_path)), encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=INPUT_DEFAULT)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DEFAULT)
    parser.add_argument("--renderer", type=Path, default=RENDERER_DEFAULT)
    args = parser.parse_args()
    input_dir = args.input_dir.resolve()
    required = [input_dir / name for name in ("summary.json", "spec.json", "oracle_points.csv", "checksums.sha256")]
    missing = [path.name for path in required if not path.is_file()]
    if missing:
        print(json.dumps({"status": "waiting", "missing": missing, "input_dir": str(input_dir)}, ensure_ascii=False))
        return 2
    summary = load_json(input_dir / "summary.json")
    verified = verify_checksums(input_dir, input_dir / "checksums.sha256")
    backend_hashes = verify_backend_hashes(summary)
    spec = load_json(input_dir / "spec.json")
    validate_spec(spec)
    fields, points = read_points(input_dir / "oracle_points.csv")
    report = make_report(summary, spec, fields, points, verified, backend_hashes)
    manifest = write_output(report, args.output_dir.resolve(), input_dir, verified, backend_hashes, summary, fields, args.renderer.resolve())
    print(json.dumps({"status": "pass", "output_dir": str(args.output_dir.resolve()), "manifest": manifest}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
