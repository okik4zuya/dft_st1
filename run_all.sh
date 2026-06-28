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
#
# Usage:
#   bash run_all.sh                 # full pipeline (relax+inject+post), all systems
#   bash run_all.sh relax           # PHASE 1 only (vc-relax + inject), all systems, then STOP
#   bash run_all.sh post            # PHASE 2 only, all systems
#   bash run_all.sh relax pristine  # PHASE 1 only, one system
#   bash run_all.sh post  ratio_2to1
#   bash run_all.sh unrelaxed       # distortion-isolation SCF (doped systems)
#   bash run_all.sh pristine        # full pipeline, one system (back-compat)
# =============================================================================

set -eo pipefail

# --- Phase / system selection ----------------------------------------------
PHASE="all"
case "$1" in
    relax|post|all|unrelaxed) PHASE="$1"; shift ;;
esac

# --- Logging helpers (defined early so resource setup can report) -----------
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()   { echo -e "${RED}[ERROR]${NC} $1"; }

# --- Resource configuration (portable: laptop -> EPYC node) -----------------
# The script auto-sizes the parallel layout to whatever machine it runs on and
# always chooses a SAFE, STABLE one:
#   * MPI ranks default to PHYSICAL cores (QE runs best on physical, not SMT
#     threads — nproc would report 128 logical on the 7773X and oversubscribe).
#   * A RAM guard caps ranks so a big SCF can't get OOM-killed on a small box.
#   * k-pools (npool) are chosen as a TRUE DIVISOR of the final rank count and
#     never exceed it. An npool that does not divide nproc makes pw.x ABORT, so
#     this is correctness on odd core counts (6, 28, ...), not just tuning.
#   * Serial fallback if no mpirun is on PATH.
# Every knob is overridable, e.g.:
#   NPROC=8 bash run_all.sh post           # force 8 ranks on a laptop
#   OMP_NUM_THREADS=2 bash run_all.sh       # hybrid 2 OpenMP threads per rank
#   NK_PW=4 NK_BANDS=2 bash run_all.sh      # pin k-pools by hand
#   MEM_PER_RANK_MB=500 bash run_all.sh     # larger cell -> reserve more RAM

# 1) MPI ranks from physical cores (override with NPROC=...) ------------------
detect_phys_cores() {
    local n="" s c
    if command -v lscpu >/dev/null 2>&1; then
        s=$(lscpu 2>/dev/null | awk -F: '/^Socket\(s\)/{gsub(/ /,"",$2); print $2}')
        c=$(lscpu 2>/dev/null | awk -F: '/^Core\(s\) per socket/{gsub(/ /,"",$2); print $2}')
        [ -n "$s" ] && [ -n "$c" ] && n=$(( s * c ))
    fi
    if [ -z "$n" ] && [ -r /proc/cpuinfo ]; then
        n=$(awk -F: '/^physical id/{p=$2} /^core id/{print p":"$2}' /proc/cpuinfo \
              | sort -u | wc -l | tr -d '[:space:]')
    fi
    case "$n" in ''|*[!0-9]*) n="" ;; esac
    [ -n "$n" ] && [ "$n" -lt 1 ] && n=""
    [ -z "$n" ] && n=$(nproc 2>/dev/null || getconf _NPROCESSORS_ONLN 2>/dev/null || echo 1)
    echo "$n"
}
NPROC=${NPROC:-$(detect_phys_cores)}
export OMP_NUM_THREADS=${OMP_NUM_THREADS:-1}
MPI_NPROC=$(( NPROC / OMP_NUM_THREADS ))
(( MPI_NPROC < 1 )) && MPI_NPROC=1

# 2) RAM guard: cap ranks to what memory can hold (override MEM_PER_RANK_MB) --
#    Benchmark: this 24-atom cell used ~50 MB/rank; default 300 keeps headroom
#    for the larger doped supercells and the post-processing tools.
MEM_PER_RANK_MB=${MEM_PER_RANK_MB:-300}
AVAIL_MB=0
[ -r /proc/meminfo ] && AVAIL_MB=$(awk '/^MemAvailable:/{print int($2/1024)}' /proc/meminfo)
if [ "${AVAIL_MB:-0}" -gt 0 ]; then
    MAX_RANKS_MEM=$(( AVAIL_MB / MEM_PER_RANK_MB ))
    (( MAX_RANKS_MEM < 1 )) && MAX_RANKS_MEM=1
    if (( MPI_NPROC > MAX_RANKS_MEM )); then
        warn "RAM guard: ${AVAIL_MB} MB free, ${MEM_PER_RANK_MB} MB/rank -> capping ranks ${MPI_NPROC} -> ${MAX_RANKS_MEM}."
        MPI_NPROC=$MAX_RANKS_MEM
    fi
