#!/usr/bin/env bash
# r2_sync.sh — Cloudflare R2 checkpoint helper for Quantum ESPRESSO simulations
set -euo pipefail

# ─── Paths ─────────────────────────────────────────────────────────────────────
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ROOT_DIR}/.r2env"

# ─── Systems — must match run_all.sh ──────────────────────────────────────────
SYSTEMS=("pristine" "ratio_1to1" "ratio_2to1" "TiO2")

prefix_of() {
    case "$1" in
        pristine)   echo "SnO2_pristine" ;;
        ratio_1to1) echo "SnO2_1to1"     ;;
        ratio_2to1) echo "SnO2_2to1"     ;;
        TiO2)       echo "TiO2_pristine" ;;
        *)          echo "$1"            ;;
    esac
}

# ─── Logging ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${GREEN}[INFO]${NC}  $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $1"; }
err()     { echo -e "${RED}[ERROR]${NC} $1" >&2; }
section() { echo -e "\n${CYAN}══ $1 ══${NC}"; }

# ─── Credential loading ────────────────────────────────────────────────────────
load_env() {
    if [ -f "$ENV_FILE" ]; then source "$ENV_FILE"; fi
    : "${R2_ACCOUNT_ID:?'.r2env missing R2_ACCOUNT_ID — run: bash r2_sync.sh setup'}"
    : "${R2_ACCESS_KEY_ID:?'.r2env missing R2_ACCESS_KEY_ID'}"
    : "${R2_SECRET_ACCESS_KEY:?'.r2env missing R2_SECRET_ACCESS_KEY'}"
    : "${R2_BUCKET:?'.r2env missing R2_BUCKET'}"
    R2_PREFIX="${R2_PREFIX:-QE}"
}

# ─── Configure rclone via env vars (no global rclone.conf touched) ─────────────
setup_remote() {
    export RCLONE_CONFIG_R2QE_TYPE=s3
    export RCLONE_CONFIG_R2QE_PROVIDER=Cloudflare
    export RCLONE_CONFIG_R2QE_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID"
    export RCLONE_CONFIG_R2QE_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY"
    export RCLONE_CONFIG_R2QE_ENDPOINT="https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    export RCLONE_CONFIG_R2QE_ACL=private
}

check_rclone() {
    if ! command -v rclone >/dev/null 2>&1; then
        err "rclone not found. Install with:"
        err "  curl https://rclone.org/install.sh | sudo bash"
        exit 1
    fi
}

# ─── cmd: setup ───────────────────────────────────────────────────────────────
cmd_setup() {
    section "R2 Credential Setup"
    echo "Credentials will be saved to: ${ENV_FILE}"
    echo ""
    if [ -f "$ENV_FILE" ]; then source "$ENV_FILE" 2>/dev/null || true; fi

    local _in
    read -rp  "R2 Account ID        [${R2_ACCOUNT_ID:-}]: "     _in
    [ -n "$_in" ] && R2_ACCOUNT_ID="$_in"
    read -rp  "R2 Access Key ID     [${R2_ACCESS_KEY_ID:-}]: "   _in
    [ -n "$_in" ] && R2_ACCESS_KEY_ID="$_in"
    read -rsp "R2 Secret Access Key [hidden]: "                  _in; echo ""
    [ -n "$_in" ] && R2_SECRET_ACCESS_KEY="$_in"
    read -rp  "R2 Bucket name       [${R2_BUCKET:-qe-simulations}]: " _in
    R2_BUCKET="${_in:-${R2_BUCKET:-qe-simulations}}"
    read -rp  "R2 Prefix (folder)   [${R2_PREFIX:-QE}]: "        _in
    R2_PREFIX="${_in:-${R2_PREFIX:-QE}}"

    cat > "$ENV_FILE" <<EOF
R2_ACCOUNT_ID=${R2_ACCOUNT_ID}
R2_ACCESS_KEY_ID=${R2_ACCESS_KEY_ID}
R2_SECRET_ACCESS_KEY=${R2_SECRET_ACCESS_KEY}
R2_BUCKET=${R2_BUCKET}
R2_PREFIX=${R2_PREFIX}
EOF
    chmod 600 "$ENV_FILE"
    info "Credentials saved to ${ENV_FILE}"

    check_rclone
    setup_remote
    info "Testing connection to r2qe:${R2_BUCKET} ..."
    if rclone lsd "r2qe:${R2_BUCKET}" >/dev/null 2>&1; then
        info "Connection OK — bucket is accessible."
    else
        err "Connection failed. Check Account ID, keys, and bucket name."
        exit 1
    fi
}

