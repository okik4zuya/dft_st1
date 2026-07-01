#!/bin/bash
# =============================================================================
# run_post.sh — HARDCODED post-processing pipeline (overnight-stable)
# SnO2-x / TiO2 DFT study | Quantum ESPRESSO v7.x
#
# Sequence per system:  scf -> nscf -> bands -> dos -> optical -> pp
#
# Deliberately HARDCODED companion to run_all.sh/run_lib.sh: fixed rank counts
# and npool, no auto-detection.  Numbers live at the top — edit there.
#
# Two modes (safety gate for overnight runs):
#   bash run_post.sh            # CHECK (default): static checks + a LIVE smoke test
#                               #   that actually launches each system's SCF, waits
#                               #   until it proves it is really running, then KILLS
#                               #   it. No output is committed; ./tmp is untouched.
#   bash run_post.sh run        # REAL run: executes the full pipeline.
#
# Overnight, detached (survives logout / dropped SSH):
#   bash run_post.sh            # confirm CHECK is green, then:
#   nohup bash run_post.sh run >/dev/null 2>&1 &
#   tail -f post_*.log
#
# Notes:
#   - PREREQUISITE: each system's vc-relax must be done AND its relaxed geometry
#     injected into scf/nscf/bands inputs BEFORE running post. This does not relax.
#   - Steps already finished ("JOB DONE" in the output) are SKIPPED on a re-run.
#   - Failure isolation: a crash in one system does not abort the others.
# =============================================================================

set -o pipefail   # deliberately NOT `set -e`: survive a failing step/system

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

# --- Hardcoded resources -----------------------------------------------------
# root@ubuntu + OpenMPI: --allow-run-as-root is REQUIRED or mpirun aborts silently.
MPI="mpirun --allow-run-as-root -np 240"     # heavy pw.x steps (scf/nscf/bands-pw)
MPI_POST="mpirun --allow-run-as-root -np 16" # post tools: read_file_new_ SIGBUSes
                                             #   if ranks > smooth-grid Nz (~30)
NK="8"                                        # npool: <= irreducible k-count of EVERY
                                             #   system (tetragonal 3x3x6 ~10-12;
                                             #   vacancy supercells 16+). 240/8=30/pool.
PD="-pd .true."                               # pencil FFT: safe at 30 ranks/pool on
                                             #   these short-c (~3 A) ~30-plane cells
SMOKE_MARKER="Self-consistent Calculation|iteration #"  # pw.x "now really running"
SMOKE_TIMEOUT=180                             # s to wait for the marker before giving up

# NC optical branch (epsilon.x supports ONLY norm-conserving pseudos, not PAW,
# so optical runs its own NC scf->nscf->epsilon on pseudo_nc/).
NC_GEN="${ROOT_DIR}/make_nc_optical.py"
NC_PSEUDO_DIR="../../pseudo_nc"               # relative to <sys>/optical/
NC_MAP="Sn=Sn.upf,O=O.upf,Ti=Ti.upf"
NC_ECUTWFC="80"
NC_ECUTRHO="320"
PYTHON="${PYTHON:-python3}"

# --- Systems (comment out any whose relax+inject is NOT yet complete) --------
SYSTEMS=(
    "pristine:SnO2_pristine"
    "ratio_1to1:SnO2_1to1"
    "ratio_2to1:SnO2_2to1"
    "TiO2:TiO2_pristine"
)

MODE="${1:-check}"
case "$MODE" in
    check|run) ;;
    *) echo "Usage: bash run_post.sh [check|run]"; exit 2 ;;
esac

# --- Logging -----------------------------------------------------------------
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; }

if [ "$MODE" = "run" ]; then
    LOGFILE="${ROOT_DIR}/post_$(date '+%Y%m%d_%H%M%S').log"
    exec > >(tee -a "${LOGFILE}") 2>&1
    info "Master log: ${LOGFILE}"
fi

