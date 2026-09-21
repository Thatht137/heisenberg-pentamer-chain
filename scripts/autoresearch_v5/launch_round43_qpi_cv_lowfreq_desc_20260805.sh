#!/usr/bin/env bash
set -euo pipefail

# 第一阶段按高频到低频推进到 omega=0.05。
root=/home/wangjieren/code/1x5_Heisenberg_Pentamer
run_root="$root/results/autoresearch_v5_20260805/round43_qpi_cv_lowfreq_desc_20260805"
run_dir="$run_root/cell-l40-qpi-lowfreq-desc"
launcher_log="$run_root/launcher_phase1.log"
launcher_pid="$run_root/launcher_phase1.pid"
verification="$run_root/launch_verification_phase1.txt"
submission="$run_root/submission_phase1.json"

cd "$root"
mkdir -p "$run_root"
if [[ -e "$run_dir" && -n "$(find "$run_dir" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]]; then
  echo "拒绝覆盖已有 cell: $run_dir" >&2
  exit 10
fi
for path in "$launcher_log" "$launcher_pid" "$verification" "$submission"; do
  [[ ! -e "$path" ]] || { echo "拒绝覆盖 launcher 文件: $path" >&2; exit 11; }
done

[[ "$(sha256sum Manifest.toml | awk '{print $1}')" == "37a53ffd73db57b9db9c4ce11f6265a9a41ac2035dc421b01f9a633d893ba12c" ]]
[[ "$(sha256sum scripts/autoresearch_v5/cv_dsf_resumable.jl | awk '{print $1}')" == "ce3fddb48ad141387d0276c73b982e0fb229b037123ff13e10bc3da75e828d61" ]]
[[ "$(sha256sum scripts/autoresearch_v5/run_cv_dsf_resumable.py | awk '{print $1}')" == "8156b934b63890ff4e655c933c9c8a397921fa62811cb4dad10a7e7c3bc323cb" ]]
[[ "$(sha256sum scripts/autoresearch_v5/progress.py | awk '{print $1}')" == "807cf897627bec8ce016f7cfe304d70324addc25f2effa2219faf286551e774e" ]]
[[ "$(/home/wangjieren/.juliaup/bin/julia +release --startup-file=no --version)" == "julia version 1.12.3" ]]

existing_julia=$(pgrep -x julia || true)
[[ -z "$existing_julia" ]] || { echo "检测到已有 Julia，停止: $existing_julia" >&2; exit 20; }
existing_runner=$(ps -eo pid=,args= | awk '/run_cv_dsf_(cell|resumable).py/ && !/awk/ {print}')
[[ -z "$existing_runner" ]] || { echo "检测到已有 CV runner，停止: $existing_runner" >&2; exit 21; }
avail_kib=$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)
avail_disk=$(df -Pk "$root" | awk 'NR==2 {print $4}')
[[ "$avail_kib" -ge 100000000 ]] || { echo "可用内存不足: ${avail_kib} KiB" >&2; exit 22; }
[[ "$avail_disk" -ge 100000000 ]] || { echo "可用磁盘不足: ${avail_disk} KiB" >&2; exit 23; }

python3 - "$submission" <<'PY'
import json
import sys
from datetime import datetime, timezone

started = datetime.now(timezone.utc)
payload = {
    "schema_version": 1,
    "job_type": "qpi_cv_lowfreq_descending_phase1",
    "cell_id": "cell-l40-qpi-lowfreq-desc",
    "scope": {
        "alpha": 0.23,
        "beta": 0.5,
        "L": 40,
        "q_over_pi": 1.0,
        "negative_alpha_excluded": True,
        "figure_9_excluded": True,
    },
    "parameters": {
        "eta": 0.1,
        "omega_grid": [0.0, 0.05, 0.10, 0.15, 0.20],
        "solve_order": [0.20, 0.15, 0.10, 0.05],
        "dmrg_maxdim": 320,
        "cv_maxdim": 1200,
        "nsweeps": 24,
        "dmrg_cutoff": 1e-10,
        "cv_cutoff": 1e-16,
        "max_cv_residual": 1e-5,
        "threads": 4,
    },
    "resources": {
        "single_julia": True,
        "nice": 15,
        "blas_threads": 1,
        "julia_threads": 4,
        "expected_eta": "4-8 h",
        "read_once_after": "6 h",
        "no_dependency_download": True,
    },
    "acceptance": [
        "natural partial termination at 4/5 points",
        "remote checksums",
        "all four phase-1 relative residuals <= 1e-5",
        "only then resume omega=0.00",
    ],
    "started_at": started.isoformat(),
}
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(payload, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
PY

printf '%s\n' \
  "round43 q=pi CV low-frequency descending phase1" \
  "started_at=$(date --iso-8601=seconds)" \
  "params=alpha=.23 beta=.5 L=40 q=pi eta=.1 order=.20,.15,.10,.05 Ddmrg=320 Dcv=1200 nsweeps=24 cv_cutoff=1e-16 residual_gate=1e-5" \
  "resources=threads=4 blas=1 nice=15 ETA=4-8h read_once_after=6h" \
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
  --max-new-points 4 \
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
  "status_exists=$(test -f "$run_dir/status.json" && echo yes || echo no)" \
  "progress_exists=$(test -f "$run_dir/progress.json" && echo yes || echo no)" \
  "target=$run_dir" > "$verification"
cat "$verification"
