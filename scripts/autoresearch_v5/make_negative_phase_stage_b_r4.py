#!/usr/bin/env python3
"""生成 Stage B R4：失败点升至64并续跑剩余94点。"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN_REL = "results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha"
RUN = ROOT / RUN_REL
PHASE = RUN / "phase-diagram-v2"
PREV = RUN / "stage-b-negative-coarse-r3-remaining95"
STAGE_REL = f"{RUN_REL}/stage-b-negative-coarse-r4-remaining94"
STAGE = ROOT / STAGE_REL
LAUNCHER = "scripts/autoresearch_v5/launch_negative_phase_stage_b_r4_remaining94.sh"
SOURCES = ["Project.toml", "Manifest.toml", "docs/full_phase_diagram_negative_standard_20260809.md",
    "src/PentamerChain.jl", "src/hamiltonian.jl", "src/order_parameters.jl",
    "scripts/autoresearch_v5/progress.py", "scripts/autoresearch_v5/negative_static_cell.jl",
    "scripts/autoresearch_v5/run_negative_static_cell.py", "scripts/autoresearch_v5/run_negative_phase_structure_cell.py",
    "scripts/autoresearch_v5/run_negative_phase_structure_batch.py", "scripts/autoresearch_v5/validate_negative_phase_run.py", LAUNCHER]

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
    outputs = [STAGE / name for name in ("parameter-scan.run_spec.json", "stage_b_r4_source_hashes.sha256", "launch-contract.json", "stage-b-action-plan.json", "server_upload_manifest.json")]
    if any(path.exists() for path in outputs): raise FileExistsError("Stage B R4 文件已存在")
    prev_spec_path, prev_plan_path = PREV / "parameter-scan.run_spec.json", PREV / "stage-b-action-plan.json"
    summary_path = PHASE / "stage_b_r3_terminal_summary.json"
    prev_spec, prev_plan, summary = map(load, (prev_spec_path, prev_plan_path, summary_path))
    if summary.get("counts") != {"success": 1, "failed": 1, "pending": 93} or summary.get("failed_cells") != ["negb3-a0750-b0050-L040"]:
        raise ValueError("R3终态基线不匹配")
    passed, failed = set(summary["pass_cells"]), set(summary["failed_cells"])
    action_map = {row["action_id"]: row for row in prev_plan["actions"]}
    cells, actions = [], []
    for original in prev_spec["cells"]:
        if original["cell_id"] in passed: continue
        cell = json.loads(json.dumps(original)); old_id = cell["cell_id"]
        cell["cell_id"] = old_id.replace("negb3-", "negb4-"); cell["stage"] = "B-R4-coarse-remaining94"; cell["r3_cell_id"] = old_id
        if old_id in failed:
            if cell["budget"] != 32: raise ValueError("R4失败点不是32 sweeps")
            cell["budget"] = 64; cell["budget_rationale"] = "R3双初态Sz0方差超门；按32→64重试"
        cells.append(cell)
        action = json.loads(json.dumps(action_map[cell["controller_action_id"]]))
        action.update({"lifecycle_state":"PLANNED","observation_status":"pending","accepted":False,"budget":cell["budget"],"artifact":f"{STAGE_REL}/cells/{cell['cell_id']}/manifest.json"})
        actions.append(action)
    if len(cells) != 94 or cells[0]["budget"] != 64: raise ValueError("R4 cells异常")
    code_hashes = {name: sha256(ROOT / name) for name in SOURCES}
    spec = json.loads(json.dumps(prev_spec)); spec.update({"run_id":"pentamer-negative-phase-stage-b-r4-remaining94-20260812","scope":"Stage B R4 remaining94; failed L40 promoted 32 to 64","cells":cells})
    spec["provenance"].update({"stage_b_r3_terminal_summary_sha256":sha256(summary_path),"stage_b_r3_run_spec_sha256":sha256(prev_spec_path),"prior_accepted_cells":["negb2-a1000-b0050-L040","negb3-a1000-b0050-L060"],"retry_policy":"failed L40 32->64; remaining cells retain budgets","code_sha256":code_hashes,"boundary_thresholds_relaxed":False})
    plan = {"schema_version":1,"stage":"B-R4-coarse-remaining94","canonical_action_index_mutated":False,"actions":actions}
    STAGE.mkdir(parents=True, exist_ok=True); spec_path=STAGE/"parameter-scan.run_spec.json"; plan_path=STAGE/"stage-b-action-plan.json"; hashes_path=STAGE/"stage_b_r4_source_hashes.sha256"
    write_json(spec_path,spec); write_json(plan_path,plan)
    with hashes_path.open("w",encoding="utf-8",newline="\n") as stream: stream.write("".join(f"{d}  {n}\n" for n,d in code_hashes.items()))
    counts={"32":sum(c["budget"]==32 for c in cells),"64":sum(c["budget"]==64 for c in cells)}
    contract={"schema_version":1,"launch_ready":True,"stage_a_complete":True,"r3_failure_validated":True,"cell_count":94,"concurrency":1,"stop_on_first_failure":True,"offline":True,"eta_hours":{"low":18,"high":32},"budget_counts":counts,"run_spec_sha256":sha256(spec_path),"source_hashes_sha256":sha256(hashes_path),"action_plan_sha256":sha256(plan_path),"r3_terminal_summary_sha256":sha256(summary_path),"boundary_thresholds_relaxed":False}
    contract_path=STAGE/"launch-contract.json"; write_json(contract_path,contract)
    files=SOURCES+[f"{STAGE_REL}/parameter-scan.run_spec.json",f"{STAGE_REL}/stage_b_r4_source_hashes.sha256",f"{STAGE_REL}/stage-b-action-plan.json",f"{STAGE_REL}/launch-contract.json"]
    write_json(STAGE/"server_upload_manifest.json",{"schema_version":1,"target":"/home/wangjieren/code/1x5_Heisenberg_Pentamer","mode":"offline_upload_only","launch_ready":True,"r3_failure_validated":True,"stage":"B-R4-coarse-remaining94","cell_count":94,"concurrency":1,"stop_on_first_failure":True,"eta_hours":{"low":18,"high":32},"remote_git_pull":False,"files":[{"path":n,"sha256":sha256(ROOT/n),"bytes":(ROOT/n).stat().st_size} for n in files]})
    print(json.dumps({"status":"pass","cells":94,"budget_counts":counts,"eta_hours":[18,32]},ensure_ascii=False)); return 0

if __name__ == "__main__": raise SystemExit(main())
