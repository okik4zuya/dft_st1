#!/bin/bash
# =============================================================================
# run_lib.sh — shared functions for run_all.sh and per-system run.sh scripts
#
# SOURCE this file; do not execute it directly.
# Callers must set ROOT_DIR before sourcing (or it defaults to this file's dir).
# =============================================================================

# Project root — default to this file's directory if not set by caller
_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${ROOT_DIR:-${_LIB_DIR}}"

PROGRESS_FILE="${ROOT_DIR}/progress.md"
GEOM_TOOL="${ROOT_DIR}/update_geometry.py"
PYTHON="${PYTHON:-python3}"

# --- Colour logging helpers --------------------------------------------------
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; }

# --- Step completion check ---------------------------------------------------
# Returns 0 if the output file exists and QE printed "JOB DONE"
step_done() {
    local outfile=$1
    [ -f "$outfile" ] && grep -q "JOB DONE" "$outfile"
}

# --- Progress log ------------------------------------------------------------
log_progress() {
    local sys=$1 step=$2 status=$3
    printf -- "- [%s] %-12s | %-18s | %s\n" \
        "$(date '+%Y-%m-%d %H:%M')" "$sys" "$step" "$status" \
        >> "${PROGRESS_FILE}"
}

# --- Resource configuration --------------------------------------------------

# 1) Physical-core detection (avoids SMT over-subscription)
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

# 2) RAM guard: cap ranks at AvailMem / MEM_PER_RANK_MB (default 300 MB)
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

# 2a) Rank ceiling: guard against FFT over-decomposition on very large nodes.
#     These 24-atom cells have only ~36-45 FFT z-planes; pw.x slab FFT fails once
#     ranks-per-pool exceeds the plane count.  Default 256 is generous — it never
#     trims the 245-core box this study runs on (245 < 256) but protects 512+
#     core nodes.  Lower it toward the 64-128 sweet spot ([[reference-qe-parallel-scaling]])
#     to free cores for running systems concurrently.
MAX_RANKS=${MAX_RANKS:-256}
if (( MPI_NPROC > MAX_RANKS )); then
    info "Rank ceiling: capping ${MPI_NPROC} -> ${MAX_RANKS} (MAX_RANKS; guards small-cell FFT)."
    MPI_NPROC=$MAX_RANKS
fi

# 2b) Rank grain: trim the rank count to a multiple of RANK_GRAIN.
#     A raw core/RAM-derived total can be an ugly number (e.g. 245 = 5*7*7)
#     whose only divisors {1,5,7,35,49} never divide a k-point mesh, so npool
#     CANNOT load-balance no matter how it is chosen.  Trimming to a multiple of
#     16 costs <RANK_GRAIN cores but makes the total share factors {2,4,8,16}
#     with the meshes used here (3x3x6 ~16 irr-k, 4x4x8 ~35).  Portable: a
#     64/96/128-core node is already a multiple of 16 and is left untouched.
#     Skip for small nodes (< 2*grain) where every core matters.
RANK_GRAIN=${RANK_GRAIN:-16}
if (( MPI_NPROC >= 2 * RANK_GRAIN )); then
    _grained=$(( MPI_NPROC - MPI_NPROC % RANK_GRAIN ))
    if (( _grained != MPI_NPROC )); then
        info "Rank grain: trimming ${MPI_NPROC} -> ${_grained} (multiple of ${RANK_GRAIN}) for clean k-pool division."
        MPI_NPROC=$_grained
    fi
fi

# 3) MPI launcher, with --allow-run-as-root only under OpenMPI + root
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

