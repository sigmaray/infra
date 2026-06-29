#!/usr/bin/env bash
# Bootstrap a fresh Ubuntu VPS: install git & Docker, deploy shared PostgreSQL, start via Compose.
#
# Usage (on VPS as root):
#   curl -fsSL https://raw.githubusercontent.com/sigmaray/flask-weather/main/docs/example-postgresql-docker-compose/scripts/setup-vps.sh | bash
#   # or
#   sudo bash docs/example-postgresql-docker-compose/scripts/setup-vps.sh
#   sudo bash docs/example-postgresql-docker-compose/scripts/setup-vps.sh --swap
#
# Environment variables:
#   DEPLOY_DIR                  Target directory (default: ~/r/d/postgresql)
#   REPO_URL                    Git clone URL (default: https://github.com/sigmaray/flask-weather.git)
#   GIT_REF                     Branch, tag, or commit to deploy (default: main)
#   REPO_SUBPATH                Path inside the repo to sync (default: docs/example-postgresql-docker-compose)
#   REPO_CACHE_DIR              Full-repo clone cache (default: DEPLOY_DIR/.repo-cache)
#   POSTGRES_USER               PostgreSQL user (default: postgres)
#   POSTGRES_PASSWORD           PostgreSQL password (default: auto-generated and saved in DEPLOY_DIR/.env)
#   POSTGRES_PORT               Host port (default: 5432)
#   SETUP_SKIP_APT              Set to 1 to skip apt-get (useful in CI where git is preinstalled)
#   SETUP_SKIP_DOCKER_INSTALL   Set to 1 to skip Docker installation (useful in CI)
#   SETUP_SOURCE_DIR            Copy compose tree from this path instead of cloning (CI / local test)
#   SETUP_ALLOW_NON_ROOT        Set to 1 to skip root check (CI with passwordless sudo)
#   SETUP_FORCE                 Set to 1 to redeploy even when already at GIT_REF and running
#   SETUP_SWAP                  Set to 1 to configure swap (same as --swap)
#   SETUP_SWAP_SIZE_MB          Swap file size in megabytes (default: 2048)
#   SETUP_SWAP_FILE             Swap file path (default: /swapfile)
#   PG_READY_TIMEOUT_SEC        Seconds to wait for PostgreSQL (default: 120)

set -euo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-${HOME}/r/d/postgresql}"
REPO_URL="${REPO_URL:-https://github.com/sigmaray/flask-weather.git}"
GIT_REF="${GIT_REF:-main}"
REPO_SUBPATH="${REPO_SUBPATH:-docs/example-postgresql-docker-compose}"
REPO_CACHE_DIR="${REPO_CACHE_DIR:-${DEPLOY_DIR}/.repo-cache}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
SETUP_SKIP_APT="${SETUP_SKIP_APT:-0}"
SETUP_SKIP_DOCKER_INSTALL="${SETUP_SKIP_DOCKER_INSTALL:-0}"
SETUP_SOURCE_DIR="${SETUP_SOURCE_DIR:-}"
SETUP_ALLOW_NON_ROOT="${SETUP_ALLOW_NON_ROOT:-0}"
SETUP_FORCE="${SETUP_FORCE:-0}"
SETUP_SWAP="${SETUP_SWAP:-0}"
SETUP_SWAP_SIZE_MB="${SETUP_SWAP_SIZE_MB:-2048}"
SETUP_SWAP_FILE="${SETUP_SWAP_FILE:-/swapfile}"
PG_READY_TIMEOUT_SEC="${PG_READY_TIMEOUT_SEC:-120}"

DEPLOY_ENV_FILE="${DEPLOY_DIR}/.env"

log() {
  printf '[setup-postgresql] %s\n' "$*" >&2
}

