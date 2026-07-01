#!/usr/bin/env bash
# Quick test: can Davidson replace CG in NSCF without the cdiaghg cholesky crash?
# Runs a 4 4 8 nscf (same geometry/nbnd as production) off the existing scf .save.
# Fast if Davidson works (~min at 240 ranks); fails FAST if it still crashes.
#
# NOTE: writes nscf wfc into ../scf/tmp/<prefix>.save (same as a real nscf).
# After a successful test you MUST run the real production nscf to (re)generate
# the .save at your chosen mesh before DOS/PDOS/optical.
set -o pipefail
cd "$(dirname "$0")"

IN="SnO2_pristine.davtest.in"
OUT="SnO2_pristine.davtest.out"

# read scf charge density (same wiring as run_post post_nscf)
rm -rf tmp 2>/dev/null; ln -sfn ../scf/tmp tmp

echo "[davtest] starting $(date '+%F %T')"
mpirun --allow-run-as-root -np 240 pw.x -nk 8 -pd .true. -in "$IN" > "$OUT" 2>&1
rc=$?
echo "[davtest] pw.x exit=$rc  $(date '+%F %T')"

echo "----------------------------------------------------------------------"
if grep -q "JOB DONE" "$OUT"; then
    echo "RESULT: PASS  — Davidson completed without crashing."
    grep -E "cdiaghg|cholesky|not converged" "$OUT" && echo "  (…but warnings above — inspect)" || echo "  no cholesky / convergence warnings."
    grep -E "PWSCF *:|number of k points=" "$OUT" | tail -3
    echo "  -> extrapolate this wall time x (8x8x12 k / 4x4x8 k) for production."
else
    echo "RESULT: FAIL — no JOB DONE. Likely still crashing. Last 25 lines:"
    tail -n 25 "$OUT" | sed 's/^/    | /'
    echo "  Next fallback to try in $IN:  diagonalization='ppcg'  (robust, ~2-4x faster than cg)"
fi
