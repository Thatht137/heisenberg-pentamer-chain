#!/usr/bin/env python3
"""按冻结误差预算比较同一点的 Python ED 与服务器 DMRG。"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ed", required=True)
    parser.add_argument("--dmrg", required=True)
    parser.add_argument("--outdir", required=True)
    args = parser.parse_args()

    ed = load_json(Path(args.ed))
    dmrg = load_json(Path(args.dmrg))
    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    csv_path = outdir / "cross-method-check.csv"
    json_path = outdir / "cross-method-check.json"
    if csv_path.exists() or json_path.exists():
        raise SystemExit("拒绝覆盖已有交叉验证结果")

    params = dmrg["params"]
    settings = dmrg["settings"]
    checks = {
        "alpha_equal": math.isclose(float(ed["alpha"]), float(params["alpha"]), abs_tol=0.0),
        "beta_equal": math.isclose(float(ed["beta"]), float(params["beta"]), abs_tol=0.0),
        "L_equal": int(ed["L"]) == int(params["L"]),
        "boundary_equal": ed["boundary"] == settings["boundary"] == "OBC",
        "dmrg_sector": settings["sector"] == "Sz=0",
        "ed_sector": abs(float(ed["total_sz"])) <= 1e-12,
        "normalization": ed["method"] == "dense_ed_python",
        "negative_alpha_excluded": bool(ed["negative_alpha_excluded"])
        and bool(dmrg["provenance"]["negative_alpha_excluded"]),
    }
    if not all(checks.values()):
        raise SystemExit(f"方法设置不一致: {checks}")

    ed_energy = float(ed["energy"])
    dmrg_energy = float(dmrg["observables"]["energy"])
    total_variance = max(float(dmrg["observables"]["variance_per_site"]) * int(params["L"]), 0.0)
    ed_budget = 1e-12
    dmrg_budget = max(1e-8, math.sqrt(total_variance))
    difference = abs(ed_energy - dmrg_energy)
    tag = "Agreement" if difference <= ed_budget + dmrg_budget else "Disagreement"

    rows = [
        {
            "method": "Python dense ED",
            "observable": "ground_state_energy",
            "value": ed_energy,
            "uncertainty": ed_budget,
            "instance": "alpha=0.23,beta=0.5,L=10,OBC,Sz=0",
            "tag": tag,
        },
        {
            "method": "ITensor finite DMRG",
            "observable": "ground_state_energy",
            "value": dmrg_energy,
            "uncertainty": dmrg_budget,
            "instance": "alpha=0.23,beta=0.5,L=10,OBC,Sz=0",
            "tag": tag,
        },
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    payload = {
        "tag": tag,
        "checks": checks,
        "energy_difference": difference,
        "ed_budget": ed_budget,
        "dmrg_budget": dmrg_budget,
        "dmrg_total_variance": total_variance,
        "dmrg_diagnostics": dmrg["diagnostics"],
        "candidate_failure_modes": []
        if tag == "Agreement"
        else [
            "Hamiltonian 符号或键表不一致",
            "总 Sz 扇区或边界条件不一致",
            "DMRG 键维、sweep 或截断精度不足",
            "能量归一化不一致",
        ],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