die() {
  printf '[setup-postgresql] ERROR: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'EOF'
Usage: setup-vps.sh [--swap]

Bootstrap Ubuntu, install git and Docker, deploy shared PostgreSQL, and start docker compose.

Options:
  --swap                      Create and enable a swap file if swap is not configured

Environment variables:
  DEPLOY_DIR                  Deployment directory (default: ~/r/d/postgresql)
  REPO_URL                    Git repository URL
  GIT_REF                     Branch, tag, or commit (default: main)
  REPO_SUBPATH                Subdirectory inside the repo to deploy
  REPO_CACHE_DIR              Local cache for the full git clone
  POSTGRES_USER               PostgreSQL user (default: postgres)
  POSTGRES_PASSWORD           PostgreSQL password (saved to DEPLOY_DIR/.env when unset)
  POSTGRES_PORT               Host port (default: 5432)
  SETUP_SKIP_APT              Skip apt-get when set to 1
  SETUP_SKIP_DOCKER_INSTALL   Skip Docker install when set to 1
  SETUP_SOURCE_DIR            Use existing directory instead of git clone
  SETUP_ALLOW_NON_ROOT        Allow running without root (for CI)
  SETUP_FORCE                 Redeploy even when already at GIT_REF and running
  SETUP_SWAP                  Configure swap when set to 1 (same as --swap)
  SETUP_SWAP_SIZE_MB          Swap file size in megabytes (default: 2048)
  SETUP_SWAP_FILE             Swap file path (default: /swapfile)
  PG_READY_TIMEOUT_SEC        PostgreSQL readiness timeout in seconds
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h|--help)
        usage
        exit 0
        ;;
      --swap)
        SETUP_SWAP=1
        shift
        ;;
      *)
        die "Unknown option: $1 (try --help)"
        ;;
    esac
  done
}

require_root() {
  if [[ "${SETUP_ALLOW_NON_ROOT}" == "1" ]]; then
    return 0
  fi
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    die "Run as root: sudo bash $0"
  fi
}

read_env_value() {
  local key="$1"
  local file="$2"
  [[ -f "${file}" ]] || return 1
  grep -E "^${key}=" "${file}" | tail -1 | cut -d= -f2-
}

ensure_deploy_env() {
  [[ -d "${DEPLOY_DIR}" ]] || die "Deploy directory missing: ${DEPLOY_DIR}"

  local existing_password=""
  existing_password="$(read_env_value POSTGRES_PASSWORD "${DEPLOY_ENV_FILE}" 2>/dev/null || true)"

  if [[ -z "${POSTGRES_PASSWORD:-}" ]]; then
    if [[ -n "${existing_password}" ]]; then
      POSTGRES_PASSWORD="${existing_password}"
      log "Using POSTGRES_PASSWORD from ${DEPLOY_ENV_FILE}"
    elif command -v openssl >/dev/null 2>&1; then
      POSTGRES_PASSWORD="$(openssl rand -base64 24)"
      log "Generated new POSTGRES_PASSWORD"
    else
      die "POSTGRES_PASSWORD is unset and openssl is not available to generate one"
    fi
  fi
  export POSTGRES_PASSWORD

  local existing_user=""
  existing_user="$(read_env_value POSTGRES_USER "${DEPLOY_ENV_FILE}" 2>/dev/null || true)"
  if [[ -n "${existing_user}" ]] && [[ -z "${POSTGRES_USER:-}" || "${POSTGRES_USER}" == "postgres" ]]; then
    POSTGRES_USER="${existing_user}"
  fi

  local existing_port=""
  existing_port="$(read_env_value POSTGRES_PORT "${DEPLOY_ENV_FILE}" 2>/dev/null || true)"
  if [[ -n "${existing_port}" ]] && [[ "${POSTGRES_PORT}" == "5432" ]]; then
    POSTGRES_PORT="${existing_port}"
  fi

  local tmp
  tmp="$(mktemp)"
  chmod 600 "${tmp}"
  {
    printf 'POSTGRES_USER=%s\n' "${POSTGRES_USER}"
    printf 'POSTGRES_PASSWORD=%s\n' "${POSTGRES_PASSWORD}"
    printf 'POSTGRES_PORT=%s\n' "${POSTGRES_PORT}"
  } > "${tmp}"
  mv "${tmp}" "${DEPLOY_ENV_FILE}"
  chmod 600 "${DEPLOY_ENV_FILE}"
  log "Wrote ${DEPLOY_ENV_FILE}"
}

