#!/usr/bin/env bash
set -euo pipefail

# round41 低频修复重跑，拒绝覆盖旧目录。
root=/home/wangjieren/code/1x5_Heisenberg_Pentamer
run_root="$root/results/autoresearch_v5_20260805/round41_qpi_cv_low005_retry_20260805_2003"
run_dir="$run_root/cell-l40-qpi-retry-005"
launcher_log="$run_root/launcher.log"
launcher_pid="$run_root/launcher.pid"
verification="$run_root/launch_verification.txt"
submission="$run_root/submission.json"

cd "$root"
mkdir -p "$run_root"
if [[ -e "$run_dir" && -n "$(find "$run_dir" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]]; then
  echo "拒绝覆盖已有 cell: $run_dir" >&2
  exit 10
fi
for path in "$launcher_log" "$launcher_pid" "$verification" "$submission"; do
  if [[ -e "$path" ]]; then
    echo "拒绝覆盖已有 launcher 文件: $path" >&2
    exit 11
  fi
done

manifest_hash=$(sha256sum Manifest.toml | awk '{print $1}')
runner_hash=$(sha256sum scripts/autoresearch_v5/run_cv_dsf_cell.py | awk '{print $1}')
julia_hash=$(sha256sum scripts/autoresearch_v5/cv_dsf_cell.jl | awk '{print $1}')
resumable_hash=$(sha256sum scripts/autoresearch_v5/cv_dsf_resumable.jl | awk '{print $1}')
progress_hash=$(sha256sum scripts/autoresearch_v5/progress.py | awk '{print $1}')
[[ "$manifest_hash" == "37a53ffd73db57b9db9c4ce11f6265a9a41ac2035dc421b01f9a633d893ba12c" ]]
[[ "$runner_hash" == "560d4344bc71c4dad487a3028a030bc41ebf813d53427bdcc17ace9eec0cc349" ]]
[[ "$julia_hash" == "3db32b71cc49f7574d1088996c1fbdf968f8382b6a8d61c3474da8a5dd3af240" ]]
[[ "$resumable_hash" == "8888ece53b931935d07fd85fe82988a157f2c7a8c1343c19c808dc6921cbb321" ]]
[[ "$progress_hash" == "807cf897627bec8ce016f7cfe304d70324addc25f2effa2219faf286551e774e" ]]
[[ "$(/home/wangjieren/.juliaup/bin/julia +release --startup-file=no --version)" == "julia version 1.12.3" ]]

existing_julia=$(pgrep -x julia || true)
[[ -z "$existing_julia" ]] || { echo "检测到已有 Julia，停止: $existing_julia" >&2; exit 20; }
existing_runner=$(ps -eo pid=,args= | awk '/run_cv_dsf_cell.py/ && !/awk/ {print}')
[[ -z "$existing_runner" ]] || { echo "检测到已有 CV runner，停止: $existing_runner" >&2; exit 21; }
avail_kib=$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)
avail_disk=$(df -Pk "$root" | awk 'NR==2 {print $4}')
[[ "$avail_kib" -ge 100000000 ]] || { echo "可用内存不足: ${avail_kib} KiB" >&2; exit 22; }
[[ "$avail_disk" -ge 100000000 ]] || { echo "可用磁盘不足: ${avail_disk} KiB" >&2; exit 23; }

mkdir -p "$run_dir"
printf '%s\n' \
  "round41 q=pi CV residual retry" \
  "started_at=$(date --iso-8601=seconds)" \
  "host=$(hostname)" \
  "params=alpha=.23 beta=.5 n_units=8 L=40 q_over_pi=1 eta=.1 omega=.05 dmrg_maxdim=320 cv_maxdim=800 nsweeps=20 cutoff=1e-10 cv_cutoff=1e-14 residual_gate=1e-5 threads=4" \
  "limits=OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 JULIA_NUM_THREADS=4 nice=15" \
  "expected_eta=30-60min; no_dependency_download=true" > "$launcher_log"

python3 - "$submission" <<'PY'
import json
import sys
from datetime import datetime, timezone

payload = {
    "schema_version": 1,
    "job_type": "qpi_cv_low005_residual_retry",
    "cell_id": "cell-l40-qpi-retry-005",
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
        "expected_eta": "30-60 min",
        "no_dependency_download": True,
    },
    "started_at": datetime.now(timezone.utc).isoformat(),
    "acceptance_order": [
        "natural termination",
        "remote checksums",
        "non-overwriting download",
        "local checksums",
        "validate_cv_run.py",
        "accepted-only assembly only on pass",
        "CV-TEBD reanalysis",
        "report.html",
    ],
}
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(payload, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
PY

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
  --cell-id cell-l40-qpi-retry-005 \
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
new_runner=$(ps -eo pid=,args= | awk '/run_cv_dsf_cell.py --cell-id cell-l40-qpi-retry-005/ && !/awk/ {print}')
new_julia=$(ps -eo pid=,args= | awk '/cv_dsf_cell.jl/ && !/awk/ {print}')
status_exists=$(test -f "$run_dir/status.json" && echo yes || echo no)
progress_exists=$(test -f "$run_dir/progress.json" && echo yes || echo no)
printf '%s\n' \
  "new_runner=$new_runner" \
  "new_julia=$new_julia" \
  "status_exists=$status_exists" \
  "progress_exists=$progress_exists" \
  "target=$run_dir" > "$verification"
cat "$verification"
