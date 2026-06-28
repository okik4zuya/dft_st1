#!/bin/bash
# =============================================================================
# run_vcrelax.sh — overnight-stable vc-relax driver (PHASE 1 only)
# SnO2-x / TiO2 DFT study | Quantum ESPRESSO v7.x
# =============================================================================
# Purpose: run vc-relax for one, several, or all systems UNATTENDED.
#
# Difference vs `run_all.sh relax`:
#   - FAILURE ISOLATION: a crash/non-convergence in one system does NOT abort
#     the others. Every selected system is attempted; a summary is printed and
#     the script exits non-zero only if something actually failed.
#   - Writes a persistent, timestamped master log so you can review in the
#     morning even if the SSH session dropped.
#   - System SELECTION as positional args (subset or `all`).
#
# Usage:
#   bash run_vcrelax.sh                      # all systems (default)
#   bash run_vcrelax.sh all                  # all systems (explicit)
#   bash run_vcrelax.sh pristine             # one system
#   bash run_vcrelax.sh pristine ratio_2to1  # a chosen subset
#   bash run_vcrelax.sh --inject all         # also inject relaxed geometry
#                                            #   into scf/nscf/bands afterwards
#   bash run_vcrelax.sh -l                   # list valid system names and exit
#   bash run_vcrelax.sh -h                   # help
#
# Run it overnight, detached from the terminal (survives logout / dropped SSH):
#   nohup bash run_vcrelax.sh all >/dev/null 2>&1 &
#   tail -f vcrelax_*.log        # watch progress
#
# Notes:
#   - Already-finished systems (JOB DONE present) are skipped, so it is safe to
#     re-run after a partial night.
#   - Geometry injection is OPT-IN (--inject). Without it, review each
#     */relax/*.relax.out first, then run `bash run_all.sh post` (or per-system
#     `run.sh inject`) once you trust the geometry.
# =============================================================================

set -o pipefail   # deliberately NOT `set -e`: we want to survive a failing system

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=run_lib.sh
source "${ROOT_DIR}/run_lib.sh"

ALL_SYSTEMS=("pristine" "ratio_1to1" "ratio_2to1" "TiO2")

usage() {
    sed -n '2,46p' "$0" | sed 's/^# \{0,1\}//'
    exit "${1:-0}"
}

list_systems() {
    echo "Valid systems:"
    for s in "${ALL_SYSTEMS[@]}"; do
        printf "  %-12s -> %s\n" "$s" "$(prefix_of "$s")"
    done
    exit 0
}

# --- Parse flags + system selection -----------------------------------------
DO_INJECT=0
SELECTED=()
while [ $# -gt 0 ]; do
    case "$1" in
        --inject)   DO_INJECT=1 ;;
        -l|--list)  list_systems ;;
        -h|--help)  usage 0 ;;
        all)        SELECTED=("${ALL_SYSTEMS[@]}") ;;
        -*)         err "Unknown option: $1"; usage 1 ;;
        *)
            # validate against the known set
            valid=0
            for s in "${ALL_SYSTEMS[@]}"; do [ "$s" = "$1" ] && valid=1 && break; done
            if [ "$valid" -eq 1 ]; then
                SELECTED+=("$1")
            else
                err "Unknown system: '$1'. Run with -l to list valid names."
                exit 1
            fi
            ;;
    esac
    shift