# ─── Upload helpers ────────────────────────────────────────────────────────────
upload_one() {
    local sys="$1"
    if [ ! -d "${ROOT_DIR}/${sys}" ]; then
        warn "Directory not found: ${sys}/ — skipping."
        return
    fi
    info "Uploading ${sys}/ → r2qe:${R2_BUCKET}/${R2_PREFIX}/${sys}"
    rclone copy "${ROOT_DIR}/${sys}" "r2qe:${R2_BUCKET}/${R2_PREFIX}/${sys}" \
        --exclude "relax/tmp/**"   \
        --exclude "__pycache__/**" \
        --exclude "*.pyc"          \
        --exclude "*.swp"          \
        --transfers 8              \
        --progress
    info "${sys}: upload done."
}

cmd_upload() {
    check_rclone; load_env; setup_remote
    local target="${1:-all}"
    if [ "$target" = "all" ]; then
        for sys in "${SYSTEMS[@]}"; do upload_one "$sys"; done
    else
        local valid=0
        for sys in "${SYSTEMS[@]}"; do [ "$sys" = "$target" ] && valid=1 && break; done
        [ "$valid" -eq 1 ] || { err "Unknown system '${target}'. Valid: ${SYSTEMS[*]}"; exit 1; }
        upload_one "$target"
    fi
    info "Upload complete."
}

# ─── Download helpers ──────────────────────────────────────────────────────────
recreate_symlinks() {
    local sys="$1"
    local base="${ROOT_DIR}/${sys}"
    if [ ! -d "${base}/scf/tmp" ]; then return 0; fi
    for step in nscf bands optical pp; do
        if [ -d "${base}/${step}" ]; then
            rm -f "${base}/${step}/tmp"
            ln -sfn ../scf/tmp "${base}/${step}/tmp"
        fi
    done
    if [ -d "${base}/dos" ]; then
        rm -f "${base}/dos/tmp"
        ln -sfn ../nscf/tmp "${base}/dos/tmp"
    fi
    info "${sys}: tmp/ symlinks recreated."
}

download_one() {
    local sys="$1"
    info "Downloading r2qe:${R2_BUCKET}/${R2_PREFIX}/${sys} → ${sys}/"
    rclone copy "r2qe:${R2_BUCKET}/${R2_PREFIX}/${sys}" "${ROOT_DIR}/${sys}" \
        --transfers 8 \
        --progress
    recreate_symlinks "$sys"
}

cmd_download() {
    check_rclone; load_env; setup_remote
    local target="${1:-all}"
    if [ "$target" = "all" ]; then
        for sys in "${SYSTEMS[@]}"; do download_one "$sys"; done
        local n=0
        n=$(ls "${ROOT_DIR}/pseudo/"*.UPF 2>/dev/null | wc -l | tr -d '[:space:]') || n=0
        if [ "${n}" -eq 0 ]; then
            warn "pseudo/*.UPF not found locally. Run: bash r2_sync.sh pull-pseudo"
        fi
    else
        local valid=0
        for sys in "${SYSTEMS[@]}"; do [ "$sys" = "$target" ] && valid=1 && break; done
        [ "$valid" -eq 1 ] || { err "Unknown system '${target}'. Valid: ${SYSTEMS[*]}"; exit 1; }
        download_one "$target"
    fi
    info "Download complete. Resume simulation with: bash run_all.sh post"
}

