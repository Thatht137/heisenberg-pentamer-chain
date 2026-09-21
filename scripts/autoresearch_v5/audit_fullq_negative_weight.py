#!/usr/bin/env python3
"""审计失败全动量 run 的原始负谱权分布。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    run = Path(args.run_dir).resolve()
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    settings = manifest["settings"]
    matrix = np.loadtxt(run / "spectrum_raw.csv", delimiter=",")
    q = np.linspace(0.0, 2.0 * np.pi, matrix.shape[0])
    omega = np.linspace(0.0, float(settings["omega_max"]), matrix.shape[1])
    negative = np.abs(np.minimum(matrix, 0.0))
    positive = np.maximum(matrix, 0.0)
    total = float((negative + positive).sum())
    q_negative = negative.sum(axis=1)
    q_positive = positive.sum(axis=1)
    omega_negative = negative.sum(axis=0)
    omega_positive = positive.sum(axis=0)

    def top(values: np.ndarray, other: np.ndarray, count: int = 10) -> list[dict[str, float]]:
        rows = []
        for index in np.argsort(values)[-count:][::-1]:
            denominator = max(float(values[index] + other[index]), 1e-30)
            rows.append({
                "index": int(index),
                "negative_abs": float(values[index]),
                "fraction": float(values[index] / denominator),
            })
        return rows

    q_rows = top(q_negative, q_positive)
    for row in q_rows:
        index = row["index"]
        row["q"] = float(q[index])
        row["q_over_pi"] = float(q[index] / np.pi)
    omega_rows = top(omega_negative, omega_positive)
    for row in omega_rows:
        row["omega"] = float(omega[row["index"]])

    flat = np.argsort(negative.ravel())[-20:][::-1]
    cells = []
    for item in flat:
        iq, iw = np.unravel_index(item, negative.shape)
        cells.append({
            "q_index": int(iq),
            "q": float(q[iq]),
            "q_over_pi": float(q[iq] / np.pi),
            "omega_index": int(iw),
            "omega": float(omega[iw]),
            "value": float(matrix[iq, iw]),
        })

    result = {
        "schema_version": 1,
        "status": "diagnostic_only",
        "run_dir": str(run),
        "scope": "0<=alpha,beta<=1；负 alpha 与 Fig.9 排除",
        "shape": [int(value) for value in matrix.shape],
        "global": {
            "negative_abs": float(negative.sum()),
            "positive_sum": float(positive.sum()),
            "fraction": float(negative.sum() / max(total, 1e-30)),
            "minimum": float(matrix.min()),
            "maximum": float(matrix.max()),
        },
        "q_top_negative_mass": q_rows,
        "omega_top_negative_mass": omega_rows,
        "top_negative_cells": cells,
        "interpretation": "描述性失败诊断；不构成 accepted physics evidence，不改变 0.15 验收门。",
    }
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "pass", "output": str(output), "fraction": result["global"]["fraction"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