fi

# 3) MPI launcher, with serial fallback. --allow-run-as-root is OpenMPI-only
#    (MPICH errors on it), so add it only under OpenMPI AND when actually root.
SERIAL=0
if command -v mpirun >/dev/null 2>&1; then
    MPI_LAUNCH="mpirun"
    if mpirun --version 2>/dev/null | grep -qiE 'open[ -]?mpi' && [ "$(id -u 2>/dev/null)" = "0" ]; then
        MPI_LAUNCH="mpirun --allow-run-as-root"
    fi
    MPI="${MPI_LAUNCH} -np ${MPI_NPROC}"
else
    warn "mpirun not found -> running pw.x serially. Add your MPI to PATH if unintended."
    SERIAL=1; MPI_NPROC=1; MPI=""
fi

# 4) k-pools as a TRUE DIVISOR of the final rank count -----------------------
#    SCF/NSCF target ~8 ranks/pool (cache-friendly; 97.4% eff. at 64 ranks).
#    Bands path targets ~16 ranks/pool (CG FFT-bound; fewer pools = faster/kpt).
largest_divisor_leq() {   # echo largest d with d|n and 1<=d<=cap
    local n=$1 cap=$2 d
    (( cap < 1 )) && cap=1
    (( cap > n )) && cap=$n
    for (( d=cap; d>=1; d-- )); do (( n % d == 0 )) && { echo "$d"; return; }; done
    echo 1
}
NK_PW=${NK_PW:-$(largest_divisor_leq "$MPI_NPROC" $(( MPI_NPROC / 8 )) )}
NK_BANDS=${NK_BANDS:-$(largest_divisor_leq "$MPI_NPROC" $(( MPI_NPROC / 16 )) )}

# 5) Command assembly --------------------------------------------------------
PW_SCF="${MPI} pw.x -nk ${NK_PW}"      # SCF / vc-relax
PW_NSCF="${MPI} pw.x -nk ${NK_PW}"     # NSCF (dense mesh, same pools)
PW_BANDS="${MPI} pw.x -nk ${NK_BANDS}" # band path (more ranks/pool for CG FFT)
DOS="${MPI} dos.x"
PROJWFC="${MPI} projwfc.x"
BANDS="${MPI} bands.x"
EPSILON="${MPI} epsilon.x"
PP="${MPI} pp.x"

ROOT_DIR="$(pwd)"
PROGRESS_FILE="${ROOT_DIR}/progress.md"
GEOM_TOOL="${ROOT_DIR}/update_geometry.py"
PYTHON=${PYTHON:-python3}

# Returns 0 if the given output file exists and contains "JOB DONE"
step_done() {
    local outfile=$1
    [ -f "$outfile" ] && grep -q "JOB DONE" "$outfile"
}

log_progress() {
    local sys=$1 step=$2 status=$3
    printf -- "- [%s] %-12s | %-18s | %s\n" \
        "$(date '+%Y-%m-%d %H:%M')" "$sys" "$step" "$status" \
        >> "${PROGRESS_FILE}"
}

# Propagate the relaxed geometry from <sys>/relax/<prefix>.relax.out into the
# scf/nscf/bands inputs. Aborts the whole run if the structure fails the
# bond-length sanity check or cannot be parsed. THIS is the safety gate.
inject_geometry() {
    local SYS=$1 PREFIX=$2
    local relax_out="${ROOT_DIR}/${SYS}/relax/${PREFIX}.relax.out"
    info "[${SYS}] Propagating relaxed geometry -> scf/nscf/bands ..."
    if "${PYTHON}" "${GEOM_TOOL}" "${relax_out}" \
            "${ROOT_DIR}/${SYS}/scf/${PREFIX}.scf.in" \
            "${ROOT_DIR}/${SYS}/nscf/${PREFIX}.nscf.in" \
            "${ROOT_DIR}/${SYS}/bands/${PREFIX}.bands.in"; then
        log_progress "$SYS" "geometry-inject" "DONE"
    else
        local rc=$?
        log_progress "$SYS" "geometry-inject" "FAILED (rc=$rc)"
        err "[${SYS}] geometry injection failed (rc=$rc) — HALTING."
        err "  Inspect ${relax_out}. Do NOT run scf/nscf on a bad geometry."
        exit 1
    fi
}