install_packages() {
  if [[ "${SETUP_SKIP_APT}" == "1" ]]; then
    command -v git >/dev/null 2>&1 || die "git not found (install it or unset SETUP_SKIP_APT)"
    command -v curl >/dev/null 2>&1 || die "curl not found (install it or unset SETUP_SKIP_APT)"
    command -v rsync >/dev/null 2>&1 || die "rsync not found (install it or unset SETUP_SKIP_APT)"
    log "Skipping apt-get (SETUP_SKIP_APT=1)"
    return 0
  fi

  log "Installing git and prerequisites..."
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq git curl ca-certificates openssl rsync
}

install_etckeeper() {
  if [[ "${SETUP_SKIP_APT}" == "1" ]]; then
    return 0
  fi

  if command -v etckeeper >/dev/null 2>&1; then
    log "etckeeper is already installed"
    return 0
  fi

  log "Installing etckeeper..."
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq etckeeper
}

install_docker() {
  if [[ "${SETUP_SKIP_DOCKER_INSTALL}" == "1" ]]; then
    log "Skipping Docker installation (SETUP_SKIP_DOCKER_INSTALL=1)"
    command -v docker >/dev/null 2>&1 || die "docker not found and installation was skipped"
    docker compose version >/dev/null 2>&1 || die "docker compose plugin not found"
    return 0
  fi

  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    log "Docker is already installed"
    return 0
  fi

  log "Installing Docker..."
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker
}

swap_is_configured() {
  local swap_kb
  swap_kb="$(awk '/^SwapTotal:/ {print $2}' /proc/meminfo)"
  [[ "${swap_kb:-0}" -gt 0 ]]
}

ensure_swap_in_fstab() {
  local swap_file="$1"
  if grep -qF "${swap_file}" /etc/fstab 2>/dev/null; then
    return 0
  fi
  echo "${swap_file} none swap sw 0 0" >> /etc/fstab
}

setup_swap() {
  if [[ "${SETUP_SWAP}" != "1" ]]; then
    return 0
  fi

  if swap_is_configured; then
    log "Swap is already configured — skipping"
    swapon --show >&2 || true
    return 0
  fi

  local swap_file="${SETUP_SWAP_FILE}"
  local swap_mb="${SETUP_SWAP_SIZE_MB}"

  log "Configuring ${swap_mb}MB swap at ${swap_file}..."

  if [[ -f "${swap_file}" ]]; then
    log "Swap file ${swap_file} exists — enabling it"
  elif ! fallocate -l "${swap_mb}M" "${swap_file}" 2>/dev/null; then
    log "fallocate failed; creating swap file with dd (this may take a while)..."
    dd if=/dev/zero of="${swap_file}" bs=1M count="${swap_mb}" status=none
  fi

  chmod 600 "${swap_file}"
  mkswap "${swap_file}" >/dev/null
  swapon "${swap_file}"
  ensure_swap_in_fstab "${swap_file}"

  log "Swap enabled:"
  swapon --show >&2 || true
}

RSYNC_OPTS=(-a --delete --exclude '.env' --exclude '.repo-cache')

count_rsync_changes() {
  local source_dir="$1"
  rsync "${RSYNC_OPTS[@]}" --dry-run --itemize-changes "${source_dir}/" "${DEPLOY_DIR}/" \
    | grep -vE '^\.d\.\.t' \
    | grep -c . || true
}

