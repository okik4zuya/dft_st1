#!/bin/bash
# =============================================================================
# run_conv.sh — one-time k-mesh + ecutwfc convergence tests for all systems.
#
# Generates single-point SCF inputs (via conv_test.py) from each system's
# relax.in, then runs every <sys>/conv/*.scf.in with skip/resume. These are
# cheap single SCFs; their total energy / force / pressure tell us the coarsest
# k-mesh (and ecutwfc) that still converges a vc-relax.
#
# Usage (from anywhere):
#   bash run_conv.sh                 # all systems
#   bash run_conv.sh pristine TiO2   # only the named systems
#
# After it finishes:  python conv_test.py analyze
#
# Disk note: each job's ./tmp/<prefix>.save is deleted after JOB DONE — only
# the .out (which holds E/force/stress) is kept.
# =============================================================================

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="${SCRIPT_DIR}"

# shellcheck source=./run_lib.sh
source "${ROOT_DIR}/run_lib.sh"

preflight

# Which systems to run (default: all four)
if [ "$#" -gt 0 ]; then
    SYSTEMS=("$@")
else
    SYSTEMS=(pristine ratio_1to1 ratio_2to1 TiO2)
fi

# (Re)generate the convergence inputs so they always track the current relax.in.
info "Generating convergence inputs from each system's relax.in ..."
"${PYTHON}" "${ROOT_DIR}/conv_test.py" gen

CONV_LOG="${ROOT_DIR}/progress.md"
[ -f "${CONV_LOG}" ] || echo "# Simulation Progress" > "${CONV_LOG}"
echo "" >> "${CONV_LOG}"
echo "## Convergence run $(date '+%Y-%m-%d %H:%M') | MPI: ${MPI_NPROC}x${OMP_NUM_THREADS} | NK_PW=${NK_PW}" >> "${CONV_LOG}"

fail=0
for SYS in "${SYSTEMS[@]}"; do
    conv_dir="${ROOT_DIR}/${SYS}/conv"
    if [ ! -d "${conv_dir}" ]; then
        warn "[${SYS}] no conv/ dir (generation skipped?) — skipping."
        continue
    fi
    shopt -s nullglob
    inputs=("${conv_dir}"/*.conv_*.scf.in)
    shopt -u nullglob
    if [ "${#inputs[@]}" -eq 0 ]; then
        warn "[${SYS}] no convergence inputs found — skipping."
        continue
    fi

    info "[${SYS}] ${#inputs[@]} convergence jobs ..."
    cd "${conv_dir}"
    mkdir -p tmp
    for infile in "${inputs[@]}"; do
        base="$(basename "${infile}" .in)"          # <prefix>.conv_<tag>.scf
        outfile="${base}.out"
        # unique tmp prefix matches conv_test.py: <prefix>_<tag>
        save_prefix="$(echo "${base}" | sed -E 's/\.conv_/_/; s/\.scf$//')"
        if step_done "${outfile}"; then
            info "[${SYS}] ${base} already done, skipping."
            continue
        fi
        info "[${SYS}] running ${base} ..."
        if $PW_SCF -in "$(basename "${infile}")" > "${outfile}" 2>&1; then
            info "[${SYS}] ${base} DONE"
            log_progress "$SYS" "conv:${base##*.conv_}" "DONE"
        else
            warn "[${SYS}] ${base} FAILED (see ${outfile})"
            log_progress "$SYS" "conv:${base##*.conv_}" "FAILED"
            fail=1
        fi
        # reclaim disk: the .out already holds E / force / stress
        rm -rf "tmp/${save_prefix}.save" 2>/dev/null || true
    done
    cd "${ROOT_DIR}"
done

echo ""
if [ "${fail}" -eq 0 ]; then
    info "All convergence jobs finished. Now run:  python conv_test.py analyze"
else
    warn "Some convergence jobs failed — inspect the .out files, then re-run this script (done jobs are skipped)."
fi
