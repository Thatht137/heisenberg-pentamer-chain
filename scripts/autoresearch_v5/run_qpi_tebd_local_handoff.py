#!/usr/bin/env python3
"""对已回传的严格 q=pi 结果执行独立本地验收。"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ANALYZER = HERE / "analyze_qpi_tebd_production.py"
COARSE = "cell-alpha023-qpi-dt0025-t30"
REFINED = "cell-alpha023-qpi-dt00125-t30"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_cell(cell: Path) -> dict[str, object]:
    failures: list[str] = []
    manifest = json.loads((cell / "manifest.json").read_text(encoding="utf-8"))
    status = json.loads((cell / "status.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "success" or manifest.get("accepted") is not True:
        failures.append("manifest 未通过")
    if status.get("status") != "success" or status.get("accepted") is not True:
        failures.append("status 未通过")
    checked = 0
    for line in (cell / "checksums.sha256").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split(maxsplit=1)
        target = (cell / relative.strip()).resolve()
        try:
            target.relative_to(cell)
        except ValueError:
            failures.append(f"路径越界: {relative}")
            continue
        if not target.is_file():
            failures.append(f"文件缺失: {relative}")
        elif sha256(target) != expected:
            failures.append(f"哈希不匹配: {relative}")
        checked += 1
    return {
        "status": "pass" if not failures else "fail",
        "checked_files": checked,
        "manifest_sha256": sha256(cell / "manifest.json"),
        "checksums_sha256": sha256(cell / "checksums.sha256"),
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--cv-dir", required=True)
    parser.add_argument("--maxdim-dir")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--fetch-receipt")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    run = Path(args.run_dir).resolve()
    cv_dir = Path(args.cv_dir).resolve()
    output = Path(args.output_dir).resolve()
    analyzer_output = output / "production_crosscheck"
    command = [
        sys.executable,
        "-X",
        "utf8",
        str(ANALYZER),
        "--coarse-dir",
        str(run / COARSE),
        "--refined-dir",
        str(run / REFINED),
        "--cv-dir",
        str(cv_dir),
        "--output-dir",
        str(analyzer_output),
        "--short-tmax",
        "25",
    ]
    if args.maxdim_dir:
        command.extend(["--maxdim-dir", str(Path(args.maxdim_dir).resolve())])
    if args.dry_run:
        print(
            json.dumps(
                {
                    "run_dir": str(run),
                    "run_exists": run.is_dir(),
                    "cv_dir": str(cv_dir),
                    "cv_exists": cv_dir.is_dir(),
                    "maxdim_dir": str(Path(args.maxdim_dir).resolve()) if args.maxdim_dir else None,
                    "maxdim_exists": Path(args.maxdim_dir).resolve().is_dir()
                    if args.maxdim_dir
                    else False,
                    "output_dir": str(output),
                    "output_exists": output.exists(),
                    "command": command,
                },
                ensure_ascii=False,
            )
        )
        return
    if not run.is_dir() or not cv_dir.is_dir():
        raise SystemExit("缺少已回传 run 或 CV anchor 集")
    if args.maxdim_dir and not Path(args.maxdim_dir).resolve().is_dir():
        raise SystemExit("指定的第二档 maxdim 结果不存在")
    if output.exists() and any(output.iterdir()):
        raise SystemExit(f"拒绝覆盖已有分析: {output}")
    output.mkdir(parents=True, exist_ok=True)

    cells = {name: verify_cell(run / name) for name in (COARSE, REFINED)}
    if not all(cell["status"] == "pass" for cell in cells.values()):
        raise SystemExit(f"独立本地 checksum 未通过: {cells}")
    receipt_check: dict[str, object] | None = None
    if args.fetch_receipt:
        receipt_path = Path(args.fetch_receipt).resolve()
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt_check = {
            "status": "pass"
            if all(
                cells[name]["manifest_sha256"] == receipt["cells"][name]["manifest_sha256"]
                and cells[name]["checksums_sha256"]
                == receipt["cells"][name]["checksums_sha256"]
                for name in cells
            )
            else "fail",
            "receipt_sha256": sha256(receipt_path),
        }
        if receipt_check["status"] != "pass":
            raise SystemExit("独立哈希与回传 receipt 不一致")

    result = subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    summary_path = analyzer_output / "summary.json"
    if not summary_path.is_file():
        raise SystemExit(f"分析器未生成 summary: {result.stderr.strip()}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if result.returncode not in (0, 2) or summary.get("status") == "fail":
        raise SystemExit(f"严格 q=pi 分析失败: {summary}")
    audit = {
        "schema_version": 1,
        "status": "pass" if summary.get("tebd_qpi_tag") == "Agreement" else "fail",
        "local_checksum": cells,
        "fetch_receipt_check": receipt_check,
        "analysis_status": summary.get("status"),
        "qpi_production_status": summary.get("qpi_production_status"),
        "full_dynamic_status": summary.get("full_dynamic_status"),
        "tebd_qpi_tag": summary.get("tebd_qpi_tag"),
        "cross_method_tag": summary.get("cross_method_tag"),
        "analysis_summary_sha256": sha256(summary_path),
        "negative_alpha_excluded": True,
        "figure_9_excluded": True,
    }
    (output / "local_handoff_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(audit, ensure_ascii=False))
    if audit["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