# ─── cmd: status ──────────────────────────────────────────────────────────────
cmd_status() {
    check_rclone; load_env; setup_remote
    section "Simulation Checkpoint Status"
    printf "%-14s %-14s %-12s %s\n" "System" "Step" "Local" "R2"
    printf "%-14s %-14s %-12s %s\n" "--------------" "--------------" "------------" "----------"

    for sys in "${SYSTEMS[@]}"; do
        local pfx
        pfx=$(prefix_of "$sys")
        for step in relax scf nscf bands dos optical pp; do
            local stepdir="${ROOT_DIR}/${sys}/${step}"
            if [ ! -d "$stepdir" ]; then continue; fi

            local outfile="${stepdir}/${pfx}.${step}.out"

            local local_label local_color
            if [ -f "$outfile" ] && grep -q "JOB DONE" "$outfile" 2>/dev/null; then
                local_label="DONE";     local_color="$GREEN"
            elif [ -f "$outfile" ]; then
                local_label="RUNNING?"; local_color="$YELLOW"
            else
                local_label="PENDING";  local_color="$NC"
            fi

            local r2_count r2_label r2_color
            r2_count=$(rclone ls "r2qe:${R2_BUCKET}/${R2_PREFIX}/${sys}/${step}/" 2>/dev/null \
                       | wc -l || echo 0)
            if [ "${r2_count:-0}" -gt 0 ]; then
                r2_label="YES"; r2_color="$GREEN"
            else
                r2_label="NO";  r2_color="$NC"
            fi

            printf "%-14s %-14s " "$sys" "$step"
            printf "${local_color}%-12s${NC} ${r2_color}%s${NC}\n" "$local_label" "$r2_label"
        done
    done
}

# ─── cmd: push-pseudo / pull-pseudo ───────────────────────────────────────────
cmd_push_pseudo() {
    check_rclone; load_env; setup_remote
    info "Uploading pseudo/ → r2qe:${R2_BUCKET}/${R2_PREFIX}/pseudo"
    rclone copy "${ROOT_DIR}/pseudo" "r2qe:${R2_BUCKET}/${R2_PREFIX}/pseudo" --progress
    info "push-pseudo done."
}

cmd_pull_pseudo() {
    check_rclone; load_env; setup_remote
    info "Downloading r2qe:${R2_BUCKET}/${R2_PREFIX}/pseudo → pseudo/"
    rclone copy "r2qe:${R2_BUCKET}/${R2_PREFIX}/pseudo" "${ROOT_DIR}/pseudo" --progress
    info "pull-pseudo done."
}

# ─── Usage ────────────────────────────────────────────────────────────────────
usage() {
    cat <<'USAGE'

Usage: bash r2_sync.sh <command> [system]

Commands:
  setup                 Save R2 credentials to .r2env and test connection
  upload  [sys|all]     Upload completed simulation work to R2  (default: all)
  download [sys|all]    Restore from R2 and recreate tmp/ symlinks
  status                Show local DONE/PENDING vs R2 YES/NO for each step
  push-pseudo           Upload pseudo/*.UPF to R2  (run once per bucket)
  pull-pseudo           Download pseudo/*.UPF from R2  (run on new pod)

Systems: pristine  ratio_1to1  ratio_2to1  TiO2

Typical workflow — current pod:
  bash r2_sync.sh setup          # first time only
  bash r2_sync.sh push-pseudo    # first time only
  bash run_all.sh relax
  bash r2_sync.sh upload         # checkpoint after relax phase
  bash run_all.sh post
  bash r2_sync.sh upload         # final checkpoint

On a new pod:
  bash r2_sync.sh setup
  bash r2_sync.sh pull-pseudo
  bash r2_sync.sh download
  bash run_all.sh post           # resumes from checkpoint

Override without editing .r2env:
  R2_BUCKET=other-bucket bash r2_sync.sh status
  bash r2_sync.sh upload pristine

USAGE
}

# ─── Main ─────────────────────────────────────────────────────────────────────
main() {
    local cmd="${1:-help}"
    shift || true
    case "$cmd" in
        setup)          cmd_setup            ;;
        upload)         cmd_upload   "$@"    ;;
        download)       cmd_download "$@"    ;;
        status)         cmd_status           ;;
        push-pseudo)    cmd_push_pseudo      ;;
        pull-pseudo)    cmd_pull_pseudo      ;;
        help|-h|--help) usage                ;;
        *) err "Unknown command: ${cmd}"; usage; exit 1 ;;
    esac
}

main "$@"
