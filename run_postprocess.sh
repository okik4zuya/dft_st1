#!/bin/bash
# =============================================================================
# run_postprocess.sh — figure pipeline for the SnO2-x / TiO2 study
#
# Produces manuscript figures 1, 2 and 5 from the QE outputs, wiring the data
# flow automatically (no manual copy-paste of alignment values):
#
#   1. extract_dft_values.py   ->  dft_values.json        (VBM/CBM/Fermi/O2s)
#   2. band_alignment.py       ->  band_alignment.json    (core shift, aligned
#                                   + energy_diagram.png    VBM/CBM, mechanism)
#   3. postprocess/run_figures.py --fig 1 2 5
#          fig1  bands + PDOS (1:1, 2:1)      <- QE bands.dat + pdos directly
#          fig2  stacked PDOS, all 4 systems  <- pdos + core shift (step 2)
#          fig5  band-alignment diagram       <- aligned VBM/CBM (step 2)
#
# Figures 3 (delta-rho / pp) and 4 (optical / epsilon) are intentionally NOT
# built here — those calculations are deferred (see run_post.sh STOP_AFTER=pdos).
#
# Usage:
#   bash run_postprocess.sh                 # figs 1 2 5 (default)
#   FIGS="1 2 5" bash run_postprocess.sh    # explicit figure selection
#   FIGS="2"     bash run_postprocess.sh    # a single figure
#
# Prerequisites: python3 with numpy, matplotlib, scipy.
# Robustness: each stage is non-fatal — a failing extract/align still lets the
# figures render (fig1 reads QE directly; fig2/fig5 fall back to Fermi-ref/demo).
# =============================================================================

set -o pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

PYTHON="${PYTHON:-python3}"
FIGS="${FIGS:-1 2 5}"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; }

LOGFILE="${ROOT_DIR}/figures_$(date '+%Y%m%d_%H%M%S').log"
exec > >(tee -a "${LOGFILE}") 2>&1

info "========================================================"
info "  run_postprocess.sh  |  $(date '+%F %T')"
info "  figures: ${FIGS}  |  python: ${PYTHON}  |  log: ${LOGFILE##*/}"
info "========================================================"

# --- dependency preflight ----------------------------------------------------
command -v "$PYTHON" >/dev/null 2>&1 || { err "python not on PATH: $PYTHON"; exit 1; }
if ! "$PYTHON" - <<'PY'
import importlib, sys
missing = [m for m in ("numpy", "matplotlib") if importlib.util.find_spec(m) is None]
if missing:
    print("MISSING:" + ",".join(missing)); sys.exit(1)
import numpy, matplotlib
print(f"numpy {numpy.__version__} | matplotlib {matplotlib.__version__}")
PY
then
    err "Missing python deps. Run: pip install numpy matplotlib scipy"; exit 1
fi

FAIL=()

# --- Stage 1: extract DFT values (VBM/CBM/Fermi/O2s -> dft_values.json) -------
info "--------------------------------------------------------"
info "  [1/3] extract_dft_values.py"
info "--------------------------------------------------------"
if "$PYTHON" extract_dft_values.py; then
    info "extract OK -> dft_values.json"
else
    warn "extract_dft_values.py failed — fig2/fig5 may fall back to Fermi-ref/demo."
    FAIL+=("extract")
fi

# --- Stage 2: band alignment (core shift + aligned VBM -> band_alignment.json)
info "--------------------------------------------------------"
info "  [2/3] band_alignment.py"
info "--------------------------------------------------------"
if [ -f dft_values.json ]; then
    if "$PYTHON" band_alignment.py; then
        info "alignment OK -> band_alignment.json + energy_diagram.png"
    else
        warn "band_alignment.py failed — fig2 uses CORE_SHIFT=0, fig5 uses DEMO."
        FAIL+=("band_alignment")
    fi
else
    warn "dft_values.json absent — skipping band_alignment; fig2/fig5 not aligned."
    FAIL+=("band_alignment(no-input)")
fi

# --- Stage 3: figures --------------------------------------------------------
info "--------------------------------------------------------"
info "  [3/3] run_figures.py --fig ${FIGS}"
info "--------------------------------------------------------"
if "$PYTHON" postprocess/run_figures.py --fig ${FIGS}; then
    info "figures OK"
else
    err "run_figures.py reported a failure — inspect output above."
    FAIL+=("figures")
fi

echo ""
info "========================================================"
info "  POSTPROCESS COMPLETE ($(date '+%F %T'))"
info "  Outputs in postprocess/:"
for n in ${FIGS}; do
    f="postprocess/fig${n}"*.png
    ls $f >/dev/null 2>&1 && info "    $(ls $f 2>/dev/null | tr '\n' ' ')" \
        || warn "    fig${n}: no PNG produced"
done
[ -f energy_diagram.png ] && info "  energy_diagram.png (band_alignment.py)"
if [ ${#FAIL[@]} -gt 0 ]; then
    warn "  degraded stages: ${FAIL[*]}"
    info "========================================================"; exit 1
fi
info "========================================================"; exit 0
