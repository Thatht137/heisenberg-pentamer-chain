#!/usr/bin/env bash
set -euo pipefail

# 第二阶段仅在第一阶段四点全部通过后恢复 omega=0.00。
root=/home/wangjieren/code/1x5_Heisenberg_Pentamer
run_root="$root/results/autoresearch_v5_20260805/round43_qpi_cv_lowfreq_desc_20260805"
run_dir="$run_root/cell-l40-qpi-lowfreq-desc"
launcher_log="$run_root/launcher_phase2.log"
launcher_pid="$run_root/launcher_phase2.pid"
verification="$run_root/launch_verification_phase2.txt"
submission="$run_root/submission_phase2.json"

cd "$root"
for path in "$launcher_log" "$launcher_pid" "$verification" "$submission"; do
  [[ ! -e "$path" ]] || { echo "拒绝覆盖 launcher 文件: $path" >&2; exit 11; }
done
[[ -f "$run_dir/checksums.sha256" ]] || { echo "第一阶段缺少 checksum" >&2; exit 12; }

python3 - "$run_dir" "$submission" <<'PY'
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

run = Path(sys.argv[1])
status = json.loads((run / "status.json").read_text(encoding="utf-8"))
manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
if status.get("status") != "partial" or manifest.get("status") != "partial":
    raise SystemExit("第一阶段不是预期 partial 终态")
rows = []
for point in sorted((run / "points").glob("omega-*.csv")):
    with point.open(encoding="utf-8", newline="") as handle:
        rows.append(next(csv.DictReader(handle)))
omegas = [float(row["omega"]) for row in rows]
residuals = [float(row["relative_residual"]) for row in rows]
expected = [0.20, 0.15, 0.10, 0.05]
if len(rows) != 4 or any(abs(left - right) > 1e-12 for left, right in zip(omegas, expected)):
    raise SystemExit(f"第一阶段频率点不完整: {omegas}")
if max(residuals) > 1e-5:
    raise SystemExit(f"第一阶段 residual 未通过: {residuals}")
residual = residuals[-1]
payload = {
    "schema_version": 1,
    "job_type": "qpi_cv_lowfreq_descending_phase2",
    "resume_from": str(run),
    "omega": 0.0,
    "trigger_omega005_residual": residual,
    "trigger_phase1_max_residual": max(residuals),
    "expected_eta": "1-3 h",
    "read_once_after": "2 h",
    "acceptance": "terminal + checksum + validate_cv_run.py + residual <= 1e-5",
    "started_at": datetime.now(timezone.utc).isoformat(),
}
Path(sys.argv[2]).write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
PY

existing_julia=$(pgrep -x julia || true)
[[ -z "$existing_julia" ]] || { echo "检测到已有 Julia，停止: $existing_julia" >&2; exit 20; }
existing_runner=$(ps -eo pid=,args= | awk '/run_cv_dsf_(cell|resumable).py/ && !/awk/ {print}')
[[ -z "$existing_runner" ]] || { echo "检测到已有 CV runner，停止: $existing_runner" >&2; exit 21; }

printf '%s\n' \
  "round43 q=pi CV low-frequency descending phase2" \
  "started_at=$(date --iso-8601=seconds)" \
  "target=omega=.00 resume=true ETA=1-3h read_once_after=2h" \
  "outdir=$run_dir" > "$launcher_log"

nohup env \
  OPENBLAS_NUM_THREADS=1 \
  OMP_NUM_THREADS=1 \
  MKL_NUM_THREADS=1 \
  GOTO_NUM_THREADS=1 \
  VECLIB_MAXIMUM_THREADS=1 \
  JULIA_NUM_THREADS=4 \
  JULIA_PKG_OFFLINE=true \
  JULIA_PKG_SERVER= \
  HTTP_PROXY=http://127.0.0.1:9 \
  HTTPS_PROXY=http://127.0.0.1:9 \
  nice -n 15 python3 scripts/autoresearch_v5/run_cv_dsf_resumable.py \
  --cell-id cell-l40-qpi-lowfreq-desc \
  --outdir "$run_dir" \
  --alpha 0.23 \
  --beta 0.5 \
  --n-units 8 \
  --q-over-pi 1.0 \
  --eta 0.1 \
  --omega-min 0.0 \
  --omega-max 0.2 \
  --omega-step 0.05 \
  --omega-order descending \
  --dmrg-maxdim 320 \
  --cv-maxdim 1200 \
  --nsweeps 24 \
  --cutoff 1e-10 \
  --cv-cutoff 1e-16 \
  --max-cv-residual 1e-5 \
  --max-new-points 1 \
  --resume \
  --threads 4 \
  >> "$launcher_log" 2>&1 < /dev/null &
launcher=$!
printf '%s\n' "$launcher" > "$launcher_pid"

sleep 3
new_runner=$(ps -eo pid=,args= | awk '/run_cv_dsf_resumable.py --cell-id cell-l40-qpi-lowfreq-desc/ && !/awk/ {print}')
new_julia=$(ps -eo pid=,args= | awk '/cv_dsf_resumable.jl/ && !/awk/ {print}')
printf '%s\n' \
  "launcher_pid=$launcher" \
  "new_runner=$new_runner" \
  "new_julia=$new_julia" \
  "target=$run_dir" > "$verification"
cat "$verification"