sync_compose_tree() {
  local source_dir="$1"
  mkdir -p "${DEPLOY_DIR}"

  local changes
  changes="$(count_rsync_changes "${source_dir}")"
  if [[ "${changes}" -eq 0 ]]; then
    log "Compose tree already synced to ${DEPLOY_DIR}"
    printf 'current'
    return 0
  fi

  rsync "${RSYNC_OPTS[@]}" "${source_dir}/" "${DEPLOY_DIR}/"
  printf 'sync'
}

fetch_existing_clone() {
  if git -C "${REPO_CACHE_DIR}" fetch --depth 1 origin "${GIT_REF}" 2>/dev/null; then
    return 0
  fi
  git -C "${REPO_CACHE_DIR}" fetch --depth 1 origin "refs/tags/${GIT_REF}:refs/tags/${GIT_REF}"
}

remote_ref_sha() {
  git -C "${REPO_CACHE_DIR}" rev-parse FETCH_HEAD 2>/dev/null \
    || git -C "${REPO_CACHE_DIR}" rev-parse "refs/tags/${GIT_REF}" 2>/dev/null \
    || git -C "${REPO_CACHE_DIR}" rev-parse "origin/${GIT_REF}" 2>/dev/null \
    || git -C "${REPO_CACHE_DIR}" rev-parse "${GIT_REF}"
}

project_worktree_clean() {
  git -C "${REPO_CACHE_DIR}" diff --quiet HEAD \
    && git -C "${REPO_CACHE_DIR}" diff --cached --quiet HEAD
}

reset_existing_clone() {
  local target_sha
  target_sha="$(remote_ref_sha)"
  git -C "${REPO_CACHE_DIR}" checkout --detach "${target_sha}"
  git -C "${REPO_CACHE_DIR}" reset --hard "${target_sha}"
}

clone_repo_cache() {
  mkdir -p "$(dirname "${REPO_CACHE_DIR}")"
  if git clone --branch "${GIT_REF}" --depth 1 "${REPO_URL}" "${REPO_CACHE_DIR}" 2>/dev/null; then
    return 0
  fi

  log "Shallow branch clone failed; fetching ${GIT_REF} by ref..."
  git clone --depth 1 "${REPO_URL}" "${REPO_CACHE_DIR}"
  fetch_existing_clone
  local target_sha
  target_sha="$(remote_ref_sha)"
  git -C "${REPO_CACHE_DIR}" checkout --detach "${target_sha}"
}

assess_existing_clone() {
  fetch_existing_clone

  local local_sha remote_sha
  local_sha="$(git -C "${REPO_CACHE_DIR}" rev-parse HEAD)"
  remote_sha="$(remote_ref_sha)"

  if [[ "${local_sha}" == "${remote_sha}" ]] && project_worktree_clean; then
    log "Repo cache already at ${GIT_REF} (${local_sha:0:7}) in ${REPO_CACHE_DIR}"
    sync_compose_tree "${REPO_CACHE_DIR}/${REPO_SUBPATH}"
    return 0
  fi

  if [[ "${local_sha}" != "${remote_sha}" ]]; then
    log "Updating repo cache ${local_sha:0:7} -> ${remote_sha:0:7}"
  else
    log "Resetting local changes in ${REPO_CACHE_DIR}"
  fi
  reset_existing_clone
  sync_compose_tree "${REPO_CACHE_DIR}/${REPO_SUBPATH}"
}

deploy_from_source() {
  [[ -d "${SETUP_SOURCE_DIR}" ]] || die "SETUP_SOURCE_DIR does not exist: ${SETUP_SOURCE_DIR}"
  [[ -f "${SETUP_SOURCE_DIR}/docker-compose.yml" ]] \
    || die "SETUP_SOURCE_DIR must contain docker-compose.yml: ${SETUP_SOURCE_DIR}"
  sync_compose_tree "${SETUP_SOURCE_DIR}"
}

