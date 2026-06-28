#!/bin/bash
# Run script for pristine TiO2 system
#
# Usage (from inside this folder or from anywhere):
#   bash run.sh            -> full post pipeline: scf -> nscf -> bands -> dos -> optical -> pp
#   bash run.sh relax      -> vc-relax + inject geometry into scf/nscf/bands
#   bash run.sh inject     -> inject geometry only (from existing relax.out)
#   bash run.sh scf        -> SCF only
#   bash run.sh nscf       -> NSCF only
#   bash run.sh bands      -> band structure only
#   bash run.sh dos        -> DOS + PDOS only
#   bash run.sh optical    -> epsilon.x only
#   bash run.sh pp         -> charge density (pp.x) only
#   bash run.sh post       -> scf -> nscf -> bands -> dos -> optical -> pp (same as no arg)

set -eo pipefail

SYS="TiO2"
PREFIX="TiO2_pristine"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# shellcheck source=../run_lib.sh
source "${ROOT_DIR}/run_lib.sh"

preflight

[ -f "${PROGRESS_FILE}" ] || echo "# Simulation Progress" > "${PROGRESS_FILE}"
echo "" >> "${PROGRESS_FILE}"
echo "## Run $(date '+%Y-%m-%d %H:%M') | System: ${SYS} | Step: ${1:-post} | MPI: ${MPI_NPROC}x${OMP_NUM_THREADS}" >> "${PROGRESS_FILE}"

case "${1:-post}" in
    relax)      run_relax       "$SYS" "$PREFIX" ;;
    inject)     inject_geometry "$SYS" "$PREFIX" ;;
    scf)        run_scf         "$SYS" "$PREFIX" ;;
    nscf)       run_nscf        "$SYS" "$PREFIX" ;;
    bands)      run_bands       "$SYS" "$PREFIX" ;;
    dos)        run_dos         "$SYS" "$PREFIX" ;;
    optical)    run_optical     "$SYS" "$PREFIX" ;;
    pp)         run_pp          "$SYS" "$PREFIX" ;;
    post|*)     run_post        "$SYS" "$PREFIX" ;;
esac