# 4) k-pools as a TRUE DIVISOR of the final rank count
#    An npool that does not divide nproc makes pw.x ABORT — this is a correctness fix.
largest_divisor_leq() {   # echo largest d with d|n and 1<=d<=cap
    local n=$1 cap=$2 d
    (( cap < 1 )) && cap=1
    (( cap > n )) && cap=$n
    for (( d=cap; d>=1; d-- )); do (( n % d == 0 )) && { echo "$d"; return; }; done
    echo 1
}
# npool must ALSO be <= the number of IRREDUCIBLE k-points, or pw.x aborts with
# "npool must be <= nk".  High-symmetry cells have FEW: pristine TiO2/SnO2 are
# 2x2x1 rutile (tetragonal 4/mmm) whose 3x3x6 relax mesh reduces to only ~10-12
# irr-k (cf. 35 for the 4x4x8 prod mesh), vs 16 for the vacancy-broken SnO2
# supercells.  The old cap (nproc/8) grows with node size and blows past that
# floor on any decent node (e.g. 30 pools on 245 cores) -> abort.  NPOOL_MAX=8
# stays under the ~10 irr-k floor on EVERY system here while still parallelising
# k-points well and keeping ranks/pool (<=MAX_RANKS/8=32) under the FFT-plane
# count.  Raise it only if all systems use denser meshes, or pin NK_PW/NK_BANDS.
NPOOL_MAX=${NPOOL_MAX:-8}
_pw_cap=$(( MPI_NPROC / 8 ));  (( _pw_cap > NPOOL_MAX )) && _pw_cap=$NPOOL_MAX
_bd_cap=$(( MPI_NPROC / 16 )); (( _bd_cap > NPOOL_MAX )) && _bd_cap=$NPOOL_MAX
NK_PW=${NK_PW:-$(largest_divisor_leq "$MPI_NPROC" "$_pw_cap")}
NK_BANDS=${NK_BANDS:-$(largest_divisor_leq "$MPI_NPROC" "$_bd_cap")}

# Post-processing rank cap: dos.x/projwfc.x/epsilon.x/pp.x call read_file_new_
# using slab decomp BEFORE -pd .true. takes effect.  If MPI ranks > smooth-grid
# Nz (= 30 for this system's 90x90x30 mesh), ranks with no z-planes get null
# array slices -> SIGBUS in read_file_new_.  Cap at POST_MAX_RANKS (default 16).
POST_MAX_RANKS=${POST_MAX_RANKS:-$(( MPI_NPROC < 16 ? MPI_NPROC : 16 ))}
MPI_POST="${MPI_LAUNCH} -np ${POST_MAX_RANKS}"
[ "${SERIAL}" = "1" ] && MPI_POST=""

# 5) Command assembly
PW_SCF="${MPI} pw.x -nk ${NK_PW}"      # SCF / vc-relax
PW_NSCF="${MPI} pw.x -nk ${NK_PW}"     # NSCF (dense mesh)
PW_BANDS="${MPI} pw.x -nk ${NK_BANDS}" # band path (more ranks/pool for CG FFT)
DOS="${MPI_POST} dos.x -pd .true."
PROJWFC="${MPI_POST} projwfc.x -pd .true."
BANDS="${MPI_POST} bands.x -pd .true."
EPSILON="${MPI_POST} epsilon.x -pd .true."
PP="${MPI_POST} pp.x -pd .true."

# --- NC optical branch config ------------------------------------------------
# epsilon.x supports ONLY norm-conserving pseudos, so the optical step runs its
# own SCF -> NSCF with NC pseudos (from pseudo_nc/) on the relaxed geometry,
# then epsilon.x. Override any of these from the environment if your NC pseudo
# filenames or cutoffs differ.
NC_PSEUDO_DIR_NAME=${NC_PSEUDO_DIR_NAME:-pseudo_nc}   # under ROOT_DIR
NC_MAP=${NC_MAP:-"Sn=Sn.upf,O=O.upf,Ti=Ti.upf"}        # El=file.upf,...
NC_ECUTWFC=${NC_ECUTWFC:-80}                            # Ry; NC needs more than PAW
NC_ECUTRHO=${NC_ECUTRHO:-320}                           # Ry; 4x ecutwfc for NC
NC_GEN="${ROOT_DIR}/make_nc_optical.py"