deploy_project() {
  log "Deploying PostgreSQL compose tree to ${DEPLOY_DIR}..."

  if [[ -n "${SETUP_SOURCE_DIR}" ]]; then
    deploy_from_source
    return 0
  fi

  if [[ -d "${REPO_CACHE_DIR}/.git" ]]; then
    assess_existing_clone
    return 0
  fi

  if [[ -d "${REPO_CACHE_DIR}" ]] && [[ -n "$(ls -A "${REPO_CACHE_DIR}" 2>/dev/null)" ]]; then
    die "${REPO_CACHE_DIR} exists but is not a git repository. Remove or rename it, then re-run."
  fi

  clone_repo_cache
  [[ -d "${REPO_CACHE_DIR}/${REPO_SUBPATH}" ]] \
    || die "Missing ${REPO_SUBPATH} in cloned repository"
  sync_compose_tree "${REPO_CACHE_DIR}/${REPO_SUBPATH}"
}

compose_stack_running() {
  [[ -d "${DEPLOY_DIR}" ]] || return 1

  local services
  services="$(cd "${DEPLOY_DIR}" && docker compose ps --status running --format '{{.Service}}' 2>/dev/null)" \
    || return 1
  grep -qx 'postgres' <<<"${services}" || return 1
}

postgres_is_ready() {
  cd "${DEPLOY_DIR}"
  docker compose exec -T postgres pg_isready -U "${POSTGRES_USER}" -d postgres -q
}

start_compose() {
  local rebuild="${1:-1}"

  if [[ "${rebuild}" == "1" ]]; then
    log "Building and starting docker compose stack..."
    cd "${DEPLOY_DIR}"
    docker compose up -d --build
    return 0
  fi

  log "Starting docker compose stack (no rebuild)..."
  cd "${DEPLOY_DIR}"
  docker compose up -d
}

wait_for_postgres() {
  log "Waiting for PostgreSQL (timeout: ${PG_READY_TIMEOUT_SEC}s)..."
  local deadline=$((SECONDS + PG_READY_TIMEOUT_SEC))
  while (( SECONDS < deadline )); do
    if postgres_is_ready; then
      log "PostgreSQL is ready"
      return 0
    fi
    sleep 2
  done

  log "PostgreSQL failed to become ready; recent logs:"
  cd "${DEPLOY_DIR}"
  docker compose logs --tail=50 postgres || true
  die "PostgreSQL readiness check failed"
}

main() {
  parse_args "$@"

  require_root
  setup_swap
  install_packages
  install_etckeeper
  install_docker

  local deploy_action
  deploy_action="$(deploy_project)"

  ensure_deploy_env

  if [[ "${SETUP_FORCE}" == "1" ]]; then
    log "SETUP_FORCE=1 — rebuilding and restarting the stack"
    start_compose 1
    wait_for_postgres
  elif [[ "${deploy_action}" == "current" ]] \
        && compose_stack_running \
        && postgres_is_ready; then
    log "PostgreSQL is already deployed at ${GIT_REF} and the stack is healthy — skipping redeploy"
    log "Use SETUP_FORCE=1 to rebuild and restart anyway"
  elif [[ "${deploy_action}" == "current" ]]; then
    log "Compose tree is already current; ensuring stack is up"
    start_compose 0
    wait_for_postgres
  else
    start_compose 1
    wait_for_postgres
  fi

  log "Deployment complete."
  log "  Directory: ${DEPLOY_DIR}"
  log "  Port:      127.0.0.1:${POSTGRES_PORT}"
  log "  Connect:   postgresql://${POSTGRES_USER}:<password>@host.docker.internal:${POSTGRES_PORT}/<database>"
  log "  Example:   postgresql://${POSTGRES_USER}:<password>@host.docker.internal:${POSTGRES_PORT}/weather"
  log "  Next step: deploy apps with DATABASE_URL pointing at host.docker.internal"
}

main "$@"