SYSTEMS=("pristine" "ratio_1to1" "ratio_2to1" "TiO2")
[ -n "$1" ] && SYSTEMS=("$1")

prefix_of() {
    case $1 in
        pristine)    echo "SnO2_pristine" ;;
        ratio_1to1)  echo "SnO2_1to1"     ;;
        ratio_2to1)  echo "SnO2_2to1"     ;;
        TiO2)        echo "TiO2_pristine" ;;
        *)           err "Unknown system: $1"; exit 1 ;;
    esac
}

# --- Initialize progress log ------------------------------------------------
[ -f "${PROGRESS_FILE}" ] || echo "# Simulation Progress" > "${PROGRESS_FILE}"
echo "" >> "${PROGRESS_FILE}"
echo "## Run $(date '+%Y-%m-%d %H:%M') | Phase: ${PHASE} | Systems: ${SYSTEMS[*]} | MPI: ${MPI_NPROC}x${OMP_NUM_THREADS} NK_PW: ${NK_PW} NK_BANDS: ${NK_BANDS}" >> "${PROGRESS_FILE}"

# --- PHASE 1: vc-relax + geometry injection --------------------------------
run_relax() {
    local SYS=$1 PREFIX=$2
    info "[${SYS}] PHASE 1: vc-relax ..."
    cd "${ROOT_DIR}/${SYS}/relax"
    mkdir -p tmp
    if step_done "${PREFIX}.relax.out"; then
        info "[${SYS}] vc-relax already done, skipping."
        log_progress "$SYS" "vc-relax" "SKIPPED (already done)"
    else
        $PW_SCF -in ${PREFIX}.relax.in > ${PREFIX}.relax.out 2>&1 \
            && { info "[${SYS}] vc-relax DONE"; log_progress "$SYS" "vc-relax" "DONE"; } \
            || { log_progress "$SYS" "vc-relax" "FAILED"; err "vc-relax failed for ${SYS}"; exit 1; }
    fi
    cd "${ROOT_DIR}"
    inject_geometry "$SYS" "$PREFIX"
}

# --- UNRELAXED: distortion-isolation SCF (doped systems only) ---------------
# Runs pw.x on <sys>/scf_unrelaxed/<prefix>.scf.in, which holds the IDEAL
# pristine-supercell coordinates (O removed, atoms NOT relaxed). Deliberately
# does NOT call inject_geometry — the whole point is the unrelaxed geometry.
# Comparing this gap with the relaxed scf/ gap isolates the distortion effect.
run_unrelaxed() {
    local SYS=$1 PREFIX=$2
    local dir="${ROOT_DIR}/${SYS}/scf_unrelaxed"
    if [ ! -f "${dir}/${PREFIX}.scf.in" ]; then
        info "[${SYS}] no scf_unrelaxed input (not a doped system), skipping."
        return 0
    fi
    info "[${SYS}] UNRELAXED SCF (distortion isolation)..."
    cd "${dir}"
    mkdir -p tmp
    if step_done "${PREFIX}.scf.out"; then
        info "[${SYS}] unrelaxed SCF already done, skipping."
        log_progress "$SYS" "SCF-unrelaxed" "SKIPPED (already done)"
    else
        $PW_SCF -in ${PREFIX}.scf.in > ${PREFIX}.scf.out 2>&1 \
            && { info "[${SYS}] unrelaxed SCF DONE"; log_progress "$SYS" "SCF-unrelaxed" "DONE"; } \
            || { log_progress "$SYS" "SCF-unrelaxed" "FAILED"; err "unrelaxed SCF failed for ${SYS}"; exit 1; }
    fi
    cd "${ROOT_DIR}"
}

