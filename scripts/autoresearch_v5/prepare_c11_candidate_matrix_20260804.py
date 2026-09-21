"""从已验收正区 manifest 提取 C11 的最小候选验证矩阵。"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CELLS = ROOT / "results/autoresearch_v5_20260802/round19_phase_diagram_positive_mesh/cells"
OUT = ROOT / "results/research_progress/c11_candidate_matrix_20260804.json"
REPORT = ROOT / "results/research_progress/report.json"
TITLE = "2026-08-04 C11 正区候选验证矩阵（离线提取）"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    groups: dict[tuple[float, float], list[dict[str, object]]] = defaultdict(list)
    for manifest_path in sorted(CELLS.glob("*/manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        params = manifest.get("params", {})
        alpha = float(params.get("alpha", -1.0))
        if alpha <= 0.0 or not manifest.get("accepted", False):
            continue
        beta = float(params["beta"])
        size = int(params["L"])
        observable = manifest["observables"]["structure_factor_ratio"]
        groups[(alpha, beta)].append(
            {
                "alpha": alpha,
                "beta": beta,
                "L": size,
                "value": float(observable["value"]),
                "error": float(observable["error"]),
                "manifest": manifest_path.relative_to(ROOT).as_posix(),
                "sha256": sha256(manifest_path),
            }
        )

    summaries = []
    for (alpha, beta), rows in groups.items():
        by_size = {int(row["L"]): row for row in rows}
        if not all(size in by_size for size in (40, 60, 80)):
            continue
        delta_60_80 = float(by_size[80]["value"]) - float(by_size[60]["value"])
        summaries.append(
            {
                "alpha": alpha,
                "beta": beta,
                "max_error": max(float(row["error"]) for row in rows),
                "delta_60_80": delta_60_80,
                "records": sorted(rows, key=lambda row: int(row["L"])),
            }
        )
    summaries.sort(key=lambda row: (-float(row["max_error"]), -abs(float(row["delta_60_80"])), float(row["alpha"]), float(row["beta"])))

    selected_keys: list[tuple[float, float]] = []
    def add_key(alpha: float, beta: float) -> None:
        key = (alpha, beta)
        if key in groups and key not in selected_keys and all(any(int(row["L"]) == size for row in groups[key]) for size in (40, 60, 80)):
            selected_keys.append(key)

    if summaries:
        add_key(float(summaries[0]["alpha"]), float(summaries[0]["beta"]))
    for summary in sorted(summaries, key=lambda row: (-abs(float(row["delta_60_80"])), -float(row["max_error"]))):
        if len(selected_keys) >= 2:
            break
        add_key(float(summary["alpha"]), float(summary["beta"]))
    alphas = sorted({key[0] for key in groups})
    betas = sorted({key[1] for key in groups})
    for alpha, beta in ((alphas[0], betas[0]), (alphas[0], betas[-1]), (alphas[-1], betas[0]), (alphas[-1], betas[-1])):
        add_key(alpha, beta)

    selected = [next(summary for summary in summaries if (summary["alpha"], summary["beta"]) == key) for key in selected_keys]
    result = {
        "schema_version": 1,
        "created_at": "2026-08-04T09:40:00+08:00",
        "status": "plan_only",
        "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True, "alpha_zero_excluded": True},
        "source": {"cells_dir": CELLS.relative_to(ROOT).as_posix(), "accepted_control_count": len(summaries), "accepted_record_count": sum(len(summary["records"]) for summary in summaries)},
        "selected_controls": selected,
        "selection_rule": "优先最大独立初态误差，其次最大 60→80 尺寸变化，再覆盖正区网格四角；每个控制点要求 L=40/60/80 三个 manifest。",
        "next_compute": "仅在服务器当前 Julia 任务完成且 phase policy 获准后，对 selected_controls 做多观测量收敛矩阵；不重扫旧 2400 点。",
        "acceptance": ["每点 L=40/60/80 均通过方差、截断和独立初态门", "不以 crossing 单独命名相", "若无显著 crossing，C11 仍只写成‘当前有限尺寸数据未见可验收内部 crossing’"],
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "从本地已验收 manifest 离线提取；不连接服务器、不启动计算、不修改 phase bounds。",
        "blocks": [
            {"kind": "verdict", "status": "neutral", "label": "候选矩阵已准备", "why": f"已从 {len(summaries)} 个三尺寸正区控制点中筛出 {len(selected)} 个优先验证点。"},
            {"kind": "table", "columns": ["alpha", "beta", "最大误差", "R(80)-R(60)", "用途"], "rows": [[f"{row['alpha']:.3g}", f"{row['beta']:.3g}", f"{row['max_error']:.3g}", f"{row['delta_60_80']:.3g}", "强耦合/误差优先验证"] for row in selected]},
            {"kind": "list", "title": "执行边界", "items": ["不重扫旧 2400 点，只补候选点的收敛矩阵。", "alpha=0 边界不纳入本矩阵；负 alpha 和 Fig.9 永久排除。", "相图完成仍需最终相邻尺寸对和显著性 guard，不从颜色图直接命名相。"]},
        ],
    }
    report["sections"] = [item for item in report["sections"] if item.get("title") != TITLE]
    report["sections"].insert(3, section)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "accepted_controls": len(summaries), "selected": len(selected)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
