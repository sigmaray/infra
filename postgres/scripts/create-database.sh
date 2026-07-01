#!/usr/bin/env bash
# Create a database on a running PostgreSQL stack (all apps use the postgres user).
#
# Usage:
#   ./scripts/create-database.sh <database>
#
# Example:
#   ./scripts/create-database.sh blog
#
# Run from postgres/ (or any path — script resolves compose file relative to its location).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

usage() {
  cat <<'EOF'
Usage: create-database.sh <database>

Create a PostgreSQL database on the running PostgreSQL stack.
Idempotent: skips creation when the database already exists.
EOF
}

log() {
  printf '[create-database] %s\n' "$*" >&2
}

die() {
  printf '[create-database] ERROR: %s\n' "$*" >&2
  exit 1
}

if [[ $# -ne 1 ]]; then
  usage
  exit 1
fi

DB_NAME="$1"

if [[ ! -f "${COMPOSE_DIR}/.env" ]]; then
  die "Missing ${COMPOSE_DIR}/.env — copy .env.example and set POSTGRES_PASSWORD."
fi

# shellcheck disable=SC1091
source "${COMPOSE_DIR}/.env"

POSTGRES_USER="${POSTGRES_USER:-postgres}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required in .env}"

if ! docker compose -f "${COMPOSE_DIR}/docker-compose.yml" ps --status running --quiet postgres >/dev/null 2>&1; then
  die "postgres service is not running. Start it with: docker compose -f ${COMPOSE_DIR}/docker-compose.yml up -d"
fi

log "Creating database '${DB_NAME}' if missing..."

docker compose -f "${COMPOSE_DIR}/docker-compose.yml" exec -T \
  -e PGPASSWORD="${POSTGRES_PASSWORD}" \
  postgres \
  psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER}" -d postgres \
  -v db_name="${DB_NAME}" <<'EOSQL'
SELECT format('CREATE DATABASE %I', :'db_name')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'db_name')
\gexec
EOSQL

log "Done."
log "Docker app (infra network): postgresql://${POSTGRES_USER}:<password>@postgresql:5432/${DB_NAME}"
log "Host-native app: postgresql://${POSTGRES_USER}:<password>@127.0.0.1:${POSTGRES_PORT:-5432}/${DB_NAME}"
