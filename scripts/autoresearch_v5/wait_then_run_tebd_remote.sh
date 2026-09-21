#!/usr/bin/env bash
set -euo pipefail

ROOT=/home/wangjieren/code/1x5_Heisenberg_Pentamer
ANCHOR=/home/wangjieren/code/1x5_Heisenberg_Pentamer/results/autoresearch_v5_20260802/round22_cv_l80_anchor/cell-0003-L80-qpi-w025
ANCHOR_DRIVER_PID=3745209
ANCHOR_PID=3745217
STAGED=$ROOT/scripts/staging_20260803/06_ft_tebd_pentamer_mapped_server.jl
LIVE=$ROOT/scripts/06_ft_tebd_pentamer_mapped_server.jl
RUN=$ROOT/results/autoresearch_v5_20260802/round23_tebd_crosscheck/cell-alpha023-dt025-t15-auto
LOG_DIR=$ROOT/results/autoresearch_v5_20260802/round23_tebd_crosscheck
LOG=$LOG_DIR/sequential_supervisor.log

mkdir -p "$LOG_DIR"
exec >> "$LOG" 2>&1
echo "$(date -Is) supervisor started"

anchor_active() {
    ps -p "$ANCHOR_PID" -o args= | grep -Fq "$ANCHOR"
}

driver_active() {
    ps -p "$ANCHOR_DRIVER_PID" -o args= | grep -Fq "run_cv_dsf_resumable.py"
}

while anchor_active || driver_active; do
    echo "$(date -Is) anchor still running"
    sleep 60
done

if pgrep -af '[c]v_dsf_resumable.jl' | grep -Fq "$ANCHOR" ||
   pgrep -af '[r]un_cv_dsf_resumable.py' | grep -Fq "$ANCHOR"; then
    echo "$(date -Is) anchor command still present; aborting"
    exit 2
fi

if pgrep -af '[j]ulia' | grep -vF "$ANCHOR" | grep -q .; then
    echo "$(date -Is) another Julia task is active; aborting"
    exit 3
fi

test -f "$STAGED"
test ! -e "$RUN"
mkdir -p "$RUN"

backup="$ROOT/scripts/staging_20260803/06_ft_tebd_pentamer_mapped_server.original.$(date +%Y%m%dT%H%M%S).jl"
cp "$LIVE" "$backup"
cp "$STAGED" "$LIVE"
test "$(sha256sum "$LIVE" | awk '{print $1}')" = "e48b8a8c993b0f381de50f4236570bf1c9b56a883ace2ab10cdf8a2da958ba6f"

cd "$ROOT"
nice -n 10 python3 scripts/autoresearch_v5/run_tebd_production.py \
    --cell-id crosscheck-alpha023-dt025-t15-auto \
    --outdir "$RUN" \
    --alpha 0.23 \
    --beta 0.5 \
    --n-units 8 \
    --tstep 0.025 \
    --n-steps 600 \
    --dmrg-maxdim 320 \
    --tebd-maxdim 320 \
    --dmrg-cutoff 1e-10 \
    --tebd-cutoff 1e-9 \
    --nsweeps 24 \
    --q-points 81 \
    --omega-points 181 \
    --omega-max 3 \
    --space-window 18 \
    --threads 8 \
    --standard-sha256 4f00f333eaf810b2853a46e4e258e192db7ef554c7800d35df2ebe27adee4b46 \
    --expected-manifest-sha256 37a53ffd73db57b9db9c4ce11f6265a9a41ac2035dc421b01f9a633d893ba12c \
    --expected-julia-version 1.12.3 \
    --source-commit working-tree-20260803-raw-spectrum \
    --julia /home/wangjieren/.juliaup/bin/julia

echo "$(date -Is) TEBD finished"