# Verify the NC pseudos named in NC_MAP exist for the elements this system uses.
# $1 = system input file whose ATOMIC_SPECIES lists the needed elements.
check_nc_pseudos() {
    local probe=$1 missing=0 pdir="${ROOT_DIR}/${NC_PSEUDO_DIR_NAME}"
    local pair el fn
    for pair in ${NC_MAP//,/ }; do
        el=${pair%%=*}; fn=${pair#*=}
        # only require the pseudo if this system actually uses the element
        grep -qiE "^\s*${el}\s+[0-9]" "$probe" 2>/dev/null || continue
        [ -f "${pdir}/${fn}" ] || { warn "missing NC pseudo: ${NC_PSEUDO_DIR_NAME}/${fn} (element ${el})"; missing=1; }
    done
    if [ "$missing" -ne 0 ]; then
        err "Norm-conserving pseudos required for epsilon.x are missing under ${pdir}/."
        err "  epsilon.x cannot use the PAW pseudos. See ${NC_PSEUDO_DIR_NAME}/README.md"
        err "  for where to download them (Pseudo Dojo, PBEsol, SR, standard, UPF)."
        return 1
    fi
    return 0
}

# --- Preflight ---------------------------------------------------------------
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
    if [ "$SERIAL" = "1" ]; then
        info "Resources: SERIAL (no mpirun) | 1 rank | NK_PW=${NK_PW} NK_BANDS=${NK_BANDS}"
    else
        info "Resources: ${MPI_NPROC} MPI ranks × OMP=${OMP_NUM_THREADS} | NK_PW=${NK_PW} ($(( MPI_NPROC / NK_PW )) ranks/pool) | NK_BANDS=${NK_BANDS} ($(( MPI_NPROC / NK_BANDS )) ranks/pool) | POST=${POST_MAX_RANKS}"
    fi
}

# --- Geometry injection ------------------------------------------------------
# Parses relax.out and overwrites CELL_PARAMETERS + ATOMIC_POSITIONS in
# scf/nscf/bands inputs. Aborts the whole run if the bond guard fails.
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

# --- PHASE 1: vc-relax + geometry injection ----------------------------------
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

# --- UNRELAXED: distortion-isolation SCF ------------------------------------
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

# --- Individual post-processing step functions -------------------------------

run_scf() {
    local SYS=$1 PREFIX=$2
    info "[${SYS}] SCF..."
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
    cd "${ROOT_DIR}"
}

run_nscf() {
    local SYS=$1 PREFIX=$2
    info "[${SYS}] NSCF..."
    cd "${ROOT_DIR}/${SYS}/nscf"
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
    cd "${ROOT_DIR}"
}

run_bands() {
    local SYS=$1 PREFIX=$2
    info "[${SYS}] Band structure..."
    cd "${ROOT_DIR}/${SYS}/bands"
    rm -rf tmp 2>/dev/null || true
    ln -sfn ../scf/tmp tmp
    if step_done "${PREFIX}.bands_pp.out"; then
        info "[${SYS}] Bands already done, skipping."
        log_progress "$SYS" "Bands" "SKIPPED (already done)"
    else
        $PW_BANDS -in ${PREFIX}.bands.in    > ${PREFIX}.bands.out    2>&1
        $BANDS    -in ${PREFIX}.bands_pp.in > ${PREFIX}.bands_pp.out 2>&1 \
            && { info "[${SYS}] Bands DONE"; log_progress "$SYS" "Bands" "DONE"; } \
            || { log_progress "$SYS" "Bands" "FAILED"; err "Bands failed for ${SYS}"; exit 1; }
    fi
    cd "${ROOT_DIR}"
}

run_dos() {
    local SYS=$1 PREFIX=$2
    info "[${SYS}] DOS and PDOS..."
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
    cd "${ROOT_DIR}"
}

run_optical() {
    local SYS=$1 PREFIX=$2
    info "[${SYS}] Optical absorption (NC SCF -> NSCF -> epsilon.x)..."
    warn "[${SYS}] If not yet set: check scissor shift in ${SYS}/optical/${PREFIX}.epsilon.in"

    local odir="${ROOT_DIR}/${SYS}/optical"
    local scf_src="${ROOT_DIR}/${SYS}/scf/${PREFIX}.scf.in"
    local nscf_src="${ROOT_DIR}/${SYS}/nscf/${PREFIX}.nscf.in"

    # epsilon.x needs NC pseudos; the PAW scf/nscf .save cannot be reused.
    check_nc_pseudos "$scf_src" || { log_progress "$SYS" "Optical" "FAILED (NC pseudos missing)"; exit 1; }

    cd "${odir}"

    # Regenerate NC inputs from the current (relaxed) scf/nscf so geometry,
    # HUBBARD and k-mesh always stay in sync with the rest of the study.
    "${PYTHON}" "${NC_GEN}" --in "${scf_src}"  --out "${PREFIX}.opt_scf.in" \
        --pseudo-dir "../../${NC_PSEUDO_DIR_NAME}" --map "${NC_MAP}" \
        --ecutwfc "${NC_ECUTWFC}" --ecutrho "${NC_ECUTRHO}" \
        || { err "[${SYS}] NC opt_scf generation failed"; exit 1; }
    "${PYTHON}" "${NC_GEN}" --in "${nscf_src}" --out "${PREFIX}.opt_nscf.in" \
        --pseudo-dir "../../${NC_PSEUDO_DIR_NAME}" --map "${NC_MAP}" \
        --ecutwfc "${NC_ECUTWFC}" --ecutrho "${NC_ECUTRHO}" \
        || { err "[${SYS}] NC opt_nscf generation failed"; exit 1; }

    # Own real tmp for the NC .save (drop any stale symlink to ../nscf/tmp).
    [ -L tmp ] && rm -f tmp
    mkdir -p tmp

    # NC SCF
    if step_done "${PREFIX}.opt_scf.out"; then
        info "[${SYS}] NC optical SCF already done, skipping."
        log_progress "$SYS" "Optical-NCscf" "SKIPPED (already done)"
    else
        $PW_SCF -in ${PREFIX}.opt_scf.in > ${PREFIX}.opt_scf.out 2>&1 \
            && { info "[${SYS}] NC optical SCF DONE"; log_progress "$SYS" "Optical-NCscf" "DONE"; } \
            || { log_progress "$SYS" "Optical-NCscf" "FAILED"; err "NC optical SCF failed for ${SYS}"; exit 1; }
    fi

    # NC NSCF (same tmp; full BZ, tetrahedra_opt, nosym — required by epsilon.x)
    if step_done "${PREFIX}.opt_nscf.out"; then
        info "[${SYS}] NC optical NSCF already done, skipping."
        log_progress "$SYS" "Optical-NCnscf" "SKIPPED (already done)"
    else
        $PW_NSCF -in ${PREFIX}.opt_nscf.in > ${PREFIX}.opt_nscf.out 2>&1 \
            && { info "[${SYS}] NC optical NSCF DONE"; log_progress "$SYS" "Optical-NCnscf" "DONE"; } \
            || { log_progress "$SYS" "Optical-NCnscf" "FAILED"; err "NC optical NSCF failed for ${SYS}"; exit 1; }
    fi

    # epsilon.x (reads NC .save from ./tmp)
    if step_done "${PREFIX}.epsilon.out"; then
        info "[${SYS}] Optical (epsilon.x) already done, skipping."
        log_progress "$SYS" "Optical" "SKIPPED (already done)"
    else
        $EPSILON -in ${PREFIX}.epsilon.in > ${PREFIX}.epsilon.out 2>&1 \
            && { info "[${SYS}] Optical DONE"; log_progress "$SYS" "Optical" "DONE"; } \
            || { log_progress "$SYS" "Optical" "FAILED"; err "epsilon.x failed for ${SYS}"; exit 1; }
    fi
    cd "${ROOT_DIR}"
}

run_pp() {
    local SYS=$1 PREFIX=$2
    info "[${SYS}] Charge density (pp.x)..."
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
}

# --- Full post pipeline: scf → nscf → bands → dos → optical → pp ------------
run_post() {
    local SYS=$1 PREFIX=$2
    run_scf     "$SYS" "$PREFIX"
    run_nscf    "$SYS" "$PREFIX"
    run_bands   "$SYS" "$PREFIX"
    run_dos     "$SYS" "$PREFIX"
    run_optical "$SYS" "$PREFIX"
    run_pp      "$SYS" "$PREFIX"
    info "[${SYS}] All post steps complete."
    log_progress "$SYS" "ALL STEPS" "COMPLETE"
    echo ""
}

# --- System → prefix mapping -------------------------------------------------
prefix_of() {
    case $1 in
        pristine)    echo "SnO2_pristine" ;;
        ratio_1to1)  echo "SnO2_1to1"     ;;
        ratio_2to1)  echo "SnO2_2to1"     ;;
        TiO2)        echo "TiO2_pristine" ;;
        *)           err "Unknown system: $1"; exit 1 ;;
    esac
}
