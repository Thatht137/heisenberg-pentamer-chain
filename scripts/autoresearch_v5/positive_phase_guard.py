#!/usr/bin/env python3
"""判定正区粗扫是无 crossing、存在 bracket 还是数据不足。"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def sign(delta: float, error: float, sigma: float) -> int:
    if delta > sigma * error:
        return 1
    if delta < -sigma * error:
        return -1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = load(args.policy)
    observations = load(args.observations)
    sigma = float(policy["criteria"]["sigma"])
    control_name = policy["axes"]["control"]["name"]
    size_name = policy["axes"]["size"]["name"]
    edge_controls = {
        float(value)
        for value in policy["axes"]["control"].get("edge_controls", [])
    }
    slice_axis = policy["axes"].get("slice")
    slice_name = slice_axis["name"] if slice_axis else None
    sizes = list(policy["axes"]["size"]["values"])
    records = observations.get("records", [])
    index = {
        (
            record["params"].get(slice_name) if slice_name else None,
            record["params"][control_name],
            record["params"][size_name],
        ): record
        for record in records
        if record.get("status") == "success"
    }
    slices = slice_axis["values"] if slice_axis else [None]
    reports = []
    for slice_value in slices:
        available = sorted({key[2] for key in index if key[0] == slice_value})
        if len(available) < 2:
            reports.append({"slice": slice_value, "status": "INCOMPLETE", "reason": "少于两个尺寸"})
            continue
        pair = (available[-2], available[-1])
        points = sorted({key[1] for key in index if key[0] == slice_value and key[2] in pair})
        entries = []
        for point in points:
            low = index.get((slice_value, point, pair[0]))
            high = index.get((slice_value, point, pair[1]))
            if not low or not high:
                continue
            delta = float(high["value"]) - float(low["value"])
            error = math.hypot(float(low["error"]), float(high["error"]))
            entries.append({"control": point, "delta": delta, "error": error, "sign": sign(delta, error, sigma)})
        interior_entries = [
            item for item in entries if float(item["control"]) not in edge_controls
        ]
        edge_entries = [
            item for item in entries if float(item["control"]) in edge_controls
        ]
        signed = [item for item in interior_entries if item["sign"]]
        brackets = [
            [left["control"], right["control"]]
            for left, right in zip(signed, signed[1:])
            if left["sign"] * right["sign"] == -1
        ]
        if brackets:
            status = "BRACKET_FOUND"
            reason = "相邻控制点出现显著符号变化"
        elif len(interior_entries) < 2:
            status = "INCOMPLETE"
            reason = "有效内部控制点不足两个"
        elif any(item["sign"] == 0 for item in interior_entries):
            status = "INCONCLUSIVE"
            reason = "至少一个内部尺寸差在 sigma 门槛内"
        else:
            status = "NO_SIGNIFICANT_CROSSING"
            reason = "所有内部尺寸差同号，固定正区内部未见显著 crossing"
        reports.append({
            "slice": slice_value,
            "size_pair": list(pair),
            "status": status,
            "reason": reason,
            "entries": entries,
            "interior_entries": interior_entries,
            "edge_entries": edge_entries,
            "edge_controls": sorted(edge_controls),
            "brackets": brackets,
        })

    statuses = {item["status"] for item in reports}
    if "INCOMPLETE" in statuses:
        overall = "INCOMPLETE"
    elif "INCONCLUSIVE" in statuses:
        overall = "INCONCLUSIVE"
    elif "BRACKET_FOUND" in statuses:
        overall = "BRACKET_FOUND"
    else:
        overall = "NO_SIGNIFICANT_CROSSING"
    result = {
        "schema_version": 1,
        "status": overall,
        "sigma": sigma,
        "control": control_name,
        "size": size_name,
        "slices": reports,
        "interpretation": {
            "NO_SIGNIFICANT_CROSSING": "可报告固定正区内部未发现可验收有限尺寸 crossing；域边界点单独记录，不赋予新相名。",
            "INCONCLUSIVE": "增加声明预算或尺寸后再判断，不得报告相界。",
            "BRACKET_FOUND": "仅报告有限尺寸 bracket，继续用 phase-diagram controller 晋级和细化。",
            "INCOMPLETE": "缺少成功 manifest，不能作物理判断。",
        }[overall],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": overall, "slices": len(reports)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
