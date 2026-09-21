#!/usr/bin/env python3
"""按上一轮终态生成 Stage B 下一轮续跑包。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN_REL = "results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha"
RUN = ROOT / RUN_REL
PHASE = RUN / "phase-diagram-v2"
LAUNCHER = "scripts/autoresearch_v5/launch_negative_phase_stage_b_next.sh"
SOURCES = ["Project.toml", "Manifest.toml", "docs/full_phase_diagram_negative_standard_20260809.md",
    "src/PentamerChain.jl", "src/hamiltonian.jl", "src/order_parameters.jl",
    "scripts/autoresearch_v5/progress.py", "scripts/autoresearch_v5/negative_static_cell.jl",
    "scripts/autoresearch_v5/run_negative_static_cell.py", "scripts/autoresearch_v5/run_negative_phase_structure_cell.py",
    "scripts/autoresearch_v5/run_negative_phase_structure_batch.py", "scripts/autoresearch_v5/validate_negative_phase_run.py", LAUNCHER]

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous-stage", required=True)
    parser.add_argument("--previous-round", type=int, required=True)
    parser.add_argument("--next-round", type=int, required=True)
    return parser.parse_args()

def load(path: Path) -> dict: return json.loads(path.read_text(encoding="utf-8"))
def sha256(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n"); stream.flush(); os.fsync(stream.fileno())
        os.replace(name, path)
    except BaseException:
        Path(name).unlink(missing_ok=True); raise

def main() -> int:
    args = parse_args()
    if args.next_round != args.previous_round + 1 or args.previous_round < 1:
        raise ValueError("轮次必须连续")
    previous = RUN / args.previous_stage
    prev_spec_path, prev_plan_path = previous / "parameter-scan.run_spec.json", previous / "stage-b-action-plan.json"
    summary_path = PHASE / f"stage_b_r{args.previous_round}_terminal_summary.json"
    prev_spec, prev_plan, summary = map(load, (prev_spec_path, prev_plan_path, summary_path))
    counts = summary.get("counts", {})
    if (summary.get("status") != "partial_failure" or counts.get("failed") != 1
            or counts.get("success", 0) < 0 or counts.get("pending", 0) < 0
            or summary.get("failed_records_contain_value_or_error") is not False
            or summary.get("boundary_thresholds_relaxed") is not False):
        raise ValueError("上一轮终态不满足续跑门")
    passed, failed = set(summary["pass_cells"]), set(summary["failed_cells"])
    if len(failed) != 1:
        raise ValueError("失败点数量异常")
    remaining_count = counts["failed"] + counts["pending"]
    stage_name = f"stage-b-negative-coarse-r{args.next_round}-remaining{remaining_count}"
    stage_rel, stage = f"{RUN_REL}/{stage_name}", RUN / stage_name
    outputs = [stage / name for name in ("parameter-scan.run_spec.json", "stage_b_next_source_hashes.sha256", "launch-contract.json", "stage-b-action-plan.json", "server_upload_manifest.json")]
    if any(path.exists() for path in outputs): raise FileExistsError("下一轮文件已存在")
    action_map = {row["action_id"]: row for row in prev_plan["actions"]}
    cells, actions = [], []
    for original in prev_spec["cells"]:
        if original["cell_id"] in passed: continue
        cell = json.loads(json.dumps(original)); old_id = cell["cell_id"]
        prefix = old_id.split("-", 1)[0]
        cell["cell_id"] = old_id.replace(prefix + "-", f"negb{args.next_round}-", 1)
        cell["stage"] = f"B-R{args.next_round}-coarse-remaining{remaining_count}"
        cell[f"r{args.previous_round}_cell_id"] = old_id
        if old_id in failed:
            old_budget = int(cell["budget"])
            if old_budget >= 128: raise ValueError("失败点已到128最终预算")
            cell["budget"] = old_budget * 2
            cell["budget_rationale"] = f"R{args.previous_round}数值门失败；按{old_budget}→{cell['budget']}重试"
        cells.append(cell)
        action = json.loads(json.dumps(action_map[cell["controller_action_id"]]))
        action.update({"lifecycle_state":"PLANNED","observation_status":"pending","accepted":False,
                       "budget":cell["budget"],"artifact":f"{stage_rel}/cells/{cell['cell_id']}/manifest.json"})
        actions.append(action)
    if len(cells) != remaining_count or cells[0]["budget"] not in {64, 128}:
        raise ValueError("续跑cells或预算异常")
    code_hashes = {name: sha256(ROOT / name) for name in SOURCES}
    spec = json.loads(json.dumps(prev_spec)); spec.update({"run_id":f"pentamer-negative-phase-stage-b-r{args.next_round}-remaining{remaining_count}-20260812","scope":f"Stage B R{args.next_round} remaining{remaining_count}; first failed cell promoted","cells":cells})
    prior = list(prev_spec.get("provenance", {}).get("prior_accepted_cells", [])) + list(passed)
    spec["provenance"].update({f"stage_b_r{args.previous_round}_terminal_summary_sha256":sha256(summary_path),f"stage_b_r{args.previous_round}_run_spec_sha256":sha256(prev_spec_path),"prior_accepted_cells":prior,"retry_policy":"only failed cell budget doubled; pending cells retain budgets","code_sha256":code_hashes,"boundary_thresholds_relaxed":False})
    plan={"schema_version":1,"stage":f"B-R{args.next_round}-coarse-remaining{remaining_count}","canonical_action_index_mutated":False,"actions":actions}
    stage.mkdir(parents=True, exist_ok=True); spec_path=stage/"parameter-scan.run_spec.json"; plan_path=stage/"stage-b-action-plan.json"; hashes_path=stage/"stage_b_next_source_hashes.sha256"
    write_json(spec_path,spec); write_json(plan_path,plan)
    with hashes_path.open("w",encoding="utf-8",newline="\n") as stream: stream.write("".join(f"{d}  {n}\n" for n,d in code_hashes.items()))
    budget_counts={str(b):sum(c["budget"]==b for c in cells) for b in (32,64,128)}
    contract={"schema_version":1,"launch_ready":True,"stage_a_complete":True,"previous_failure_validated":True,"cell_count":remaining_count,"concurrency":1,"stop_on_first_failure":True,"offline":True,"eta_hours":{"low":18,"high":32},"budget_counts":budget_counts,"run_spec_sha256":sha256(spec_path),"source_hashes_sha256":sha256(hashes_path),"action_plan_sha256":sha256(plan_path),"previous_terminal_summary_sha256":sha256(summary_path),"boundary_thresholds_relaxed":False}
    contract_path=stage/"launch-contract.json"; write_json(contract_path,contract)
    files=SOURCES+[f"{stage_rel}/parameter-scan.run_spec.json",f"{stage_rel}/stage_b_next_source_hashes.sha256",f"{stage_rel}/stage-b-action-plan.json",f"{stage_rel}/launch-contract.json"]
    write_json(stage/"server_upload_manifest.json",{"schema_version":1,"target":"/home/wangjieren/code/1x5_Heisenberg_Pentamer","mode":"offline_upload_only","launch_ready":True,"previous_failure_validated":True,"stage":f"B-R{args.next_round}-coarse-remaining{remaining_count}","stage_directory":stage_name,"cell_count":remaining_count,"concurrency":1,"stop_on_first_failure":True,"eta_hours":{"low":18,"high":32},"remote_git_pull":False,"files":[{"path":n,"sha256":sha256(ROOT/n),"bytes":(ROOT/n).stat().st_size} for n in files]})
    print(json.dumps({"status":"pass","stage":stage_name,"cells":remaining_count,"budget_counts":budget_counts,"prior_accepted":len(prior)},ensure_ascii=False)); return 0

if __name__ == "__main__": raise SystemExit(main())