# --- PHASE 2: scf -> nscf -> bands -> dos -> optical -> pp ------------------
run_post() {
    local SYS=$1 PREFIX=$2

    # --- Step 2: SCF --------------------------------------------------------
    info "[${SYS}] Step 2/7: SCF..."
    cd "${ROOT_DIR}/${SYS}/scf"
    mkdir -p tmp
    if step_done "${PREFIX}.scf.out"; then
        info "[${SYS}] SCF already done, skipping."
        log_progress "$SYS" "SCF" "SKIPPED (already done)"
    else
        $PW_SCF -in ${PREFIX}.scf.in > ${PREFIX}.scf.out 2>&1 \
            && { info "[${SYS}] SCF DONE"; log_progress "$SYS" "SCF" "DONE"; } \
            || { log_progress "$SYS" "SCF" "FAILED"; err "SCF failed for ${SYS}"; exit 1; }
    fi

    # --- Step 3: NSCF -------------------------------------------------------
    info "[${SYS}] Step 3/7: NSCF..."
    cd "${ROOT_DIR}/${SYS}/nscf"
    # nscf/tmp must POINT AT scf/tmp (be a symlink, not a real dir) so that
    # outdir './tmp' resolves to the SCF .save. The old 'mkdir -p tmp; ln ... tmp/'
    # created a real dir with a broken link inside -> 'data-file-schema.xml not
    # found'. Replace any stale tmp with a clean symlink.
    rm -rf tmp 2>/dev/null || true
    ln -sfn ../scf/tmp tmp
    if step_done "${PREFIX}.nscf.out"; then
        info "[${SYS}] NSCF already done, skipping."
        log_progress "$SYS" "NSCF" "SKIPPED (already done)"
    else
        $PW_NSCF -in ${PREFIX}.nscf.in > ${PREFIX}.nscf.out 2>&1 \
            && { info "[${SYS}] NSCF DONE"; log_progress "$SYS" "NSCF" "DONE"; } \
            || { log_progress "$SYS" "NSCF" "FAILED"; err "NSCF failed for ${SYS}"; exit 1; }
    fi

    # --- Step 4: Bands ------------------------------------------------------
    info "[${SYS}] Step 4/7: Band structure..."
    cd "${ROOT_DIR}/${SYS}/bands"
    rm -rf tmp 2>/dev/null || true
    ln -sfn ../scf/tmp tmp
    if step_done "${PREFIX}.bands_pp.out"; then
        info "[${SYS}] Bands already done, skipping."
        log_progress "$SYS" "Bands" "SKIPPED (already done)"
    else
        $PW_BANDS -in ${PREFIX}.bands.in    > ${PREFIX}.bands.out    2>&1
        $BANDS -in ${PREFIX}.bands_pp.in > ${PREFIX}.bands_pp.out 2>&1 \
            && { info "[${SYS}] Bands DONE"; log_progress "$SYS" "Bands" "DONE"; } \
            || { log_progress "$SYS" "Bands" "FAILED"; err "Bands failed for ${SYS}"; exit 1; }
    fi

    # --- Step 5: DOS + PDOS -------------------------------------------------
    info "[${SYS}] Step 5/7: DOS and PDOS..."
    cd "${ROOT_DIR}/${SYS}/dos"
    rm -rf tmp 2>/dev/null || true
    ln -sfn ../nscf/tmp tmp
    if step_done "${PREFIX}.pdos.out"; then
        info "[${SYS}] DOS/PDOS already done, skipping."
        log_progress "$SYS" "DOS/PDOS" "SKIPPED (already done)"
    else
        $DOS     -in ${PREFIX}.dos.in  > ${PREFIX}.dos.out  2>&1
        $PROJWFC -in ${PREFIX}.pdos.in > ${PREFIX}.pdos.out 2>&1 \
            && { info "[${SYS}] DOS/PDOS DONE"; log_progress "$SYS" "DOS/PDOS" "DONE"; } \
            || { log_progress "$SYS" "DOS/PDOS" "FAILED"; err "DOS failed for ${SYS}"; exit 1; }
    fi

    # --- Step 6: Optical ----------------------------------------------------
    info "[${SYS}] Step 6/7: Optical absorption (epsilon.x)..."
    warn "[${SYS}] If not yet set: scissor shift in ${SYS}/optical/${PREFIX}.epsilon.in"
    warn "  (read Eg_PBE+U from band structure first)"
    cd "${ROOT_DIR}/${SYS}/optical"
    rm -rf tmp 2>/dev/null || true
    ln -sfn ../nscf/tmp tmp
    if step_done "${PREFIX}.epsilon.out"; then
        info "[${SYS}] Optical already done, skipping."
        log_progress "$SYS" "Optical" "SKIPPED (already done)"
    else
        $EPSILON -in ${PREFIX}.epsilon.in > ${PREFIX}.epsilon.out 2>&1 \
            && { info "[${SYS}] Optical DONE"; log_progress "$SYS" "Optical" "DONE"; } \
            || { log_progress "$SYS" "Optical" "FAILED"; err "epsilon.x failed for ${SYS}"; exit 1; }
    fi

    # --- Step 7: Charge density (pp.x) -------------------------------------
    info "[${SYS}] Step 7/7: Charge density (pp.x)..."
    cd "${ROOT_DIR}/${SYS}/pp"
    rm -rf tmp 2>/dev/null || true
    ln -sfn ../scf/tmp tmp
    if step_done "${PREFIX}.pp.out"; then
        info "[${SYS}] pp (charge density) already done, skipping."
        log_progress "$SYS" "pp (charge dens.)" "SKIPPED (already done)"
    else
        $PP -in ${PREFIX}.pp.in > ${PREFIX}.pp.out 2>&1 \
            && { info "[${SYS}] Charge density DONE"; log_progress "$SYS" "pp (charge dens.)" "DONE"; } \
            || { log_progress "$SYS" "pp (charge dens.)" "FAILED"; err "pp.x failed for ${SYS}"; exit 1; }
    fi

    cd "${ROOT_DIR}"
    info "[${SYS}] PHASE 2 complete."
    log_progress "$SYS" "ALL STEPS" "COMPLETE"
    echo ""
}