done
[ ${#SELECTED[@]} -eq 0 ] && SELECTED=("${ALL_SYSTEMS[@]}")

# De-duplicate while preserving order (in case 'pristine pristine' etc.)
declare -A _seen
_uniq=()
for s in "${SELECTED[@]}"; do
    [ -n "${_seen[$s]:-}" ] && continue
    _seen[$s]=1; _uniq+=("$s")
done
SELECTED=("${_uniq[@]}")

# --- Master log (also tee'd to console) -------------------------------------
LOGFILE="${ROOT_DIR}/vcrelax_$(date '+%Y%m%d_%H%M%S').log"
exec > >(tee -a "${LOGFILE}") 2>&1

# --- Preflight (aborts before starting if QE / pseudos are missing) ---------
preflight

[ -f "${PROGRESS_FILE}" ] || echo "# Simulation Progress" > "${PROGRESS_FILE}"
echo "" >> "${PROGRESS_FILE}"
echo "## Run $(date '+%Y-%m-%d %H:%M') | vc-relax | Systems: ${SELECTED[*]} | inject: ${DO_INJECT} | MPI: ${MPI_NPROC}x${OMP_NUM_THREADS} NK_PW: ${NK_PW}" >> "${PROGRESS_FILE}"

info "Master log: ${LOGFILE}"
info "Selected systems: ${SELECTED[*]} | inject after relax: $([ "$DO_INJECT" = 1 ] && echo yes || echo no)"

# --- Non-fatal vc-relax for one system --------------------------------------
# Returns: 0 done/skipped-done | 1 failed | 2 skipped (no input)
do_vcrelax() {
    local SYS=$1 PREFIX=$2
    local dir="${ROOT_DIR}/${SYS}/relax"
    local out="${PREFIX}.relax.out"

    if [ ! -f "${dir}/${PREFIX}.relax.in" ]; then
        warn "[${SYS}] no relax input at ${dir}/${PREFIX}.relax.in — skipping."
        log_progress "$SYS" "vc-relax" "SKIPPED (no input)"
        return 2
    fi

    cd "${dir}" || { err "[${SYS}] cannot cd to ${dir}"; return 1; }
    mkdir -p tmp

    if step_done "$out"; then
        info "[${SYS}] vc-relax already done, skipping."
        log_progress "$SYS" "vc-relax" "SKIPPED (already done)"
        cd "${ROOT_DIR}"; return 0
    fi

    info "[${SYS}] vc-relax starting $(date '+%F %T') ..."
    if $PW_SCF -in "${PREFIX}.relax.in" > "${out}" 2>&1 && grep -q "JOB DONE" "${out}"; then
        info "[${SYS}] vc-relax DONE $(date '+%F %T')"
        log_progress "$SYS" "vc-relax" "DONE"
        cd "${ROOT_DIR}"; return 0
    fi

    err "[${SYS}] vc-relax FAILED — inspect ${dir}/${out}"
    log_progress "$SYS" "vc-relax" "FAILED"
    cd "${ROOT_DIR}"; return 1
}

# --- Non-fatal geometry injection -------------------------------------------
do_inject() {
    local SYS=$1 PREFIX=$2
    local relax_out="${ROOT_DIR}/${SYS}/relax/${PREFIX}.relax.out"
    info "[${SYS}] injecting relaxed geometry -> scf/nscf/bands ..."
    if "${PYTHON}" "${GEOM_TOOL}" "${relax_out}" \
            "${ROOT_DIR}/${SYS}/scf/${PREFIX}.scf.in" \
            "${ROOT_DIR}/${SYS}/nscf/${PREFIX}.nscf.in" \
            "${ROOT_DIR}/${SYS}/bands/${PREFIX}.bands.in"; then
        log_progress "$SYS" "geometry-inject" "DONE"
        return 0
    fi
    warn "[${SYS}] geometry injection failed (bond guard / parse) — review ${relax_out}."
    log_progress "$SYS" "geometry-inject" "FAILED"
    return 1
}

# --- Main loop (failure-isolated) -------------------------------------------
DONE_SYS=(); FAIL_SYS=(); SKIP_SYS=(); INJECT_FAIL=()
START_TS=$(date '+%s')

for SYS in "${SELECTED[@]}"; do
    PREFIX="$(prefix_of "$SYS")"
    info "========================================================"
    info "  System: ${SYS} (prefix: ${PREFIX})"
    info "========================================================"

    do_vcrelax "$SYS" "$PREFIX"
    case $? in
        0)  DONE_SYS+=("$SYS")
            if [ "$DO_INJECT" = 1 ]; then
                do_inject "$SYS" "$PREFIX" || INJECT_FAIL+=("$SYS")
            fi
            ;;
        2)  SKIP_SYS+=("$SYS") ;;
        *)  FAIL_SYS+=("$SYS") ;;
    esac
done

# --- Summary ----------------------------------------------------------------
ELAPSED=$(( $(date '+%s') - START_TS ))
echo ""
info "========================================================"
info "  vc-relax run summary  ($(date '+%F %T'), elapsed $(( ELAPSED/3600 ))h$(( (ELAPSED%3600)/60 ))m)"
info "========================================================"
info "  done    : ${DONE_SYS[*]:-none}"
[ ${#SKIP_SYS[@]}    -gt 0 ] && warn "  skipped : ${SKIP_SYS[*]} (no input file)"
[ ${#INJECT_FAIL[@]} -gt 0 ] && warn "  inject  : FAILED for ${INJECT_FAIL[*]} (geometry not propagated)"
if [ ${#FAIL_SYS[@]} -gt 0 ]; then
    err "  FAILED  : ${FAIL_SYS[*]}"
    err "Review the *.relax.out for the failed system(s). Other systems completed."
fi
info "Master log saved: ${LOGFILE}"
echo ""
log_progress "ALL" "vc-relax batch" "done=${#DONE_SYS[@]} fail=${#FAIL_SYS[@]} skip=${#SKIP_SYS[@]}"

# Non-zero exit if any real failure (vc-relax or requested injection)
[ ${#FAIL_SYS[@]} -gt 0 ] || [ ${#INJECT_FAIL[@]} -gt 0 ] && exit 1
exit 0
