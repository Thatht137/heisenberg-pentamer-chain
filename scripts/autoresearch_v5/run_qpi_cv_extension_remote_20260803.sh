#!/usr/bin/env bash
set -euo pipefail

root=/home/wangjieren/code/1x5_Heisenberg_Pentamer
run_root="$root/results/autoresearch_v5_20260803/round31_qpi_cv_extension"
launcher_dir="$run_root"
mkdir -p "$launcher_dir"

if find "$run_root" -mindepth 1 -maxdepth 1 -type d | grep -q .; then
  echo "拒绝覆盖已有 CV 扩展 cell: $run_root" >&2
  exit 1
fi
if pgrep -x julia >/dev/null; then
  echo "拒绝与已有 Julia 并行" >&2
  exit 2
fi

write_overall() {
  local phase="$1"
  local completed="$2"
  local status="$3"
  python3 - "$run_root" "$phase" "$completed" "$status" <<'PY'
import json
import pathlib
import sys
from datetime import datetime, timezone
root = pathlib.Path(sys.argv[1])
payload = {
    "schema_version": 1,
    "job_type": "qpi_cv_extension_sequential",
    "phase": sys.argv[2],
    "completed_cells": int(sys.argv[3]),
    "total_cells": 4,
    "status": sys.argv[4],
    "updated_at": datetime.now(timezone.utc).isoformat(),
    "scope": {"alpha": 0.23, "beta": 0.5, "L": 40, "q_over_pi": 1.0,
              "negative_alpha_excluded": True, "figure_9_excluded": True},
}
(root / "overall_progress.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
}

run_cell() {
  local cell_id="$1"
  local omega_min="$2"
  local omega_max="$3"
  local outdir="$run_root/$cell_id"
  if [[ -e "$outdir" ]]; then
    echo "拒绝覆盖已有 cell: $outdir" >&2
    exit 3
  fi
  python3 scripts/autoresearch_v5/run_cv_dsf_cell.py \
    --cell-id "$cell_id" \
    --outdir "$outdir" \
    --alpha 0.23 --beta 0.5 --n-units 8 --q-over-pi 1.0 --eta 0.1 \
    --omega-min "$omega_min" --omega-max "$omega_max" --omega-step 0.05 \
    --dmrg-maxdim 256 --cv-maxdim 600 --nsweeps 16 \
    --cutoff 1e-10 --cv-cutoff 1e-14 --max-cv-residual 1e-5 --threads 8
}

write_overall "starting" 0 "running"
run_cell cell-l40-qpi-low-000-020 0.00 0.20
write_overall "low_frequency_done" 1 "running"
run_cell cell-l40-qpi-high-055 0.55 0.55
write_overall "omega_055_done" 2 "running"
run_cell cell-l40-qpi-high-100 1.00 1.00
write_overall "omega_100_done" 3 "running"
run_cell cell-l40-qpi-high-150 1.50 1.50
write_overall "finished" 4 "success"
echo "QPI_CV_EXTENSION_SUCCESS run_root=$run_root"
