#!/bin/bash
# =============================================================================
# Master run script — SnO2-x/TiO2 DFT calculations
# Systems: pristine SnO2 | 1:1 (12.5% Vo) | 2:1 (18.75% Vo) | pristine TiO2
# Quantum ESPRESSO v7.x
# =============================================================================
# Two-phase workflow (prevents running scf/nscf/bands on an unrelaxed or bad
# geometry — see notes/error.md and the 1737 kbar O-position incident):
#
#   PHASE 1 (relax): vc-relax each system, then AUTO-INJECT the relaxed
#                    CELL_PARAMETERS + ATOMIC_POSITIONS into scf/nscf/bands
#                    inputs via update_geometry.py. A bond-length guard aborts
#                    if any cation-O distance < 1.8 A. Then STOP for review.
#   PHASE 2 (post):  scf -> nscf -> bands -> dos -> optical -> pp.
#                    Geometry injection is NOT run automatically in post —
#                    use 'relax' first, or run inject separately from each
#                    system's run.sh.
#
# Usage:
#   bash run_all.sh                 # full pipeline (relax+inject+post), all systems
#   bash run_all.sh relax           # PHASE 1 only (vc-relax + inject), all systems
#   bash run_all.sh post            # PHASE 2 only (no injection), all systems
#   bash run_all.sh relax pristine  # PHASE 1, one system
#   bash run_all.sh post  ratio_2to1
#   bash run_all.sh unrelaxed       # distortion-isolation SCF (doped systems)
#   bash run_all.sh pristine        # full pipeline, one system (back-compat)
#
# Per-system convenience (from inside system folder):
#   cd pristine && bash run.sh [step]  — no relax.out required for post steps
# =============================================================================

set -eo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=run_lib.sh
source "${ROOT_DIR}/run_lib.sh"

# --- Phase / system selection ------------------------------------------------
PHASE="all"
case "$1" in
    relax|post|all|unrelaxed) PHASE="$1"; shift ;;
esac

SYSTEMS=("pristine" "ratio_1to1" "ratio_2to1" "TiO2")
[ -n "$1" ] && SYSTEMS=("$1")

# --- Preflight + resource summary -------------------------------------------
preflight

# --- Initialize progress log -------------------------------------------------
[ -f "${PROGRESS_FILE}" ] || echo "# Simulation Progress" > "${PROGRESS_FILE}"
echo "" >> "${PROGRESS_FILE}"
echo "## Run $(date '+%Y-%m-%d %H:%M') | Phase: ${PHASE} | Systems: ${SYSTEMS[*]} | MPI: ${MPI_NPROC}x${OMP_NUM_THREADS} NK_PW: ${NK_PW} NK_BANDS: ${NK_BANDS}" >> "${PROGRESS_FILE}"

# --- Main loop ---------------------------------------------------------------
for SYS in "${SYSTEMS[@]}"; do
    PREFIX="$(prefix_of "$SYS")"
    info "========================================================"
    info "  System: ${SYS} (prefix: ${PREFIX}) | phase: ${PHASE}"
    info "========================================================"
    case "$PHASE" in
        relax)      run_relax      "$SYS" "$PREFIX" ;;
        post)       run_post       "$SYS" "$PREFIX" ;;
        all)        run_relax      "$SYS" "$PREFIX"
                    run_post       "$SYS" "$PREFIX" ;;
        unrelaxed)  run_unrelaxed  "$SYS" "$PREFIX" ;;
    esac
done

# --- Phase-specific exit messages --------------------------------------------
case "$PHASE" in
    unrelaxed)
        echo ""
        info "Unrelaxed SCF done for doped systems."
        info "Compare gap(scf_unrelaxed) vs gap(scf) to isolate the distortion effect,"
        info "then run:  python distortion_analysis.py"
        ;;
    relax)
        echo ""
        info "PHASE 1 done. Relaxed geometry injected into scf/nscf/bands inputs."
        warn "REVIEW before continuing:"
        warn "  1. Check each */relax/*.relax.out ended with 'bfgs converged' and low pressure."
        warn "  2. Spot-check the injected CELL_PARAMETERS/ATOMIC_POSITIONS in */scf/*.scf.in."
        warn "  3. Set scissor shifts in */optical/*.epsilon.in if known."
        info "Then run:  bash run_all.sh post"
        ;;
    post|all)
        info "All systems complete. Run post-processing Python scripts next."
        echo ""
        echo "Output files summary:"
        echo "  Band structure : */bands/*.dat"
        echo "  Total DOS      : */dos/*_total.dos"
        echo "  PDOS           : */dos/*_pdos.pdos_atm*"
        echo "  epsilon(omega) : */optical/epsilon_re.dat, epsilon_im.dat"
        echo "  Charge density : */pp/*.cube"
        ;;
esac
