#!/usr/bin/env python3
"""比较 L=10 center/domain 静态 oracle。"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from analyze_positive_static_multistart import compare_cell_dirs


ROOT = Path(__file__).resolve().parents[2]
CENTER = ROOT / "results" / "autoresearch_v5_20260730" / "round8_positive_static_production" / "local_oracle_L10_tight"
RUN = ROOT / "results" / "autoresearch_v5_20260731" / "round10_positive_static_multistart_production"
DOMAIN = RUN / "local_oracle_L10_domain_tight"
OUTDIR = RUN / "local_oracle_multistart_crosscheck"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    settings = json.loads((RUN / "settings.json").read_text(encoding="utf-8"))
    budgets = {
        key: float(value)
        for key, value in settings["initialization_validation"].items()
    }
    comparison = compare_cell_dirs(CENTER, DOMAIN, budgets)
    rows = []
    for name, value in comparison["metrics"].items():
        rows.append({
            "diagnostic": name,
            "value": value,
            "budget": budgets[f"{name}_max"],
            "accepted": comparison["checks"][name],
        })
    with (OUTDIR / "multistart-check.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("diagnostic", "value", "budget", "accepted"))
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "tag": "Agreement" if comparison["accepted"] else "Disagreement",
        "configuration": {"L": 10, "alpha": 0.1, "beta": 0.5, "boundary": "OBC"},
        "methods": {"primary": "DMRG center product state", "secondary": "DMRG domain product state"},
        "budgets": budgets,
        **comparison,
        "source_sha256": {
            str((CENTER / "manifest.json").relative_to(ROOT)): sha256(CENTER / "manifest.json"),
            str((DOMAIN / "manifest.json").relative_to(ROOT)): sha256(DOMAIN / "manifest.json"),
        },
        "boundary": "初态一致性只验证实现不依赖这两个产品态；生产尺寸仍须逐点复核。",
    }
    summary_path = OUTDIR / "multistart-check.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files = sorted(path for path in OUTDIR.iterdir() if path.is_file() and path.name != "checksums.sha256")
    (OUTDIR / "checksums.sha256").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in files), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))
    if not comparison["accepted"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