CHECK_FAIL=0
DONE_STEPS=(); FAIL_STEPS=(); SKIP_STEPS=()
SMOKE_PASS=(); SMOKE_FAIL=()

# --- Process-tree kill (stop a backgrounded mpirun cleanly) ------------------
_kill_tree() {
    local pid=$1 i
    kill "$pid" 2>/dev/null
    for i in 1 2 3 4 5; do kill -0 "$pid" 2>/dev/null || { wait "$pid" 2>/dev/null; return 0; }; sleep 1; done
    kill -9 "$pid" 2>/dev/null
    wait "$pid" 2>/dev/null
    return 0
}

# --- CHECK: live SCF smoke test ---------------------------------------------
# Launch the REAL scf command; if it reaches the SCF loop (proving MPI-as-root,
# pseudo read, npool<=nk and FFT setup all work), stop it and PASS.  Uses a
# scratch outdir via a temp input so the real ./tmp/.save is never touched.
smoke_scf() {
    local SYS=$1 P=$2 d="${ROOT_DIR}/${SYS}/scf"
    local src="${P}.scf.in" tin="${P}.scf.smoke.in" tout="${P}.scf.smoke.out" tdir="./tmp_smoke"
    if [ ! -f "${d}/${src}" ]; then
        err "[SMOKE] ${SYS}/scf: MISSING ${src}"; CHECK_FAIL=1; SMOKE_FAIL+=("${SYS}/scf(no-input)"); return 1
    fi
    # Already completed for real? then it is proven — do not relaunch.
    if [ -f "${d}/${P}.scf.out" ] && grep -q "JOB DONE" "${d}/${P}.scf.out" 2>/dev/null; then
        info "[SMOKE] ${SYS}/scf: already JOB DONE for real -> PASS"; SMOKE_PASS+=("${SYS}/scf(done)"); return 0
    fi

    cd "$d" || { err "[SMOKE] ${SYS}/scf: cannot cd $d"; CHECK_FAIL=1; SMOKE_FAIL+=("${SYS}/scf"); cd "$ROOT_DIR"; return 1; }
    # temp input with a scratch outdir so the real ./tmp is never clobbered
    sed -E "s|^([[:space:]]*outdir[[:space:]]*=).*|\1 '${tdir}'|" "$src" > "$tin"
    mkdir -p "$tdir"

    info "[SMOKE] ${SYS}/scf: launching real pw.x (scratch outdir) — will stop once it's running ..."
    $MPI pw.x -nk $NK $PD -in "$tin" > "$tout" 2>&1 &
    local pid=$! waited=0 ok=0
    while kill -0 "$pid" 2>/dev/null; do
        if grep -qE "$SMOKE_MARKER" "$tout" 2>/dev/null; then ok=1; break; fi
        sleep 3; waited=$((waited+3))
        [ "$waited" -ge "$SMOKE_TIMEOUT" ] && break
    done

    if [ "$ok" -eq 1 ]; then
        info "[SMOKE] ${SYS}/scf: reached SCF loop after ~${waited}s — REALLY RUNS. Stopping it."
        _kill_tree "$pid"
        info "[SMOKE] ${SYS}/scf: PASS"
        SMOKE_PASS+=("${SYS}/scf")
    elif kill -0 "$pid" 2>/dev/null; then
        warn "[SMOKE] ${SYS}/scf: no SCF marker after ${SMOKE_TIMEOUT}s (slow init?) — stopping, INCONCLUSIVE."
        _kill_tree "$pid"
        CHECK_FAIL=1; SMOKE_FAIL+=("${SYS}/scf(timeout)")
    else
        err "[SMOKE] ${SYS}/scf: process EXITED before the SCF loop — real launch error. Last lines:"
        tail -n 20 "$tout" 2>/dev/null | sed 's/^/      | /'
        CHECK_FAIL=1; SMOKE_FAIL+=("${SYS}/scf")
    fi

    rm -rf "$tdir" "$tin" "$tout"   # leave no trace; real pipeline starts fresh
    cd "$ROOT_DIR"
}

