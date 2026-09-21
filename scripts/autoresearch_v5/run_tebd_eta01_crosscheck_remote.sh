#!/usr/bin/env bash
set -euo pipefail

ROOT=/home/wangjieren/code/1x5_Heisenberg_Pentamer
STAGE=$ROOT/scripts/staging_20260803_eta
RUN_ROOT=$ROOT/results/autoresearch_v5_20260803/round24_tebd_eta01_crosscheck
COARSE=$RUN_ROOT/cell-alpha023-dt025-t30
REFINED=$RUN_ROOT/cell-alpha023-dt0125-t30
OVERALL=$RUN_ROOT/overall_status.json

mkdir -p "$RUN_ROOT"
printf '{"status":"running","phase":"deploy"}\n' > "$OVERALL"

if pgrep -x julia >/dev/null; then
    printf '{"status":"failed","phase":"preflight","reason":"another_julia"}\n' > "$OVERALL"
    exit 3
fi

backup=$STAGE/live_backup_$(date +%Y%m%dT%H%M%S)
mkdir -p "$backup"
cp "$ROOT/scripts/06_ft_tebd_pentamer_mapped_server.jl" "$backup/"
cp "$ROOT/scripts/autoresearch_v5/run_tebd_production.py" "$backup/"
cp "$ROOT/scripts/autoresearch_v5/analyze_tebd_crosscheck.py" "$backup/"
cp "$STAGE/06_ft_tebd_pentamer_mapped_server.jl" "$ROOT/scripts/06_ft_tebd_pentamer_mapped_server.jl"
cp "$STAGE/run_tebd_production.py" "$ROOT/scripts/autoresearch_v5/run_tebd_production.py"
cp "$STAGE/analyze_tebd_crosscheck.py" "$ROOT/scripts/autoresearch_v5/analyze_tebd_crosscheck.py"

test "$(sha256sum "$ROOT/scripts/06_ft_tebd_pentamer_mapped_server.jl" | awk '{print $1}')" = "febb775f49aca2bf561360d939ecfc2fc33aedbd83506de0eaf5577028bf5996"
test "$(sha256sum "$ROOT/scripts/autoresearch_v5/run_tebd_production.py" | awk '{print $1}')" = "453ec26e5f4e36f18488f46537ab83593d8612d69e12e8662a05777d900f7a3d"
test "$(sha256sum "$ROOT/scripts/autoresearch_v5/analyze_tebd_crosscheck.py" | awk '{print $1}')" = "984785f85bba00d23d76c14549b72b94a25bfece210b8ec1b98146668004899b"

run_cell() {
    local cell_id=$1
    local outdir=$2
    local tstep=$3
    local n_steps=$4
    nice -n 10 python3 "$ROOT/scripts/autoresearch_v5/run_tebd_production.py" \
        --cell-id "$cell_id" \
        --outdir "$outdir" \
        --alpha 0.23 \
        --beta 0.5 \
        --n-units 8 \
        --tstep "$tstep" \
        --n-steps "$n_steps" \
        --dmrg-maxdim 320 \
        --tebd-maxdim 320 \
        --dmrg-cutoff 1e-10 \
        --tebd-cutoff 1e-9 \
        --nsweeps 24 \
        --q-points 81 \
        --omega-points 181 \
        --omega-max 3 \
        --space-window 18 \
        --time-window exponential \
        --window-eta 0.1 \
        --threads 8 \
        --standard-sha256 4f00f333eaf810b2853a46e4e258e192db7ef554c7800d35df2ebe27adee4b46 \
        --expected-manifest-sha256 37a53ffd73db57b9db9c4ce11f6265a9a41ac2035dc421b01f9a633d893ba12c \
        --expected-julia-version 1.12.3 \
        --source-commit working-tree-20260803-exp-window-eta01 \
        --julia /home/wangjieren/.juliaup/bin/julia
}

printf '{"status":"running","phase":"coarse"}\n' > "$OVERALL"
if run_cell tebd-alpha023-dt025-t30 "$COARSE" 0.025 1200; then
    :
else
    rc=$?
    printf '{"status":"failed","phase":"coarse","reason":"cell_rejected_or_execution_failed","returncode":%d}\n' "$rc" > "$OVERALL"
    exit "$rc"
fi

printf '{"status":"running","phase":"refined"}\n' > "$OVERALL"
if run_cell tebd-alpha023-dt0125-t30 "$REFINED" 0.0125 2400; then
    :
else
    rc=$?
    printf '{"status":"failed","phase":"refined","reason":"cell_rejected_or_execution_failed","returncode":%d}\n' "$rc" > "$OVERALL"
    exit "$rc"
fi

printf '{"status":"running","phase":"crosscheck"}\n' > "$OVERALL"
if python3 "$ROOT/scripts/autoresearch_v5/analyze_tebd_crosscheck.py" \
    --coarse-dir "$COARSE" \
    --refined-dir "$REFINED" \
    --output "$RUN_ROOT/crosscheck.json"; then
    :
else
    rc=$?
    printf '{"status":"failed","phase":"crosscheck","reason":"dt_half_crosscheck_failed","returncode":%d}\n' "$rc" > "$OVERALL"
    exit "$rc"
fi

printf '{"status":"success","phase":"finished"}\n' > "$OVERALL"
