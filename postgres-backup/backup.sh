#!/usr/bin/env bash
# Dump configured PostgreSQL databases to BACKUP_DIR (custom format -Fc).
# Intended to run inside the postgresql-backup container (supercronic or manual).
#
# Env (see .env.example):
#   PGHOST, PGPORT, PGUSER, PGPASSWORD — libpq connection
#   BACKUP_DATABASES — comma-separated names; empty = all non-template DBs except "postgres"
#   BACKUP_DIR — dump root (default /backups)
#   BACKUP_RETENTION_DAYS — delete dumps older than N days (default 14)
#   BACKUP_LOG — append log file (default ${BACKUP_DIR}/backup.log)

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
BACKUP_LOG="${BACKUP_LOG:-${BACKUP_DIR}/backup.log}"
PGHOST="${PGHOST:-postgresql}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-${POSTGRES_USER:-postgres}}"

export PGHOST PGPORT PGUSER
: "${PGPASSWORD:=${POSTGRES_PASSWORD:-}}"
: "${PGPASSWORD:?PGPASSWORD or POSTGRES_PASSWORD is required}"
export PGPASSWORD

mkdir -p "${BACKUP_DIR}"
touch "${BACKUP_LOG}"

log() {
  local line
  line="[$(date -Iseconds)] [backup] $*"
  printf '%s\n' "$line" >&2
  printf '%s\n' "$line" >>"${BACKUP_LOG}"
}

die() {
  log "ERROR: $*"
  exit 1
}

list_databases() {
  if [[ -n "${BACKUP_DATABASES:-}" ]]; then
    local raw="${BACKUP_DATABASES//,/ }"
    # shellcheck disable=SC2086
    printf '%s\n' ${raw}
    return
  fi

  psql -v ON_ERROR_STOP=1 -Atc \
    "SELECT datname FROM pg_database
     WHERE datistemplate = false
       AND datname <> 'postgres'
     ORDER BY 1"
}

dump_one() {
  local db="$1"
  local stamp outfile tmp size
  stamp="$(date +%Y%m%d_%H%M%S)"
  mkdir -p "${BACKUP_DIR}/${db}"
  outfile="${BACKUP_DIR}/${db}/${db}_${stamp}.dump"
  tmp="${outfile}.tmp"

  log "Dumping '${db}' -> ${outfile}"
  if ! pg_dump -Fc --dbname="${db}" --file="${tmp}"; then
    rm -f "${tmp}"
    log "FAILED dump of '${db}'"
    return 1
  fi
  mv "${tmp}" "${outfile}"
  size="$(wc -c <"${outfile}" | tr -d ' ')"
  log "OK '${db}' (${size} bytes)"
}

apply_retention() {
  local days="$1"
  if ! [[ "${days}" =~ ^[0-9]+$ ]]; then
    die "BACKUP_RETENTION_DAYS must be a non-negative integer (got: ${days})"
  fi
  if [[ "${days}" -eq 0 ]]; then
    log "Retention disabled (BACKUP_RETENTION_DAYS=0)"
    return
  fi

  log "Applying retention: delete dumps older than ${days} day(s)"
  find "${BACKUP_DIR}" -type f -name '*.dump' -mtime "+${days}" -print -delete \
    | while IFS= read -r path; do
      log "Deleted old dump: ${path}"
    done
}

log "Starting backup (host=${PGHOST}:${PGPORT} user=${PGUSER})"

if ! psql -v ON_ERROR_STOP=1 -Atc "SELECT 1" >/dev/null; then
  die "Cannot connect to PostgreSQL at ${PGHOST}:${PGPORT}"
fi

mapfile -t databases < <(list_databases | sed '/^$/d')
if [[ ${#databases[@]} -eq 0 ]]; then
  die "No databases to back up (set BACKUP_DATABASES or create app databases)"
fi

failed=0
for db in "${databases[@]}"; do
  if ! dump_one "${db}"; then
    failed=1
  fi
done

apply_retention "${BACKUP_RETENTION_DAYS}"

if [[ "${failed}" -ne 0 ]]; then
  die "One or more dumps failed"
fi

log "Backup finished successfully"