# --- Preflight: fail fast with a clear message instead of a 64-rank mpirun dump
preflight() {
    if ! command -v pw.x >/dev/null 2>&1; then
        err "pw.x not found on PATH. Quantum ESPRESSO is not loaded in this shell."
        err "  Fix e.g.:  export PATH=/path/to/qe/bin:\$PATH   (add to ~/.bashrc to persist)"
        err "  Verify:    which pw.x && pw.x --version"
        exit 1
    fi
    local missing=0
    for f in pseudo/Sn.pbesol-dn-kjpaw_psl.1.0.0.UPF \
             pseudo/O.pbesol-n-kjpaw_psl.1.0.0.UPF \
             pseudo/Ti.pbesol-spn-kjpaw_psl.1.0.0.UPF; do
        [ -f "${ROOT_DIR}/$f" ] || { warn "missing pseudopotential: $f"; missing=1; }
    done
    [ "$missing" -eq 0 ] || { err "pseudopotential(s) missing under ${ROOT_DIR}/pseudo/"; exit 1; }
    info "preflight OK: $(command -v pw.x) | $(pw.x --version 2>/dev/null | head -1)"
}
preflight
if [ "$SERIAL" = "1" ]; then
    info "Resources: SERIAL (no mpirun) | 1 rank | NK_PW=${NK_PW} NK_BANDS=${NK_BANDS}"
else
    info "Resources: ${MPI_NPROC} MPI ranks × OMP=${OMP_NUM_THREADS} | NK_PW=${NK_PW} ($(( MPI_NPROC / NK_PW )) ranks/pool) | NK_BANDS=${NK_BANDS} ($(( MPI_NPROC / NK_BANDS )) ranks/pool)"
fi

for SYS in "${SYSTEMS[@]}"; do
    PREFIX="$(prefix_of "$SYS")"
    info "========================================================"
    info "  System: ${SYS} (prefix: ${PREFIX}) | phase: ${PHASE}"
    info "========================================================"
    case "$PHASE" in
        relax)     run_relax "$SYS" "$PREFIX" ;;
        post)      inject_geometry "$SYS" "$PREFIX"; run_post "$SYS" "$PREFIX" ;;
        all)       run_relax "$SYS" "$PREFIX"; run_post "$SYS" "$PREFIX" ;;
        unrelaxed) run_unrelaxed "$SYS" "$PREFIX" ;;
    esac
done

if [ "$PHASE" = "unrelaxed" ]; then
    echo ""
    info "Unrelaxed SCF done for doped systems."
    info "Compare gap(scf_unrelaxed) vs gap(scf) to isolate the distortion effect,"
    info "then run:  python distortion_analysis.py"
    exit 0
fi

if [ "$PHASE" = "relax" ]; then
    echo ""
    info "PHASE 1 done. Relaxed geometry injected into scf/nscf/bands inputs."
    warn "REVIEW before continuing:"
    warn "  1. Check each */relax/*.relax.out ended with 'bfgs converged' and low pressure."
    warn "  2. Spot-check the injected CELL_PARAMETERS/ATOMIC_POSITIONS in */scf/*.scf.in."
    warn "  3. Set scissor shifts in */optical/*.epsilon.in if known."
    info "Then run:  bash run_all.sh post"
    exit 0
fi

info "All systems complete. Run post-processing Python scripts next."
echo ""
echo "Output files summary:"
echo "  Band structure : */bands/*.dat"
echo "  Total DOS      : */dos/*_total.dos"
echo "  PDOS           : */dos/*_pdos.pdos_atm*"
echo "  epsilon(omega) : */optical/epsilon_re.dat, epsilon_im.dat"
echo "  Charge density : */pp/*.cube"