# --- CHECK: static input existence ------------------------------------------
check_inputs() {
    local SYS=$1 P=$2 f
    for f in scf/${P}.scf.in nscf/${P}.nscf.in bands/${P}.bands.in bands/${P}.bands_pp.in \
             dos/${P}.dos.in dos/${P}.pdos.in optical/${P}.epsilon.in pp/${P}.pp.in; do
        if [ -f "${ROOT_DIR}/${SYS}/${f}" ]; then info "[CHECK] input OK: ${SYS}/${f}"
        else err "[CHECK] MISSING input: ${SYS}/${f}"; CHECK_FAIL=1; fi
    done
}

# --- CHECK: optical NC-branch dependencies ----------------------------------
check_optical() {
    local SYS=$1 P=$2 pair el fn
    [ -f "$NC_GEN" ] || { err "[${SYS}/optical] missing NC generator: $NC_GEN"; CHECK_FAIL=1; }
    command -v "$PYTHON" >/dev/null 2>&1 || { err "[${SYS}/optical] $PYTHON not on PATH"; CHECK_FAIL=1; }
    for pair in ${NC_MAP//,/ }; do
        el=${pair%%=*}; fn=${pair#*=}
        grep -qiE "^[[:space:]]*${el}[[:space:]]+[0-9]" "${ROOT_DIR}/${SYS}/scf/${P}.scf.in" 2>/dev/null || continue
        [ -f "${ROOT_DIR}/pseudo_nc/${fn}" ] || { err "[${SYS}/optical] missing NC pseudo pseudo_nc/${fn} (${el})"; CHECK_FAIL=1; }
    done
    info "[CHECK] ${SYS}/optical: NC deps checked"
}

# --- RUN: core executor (runs in the MAIN shell so state propagates) ---------
# qe_run <label> <workdir> <infile> <outfile> <cmd...>
qe_run() {
    local label=$1 wd=$2 infile=$3 out=$4; shift 4
    if [ ! -f "${wd}/${infile}" ]; then
        err "[$label] MISSING input: ${wd}/${infile}"; FAIL_STEPS+=("$label"); return 1
    fi
    if [ -f "${wd}/${out}" ] && grep -q "JOB DONE" "${wd}/${out}" 2>/dev/null; then
        info "[SKIP] $label already done"; SKIP_STEPS+=("$label"); return 0
    fi
    info "[$label] starting $(date '+%F %T')"
    cd "$wd" || { err "[$label] cannot cd $wd"; FAIL_STEPS+=("$label"); cd "$ROOT_DIR"; return 1; }
    if "$@" > "$out" 2>&1; then
        info "[$label] DONE $(date '+%F %T')"; DONE_STEPS+=("$label"); cd "$ROOT_DIR"; return 0
    fi
    err "[$label] FAILED — inspect ${wd}/${out}"; FAIL_STEPS+=("$label"); cd "$ROOT_DIR"; return 1
}

link_tmp() { ( cd "$1" && { rm -rf tmp 2>/dev/null; ln -sfn "$2" tmp; } ); }

post_scf() {
    local SYS=$1 P=$2 d="${ROOT_DIR}/${SYS}/scf"
    mkdir -p "${d}/tmp"
    qe_run "${SYS}/scf" "$d" "${P}.scf.in" "${P}.scf.out" $MPI pw.x -nk $NK $PD -in "${P}.scf.in"
}
post_nscf() {
    local SYS=$1 P=$2 d="${ROOT_DIR}/${SYS}/nscf"
    link_tmp "$d" "../scf/tmp"
    qe_run "${SYS}/nscf" "$d" "${P}.nscf.in" "${P}.nscf.out" $MPI pw.x -nk $NK $PD -in "${P}.nscf.in"
}
post_bands() {
    local SYS=$1 P=$2 d="${ROOT_DIR}/${SYS}/bands"
    link_tmp "$d" "../scf/tmp"
    qe_run "${SYS}/bands-pw" "$d" "${P}.bands.in" "${P}.bands.out" $MPI pw.x -nk $NK $PD -in "${P}.bands.in" \
      && qe_run "${SYS}/bands-pp" "$d" "${P}.bands_pp.in" "${P}.bands_pp.out" $MPI_POST bands.x $PD -in "${P}.bands_pp.in"
}
post_dos() {
    local SYS=$1 P=$2 d="${ROOT_DIR}/${SYS}/dos"
    link_tmp "$d" "../nscf/tmp"
    qe_run "${SYS}/dos" "$d" "${P}.dos.in" "${P}.dos.out" $MPI_POST dos.x $PD -in "${P}.dos.in" \
      && qe_run "${SYS}/pdos" "$d" "${P}.pdos.in" "${P}.pdos.out" $MPI_POST projwfc.x $PD -in "${P}.pdos.in"
}
post_optical() {
    local SYS=$1 P=$2 d="${ROOT_DIR}/${SYS}/optical"
    info "[${SYS}/optical] generating NC inputs + running scf->nscf->epsilon"
    cd "$d" || { err "[${SYS}/optical] cannot cd $d"; FAIL_STEPS+=("${SYS}/optical"); cd "$ROOT_DIR"; return 1; }
    if ! "$PYTHON" "$NC_GEN" --in "../scf/${P}.scf.in"  --out "${P}.opt_scf.in" \
            --pseudo-dir "$NC_PSEUDO_DIR" --map "$NC_MAP" --ecutwfc "$NC_ECUTWFC" --ecutrho "$NC_ECUTRHO" \
       || ! "$PYTHON" "$NC_GEN" --in "../nscf/${P}.nscf.in" --out "${P}.opt_nscf.in" \
            --pseudo-dir "$NC_PSEUDO_DIR" --map "$NC_MAP" --ecutwfc "$NC_ECUTWFC" --ecutrho "$NC_ECUTRHO"; then
        err "[${SYS}/optical] NC input generation failed"; FAIL_STEPS+=("${SYS}/optical"); cd "$ROOT_DIR"; return 1
    fi
    [ -L tmp ] && rm -f tmp        # NC .save needs a REAL tmp, not the PAW symlink
    mkdir -p tmp
    cd "$ROOT_DIR"
    qe_run "${SYS}/opt_scf"  "$d" "${P}.opt_scf.in"  "${P}.opt_scf.out"  $MPI pw.x -nk $NK $PD -in "${P}.opt_scf.in" \
      && qe_run "${SYS}/opt_nscf" "$d" "${P}.opt_nscf.in" "${P}.opt_nscf.out" $MPI pw.x -nk $NK $PD -in "${P}.opt_nscf.in" \
      && qe_run "${SYS}/epsilon"  "$d" "${P}.epsilon.in"  "${P}.epsilon.out"  $MPI_POST epsilon.x $PD -in "${P}.epsilon.in"
}
post_pp() {
    local SYS=$1 P=$2 d="${ROOT_DIR}/${SYS}/pp"
    link_tmp "$d" "../scf/tmp"
    qe_run "${SYS}/pp" "$d" "${P}.pp.in" "${P}.pp.out" $MPI_POST pp.x $PD -in "${P}.pp.in"
}

# --- Global preflight (both modes): tools + pseudos --------------------------
info "========================================================"
info "  run_post.sh  |  MODE=${MODE}  |  $(date '+%F %T')"
info "  pw.x ranks: ${MPI##*-np } | post ranks: ${MPI_POST##*-np } | npool: ${NK}"
info "========================================================"

for tool in mpirun pw.x dos.x projwfc.x bands.x epsilon.x pp.x; do
    command -v "$tool" >/dev/null 2>&1 && info "[CHECK] found: $tool" \
        || { err "[CHECK] MISSING on PATH: $tool"; CHECK_FAIL=1; }
done
for pp in pseudo/Sn.pbesol-dn-kjpaw_psl.1.0.0.UPF pseudo/O.pbesol-n-kjpaw_psl.1.0.0.UPF \
          pseudo/Ti.pbesol-spn-kjpaw_psl.1.0.0.UPF; do
    [ -f "${ROOT_DIR}/$pp" ] && info "[CHECK] found: $pp" || { err "[CHECK] MISSING: $pp"; CHECK_FAIL=1; }
done

# =============================================================================
if [ "$MODE" = "check" ]; then
    # NOTE: no standalone 'pw.x --version' probe — QE's pw.x has no reliable
    # early-exit flag, so an unrecognized arg makes it block reading stdin.
    # The per-system smoke_scf below launches pw.x with '-in <file>' (never
    # stdin), backgrounded with a timeout+kill, and validates MPI-as-root there.
    for entry in "${SYSTEMS[@]}"; do
        SYS="${entry%%:*}"; PREFIX="${entry##*:}"
        info "--------------------------------------------------------"
        info "  CHECK system: ${SYS}  (prefix ${PREFIX})"
        info "--------------------------------------------------------"
        check_inputs  "$SYS" "$PREFIX"
        check_optical "$SYS" "$PREFIX"
        smoke_scf     "$SYS" "$PREFIX"   # LIVE: launch real SCF, confirm it runs, kill it
    done

    echo ""
    info "========================================================"
    info "  SMOKE PASS: ${#SMOKE_PASS[@]}  ${SMOKE_PASS[*]:-none}"
    [ ${#SMOKE_FAIL[@]} -gt 0 ] && err "  SMOKE FAIL: ${#SMOKE_FAIL[@]}  ${SMOKE_FAIL[*]}"
    if [ "$CHECK_FAIL" -eq 0 ]; then
        info "  CHECK PASSED — tools/pseudos/inputs present and every SCF really launches."
        info "  Note: nscf/bands/dos/optical/pp reuse the SAME mpirun/pw.x/npool proven"
        info "        here; they cannot be launched standalone (need the upstream .save)."
        info "  Start the real run:   nohup bash run_post.sh run >/dev/null 2>&1 &"
    else
        err "  CHECK FAILED — fix the items above before running."
        info "========================================================"; exit 1
    fi
    info "========================================================"; exit 0
fi

# =============================================================================
# REAL RUN
for entry in "${SYSTEMS[@]}"; do
    SYS="${entry%%:*}"; PREFIX="${entry##*:}"
    info "--------------------------------------------------------"
    info "  System: ${SYS}  (prefix ${PREFIX})"
    info "--------------------------------------------------------"
    if ! post_scf "$SYS" "$PREFIX"; then
        err "[${SYS}] SCF failed — skipping remaining steps for this system."; continue
    fi
    post_nscf    "$SYS" "$PREFIX"
    post_bands   "$SYS" "$PREFIX"
    post_dos     "$SYS" "$PREFIX"
    post_optical "$SYS" "$PREFIX"
    post_pp      "$SYS" "$PREFIX"
done

echo ""
info "========================================================"
info "  POST RUN COMPLETE ($(date '+%F %T'))"
info "  done   : ${#DONE_STEPS[@]}  ${DONE_STEPS[*]:-}"
[ ${#SKIP_STEPS[@]} -gt 0 ] && warn "  skipped: ${#SKIP_STEPS[@]}  ${SKIP_STEPS[*]}"
if [ ${#FAIL_STEPS[@]} -gt 0 ]; then
    err "  FAILED : ${#FAIL_STEPS[@]}  ${FAIL_STEPS[*]}"
    info "========================================================"; exit 1
fi
info "========================================================"; exit 0
