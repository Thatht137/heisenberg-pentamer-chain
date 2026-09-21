#!/usr/bin/env bash
set -euo pipefail

# 低频独立复核，拒绝覆盖历史结果。
root=/home/wangjieren/code/1x5_Heisenberg_Pentamer
run_root="$root/results/autoresearch_v5_20260804/round41_qpi_cv_low005_smoke"
run_dir="$run_root/cell-l40-qpi-low-005-highbudget"
launcher_log="$run_root/launcher_cell-l40-qpi-low-005-highbudget_attempt2.log"
launcher_pid="$run_root/launcher_cell-l40-qpi-low-005-highbudget_attempt2.pid"
verification="$run_root/launch_verification_attempt2.txt"
submission="$run_root/submission_cell-l40-qpi-low-005-highbudget_attempt2.json"
failed_submission="$run_root/submission_cell-l40-qpi-low-005-highbudget_attempt1.json"

cd "$root"
mkdir -p "$run_root"
if [[ -e "$run_dir" ]]; then
  mapfile -t leftovers < <(find "$run_dir" -mindepth 1 -maxdepth 1 -printf '%f\n')
  if [[ "${#leftovers[@]}" -eq 1 && "${leftovers[0]}" == "submission.json" && ! -e "$failed_submission" ]]; then
    mv "$run_dir/submission.json" "$failed_submission"
    rmdir "$run_dir"
  else
    echo "拒绝覆盖已有 cell: $run_dir" >&2
    exit 10
  fi
fi
if [[ -e "$launcher_log" || -e "$launcher_pid" || -e "$verification" ]]; then
  echo "拒绝覆盖已有 round41 launcher 文件" >&2
  exit 11
fi

manifest_hash=$(sha256sum Manifest.toml | awk '{print $1}')
runner_hash=$(sha256sum scripts/autoresearch_v5/run_cv_dsf_cell.py | awk '{print $1}')
julia_hash=$(sha256sum scripts/autoresearch_v5/cv_dsf_cell.jl | awk '{print $1}')
progress_hash=$(sha256sum scripts/autoresearch_v5/progress.py | awk '{print $1}')
[[ "$manifest_hash" == "37a53ffd73db57b9db9c4ce11f6265a9a41ac2035dc421b01f9a633d893ba12c" ]]
[[ "$runner_hash" == "560d4344bc71c4dad487a3028a030bc41ebf813d53427bdcc17ace9eec0cc349" ]]
[[ "$julia_hash" == "049908c694ed6841bd0c3b3028b3b966cedafd426c49f07e1f491393d59e5292" ]]
[[ "$progress_hash" == "807cf897627bec8ce016f7cfe304d70324addc25f2effa2219faf286551e774e" ]]
[[ "$(/home/wangjieren/.juliaup/bin/julia +release --startup-file=no --version)" == "julia version 1.12.3" ]]

mapfile -t julia_pids < <(pgrep -x julia || true)
[[ "${#julia_pids[@]}" -eq 1 ]]
existing_julia="${julia_pids[0]}"
existing_cmd=$(ps -o args= -p "$existing_julia")
[[ "$existing_cmd" == *"cell-l40-qpi-high-150"* ]]
avail_kib=$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)
avail_disk=$(df -Pk "$root" | awk 'NR==2 {print $4}')
[[ "$avail_kib" -ge 100000000 ]]
[[ "$avail_disk" -ge 100000000 ]]

printf '%s\n' \
  "round41 low-frequency CV smoke launcher" \
  "started_at=$(date --iso-8601=seconds)" \
  "host=$(hostname)" \
  "existing_high150_julia_pid=$existing_julia" \
  "params=alpha=.23 beta=.5 n_units=8 L=40 q_over_pi=1 eta=.1 omega=.05 dmrg_maxdim=320 cv_maxdim=800 nsweeps=20 cutoff=1e-10 cv_cutoff=1e-14 residual_gate=1e-5 threads=4" \
  "limits=OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 JULIA_NUM_THREADS=4 nice=15" \
  "outdir=$run_dir" > "$launcher_log"

python3 - "$submission" <<'PY'
import json
import sys
from datetime import datetime, timezone

payload = {
    "schema_version": 1,
    "job_type": "qpi_cv_low005_smoke",
    "cell_id": "cell-l40-qpi-low-005-highbudget",
    "scope": {
        "alpha": 0.23,
        "beta": 0.5,
        "L": 40,
        "n_units": 8,
        "q_over_pi": 1.0,
        "negative_alpha_excluded": True,
        "figure_9_excluded": True,
    },
    "parameters": {
        "eta": 0.1,
        "omega_min": 0.05,
        "omega_max": 0.05,
        "omega_step": 0.05,
        "dmrg_maxdim": 320,
        "cv_maxdim": 800,
        "nsweeps": 20,
        "cutoff": 1e-10,
        "cv_cutoff": 1e-14,
        "max_cv_residual": 1e-5,
        "threads": 4,
    },
    "resource_limits": {
        "nice": 15,
        "OPENBLAS_NUM_THREADS": 1,
        "OMP_NUM_THREADS": 1,
        "MKL_NUM_THREADS": 1,
        "JULIA_NUM_THREADS": 4,
        "no_dependency_download": True,
        "existing_high150_preserved": True,
    },
    "started_at": datetime.now(timezone.utc).isoformat(),
    "acceptance_order": [
        "natural termination",
        "remote checksums",
        "non-overwriting download",
        "validate_cv_run.py",
        "accepted-only assembly",
        "CV-TEBD reanalysis",
    ],
}
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(payload, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
PY

# 外层 nice=15，子进程保留离线和线程限制。
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
  nice -n 15 python3 scripts/autoresearch_v5/run_cv_dsf_cell.py \
  --cell-id cell-l40-qpi-low-005-highbudget \
  --outdir "$run_dir" \
  --alpha 0.23 \
  --beta 0.5 \
  --n-units 8 \
  --q-over-pi 1.0 \
  --eta 0.1 \
  --omega-min 0.05 \
  --omega-max 0.05 \
  --omega-step 0.05 \
  --dmrg-maxdim 320 \
  --cv-maxdim 800 \
  --nsweeps 20 \
  --cutoff 1e-10 \
  --cv-cutoff 1e-14 \
  --max-cv-residual 1e-5 \
  --threads 4 \
  >> "$launcher_log" 2>&1 < /dev/null &
launcher=$!
printf '%s\n' "$launcher" > "$launcher_pid"
printf '%s\n' "launcher_pid=$launcher" "verify_at=$(date --iso-8601=seconds)" >> "$launcher_log"

sleep 3
new_runner=$(pgrep -af 'python3 scripts/autoresearch_v5/run_cv_dsf_cell.py --cell-id cell-l40-qpi-low-005-highbudget' || true)
new_julia=$(pgrep -af 'cv_dsf_cell.jl.*0.05 0.05' || true)
high150=$(pgrep -af 'cell-l40-qpi-high-150' || true)
printf '%s\n' \
  "new_runner=$new_runner" \
  "new_julia=$new_julia" \
  "high150=$high150" \
  "status_exists=$(test -f "$run_dir/status.json" && echo yes || echo no)" \
  "progress_exists=$(test -f "$run_dir/progress.json" && echo yes || echo no)" \
  "target=$run_dir" > "$verification"
cat "$verification"
