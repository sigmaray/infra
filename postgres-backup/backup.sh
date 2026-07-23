#!/usr/bin/env bash
# Dump configured PostgreSQL databases (custom format -Fc).
# Destinations (independently enabled):
#   BACKUP_LOCAL — volume at BACKUP_DIR
#   BACKUP_S3    — upload to S3-compatible object storage
#
# Env: see .env.example

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
BACKUP_LOG="${BACKUP_LOG:-${BACKUP_DIR}/backup.log}"
BACKUP_LOCAL="${BACKUP_LOCAL:-true}"
BACKUP_S3="${BACKUP_S3:-false}"
S3_PREFIX="${S3_PREFIX:-postgres}"
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

# True for 1/true/yes/on (case-insensitive). False for 0/false/no/off/empty.
is_enabled() {
  local v
  v="$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')"
  case "${v}" in
    1 | true | yes | on) return 0 ;;
    0 | false | no | off | "") return 1 ;;
    *) die "invalid boolean '${1}' (use true/false)" ;;
  esac
}

s3_uri_prefix() {
  local prefix="${S3_PREFIX#/}"
  prefix="${prefix%/}"
  if [[ -n "${prefix}" ]]; then
    printf 's3://%s/%s' "${S3_BUCKET}" "${prefix}"
  else
    printf 's3://%s' "${S3_BUCKET}"
  fi
}

aws_s3() {
  local -a args=()
  if [[ -n "${AWS_ENDPOINT_URL:-}" ]]; then
    args+=(--endpoint-url "${AWS_ENDPOINT_URL}")
  fi
  aws "${args[@]}" s3 "$@"
}

upload_s3() {
  local file="$1"
  local db="$2"
  local base dest
  base="$(basename "${file}")"
  dest="$(s3_uri_prefix)/${db}/${base}"

  log "Uploading '${file}' -> ${dest}"
  if ! aws_s3 cp "${file}" "${dest}"; then
    log "FAILED S3 upload of '${file}'"
    return 1
  fi
  log "OK S3 ${dest}"
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
  local stamp outfile tmp size work_dir keep_local=0
  stamp="$(date +%Y%m%d_%H%M%S)"

  if is_enabled "${BACKUP_LOCAL}"; then
    keep_local=1
    mkdir -p "${BACKUP_DIR}/${db}"
    outfile="${BACKUP_DIR}/${db}/${db}_${stamp}.dump"
  else
    work_dir="$(mktemp -d)"
    outfile="${work_dir}/${db}_${stamp}.dump"
  fi
  tmp="${outfile}.tmp"

  log "Dumping '${db}' -> ${outfile}"
  if ! pg_dump -Fc --dbname="${db}" --file="${tmp}"; then
    rm -f "${tmp}"
    [[ -n "${work_dir:-}" ]] && rm -rf "${work_dir}"
    log "FAILED dump of '${db}'"
    return 1
  fi
  mv "${tmp}" "${outfile}"
  size="$(wc -c <"${outfile}" | tr -d ' ')"
  log "OK dump '${db}' (${size} bytes)"

  if is_enabled "${BACKUP_S3}"; then
    if ! upload_s3 "${outfile}" "${db}"; then
      [[ "${keep_local}" -eq 0 ]] && rm -rf "${work_dir}"
      return 1
    fi
  fi

  if [[ "${keep_local}" -eq 0 ]]; then
    rm -rf "${work_dir}"
  fi
}

apply_retention() {
  local days="$1"
  if ! [[ "${days}" =~ ^[0-9]+$ ]]; then
    die "BACKUP_RETENTION_DAYS must be a non-negative integer (got: ${days})"
  fi
  if [[ "${days}" -eq 0 ]]; then
    log "Local retention disabled (BACKUP_RETENTION_DAYS=0)"
    return
  fi

  log "Applying local retention: delete dumps older than ${days} day(s)"
  find "${BACKUP_DIR}" -type f -name '*.dump' -mtime "+${days}" -print -delete \
    | while IFS= read -r path; do
      log "Deleted old dump: ${path}"
    done
}

# --- main ---

local_on=0
s3_on=0
is_enabled "${BACKUP_LOCAL}" && local_on=1
is_enabled "${BACKUP_S3}" && s3_on=1

if [[ "${local_on}" -eq 0 && "${s3_on}" -eq 0 ]]; then
  die "Enable at least one destination: BACKUP_LOCAL and/or BACKUP_S3"
fi

if [[ "${s3_on}" -eq 1 ]]; then
  : "${S3_BUCKET:?S3_BUCKET is required when BACKUP_S3=true}"
  : "${AWS_ACCESS_KEY_ID:?AWS_ACCESS_KEY_ID is required when BACKUP_S3=true}"
  : "${AWS_SECRET_ACCESS_KEY:?AWS_SECRET_ACCESS_KEY is required when BACKUP_S3=true}"
  export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY
  export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
  # MinIO / R2 / custom endpoints: path-style + avoid CLI v2 checksum headers MinIO rejects.
  if [[ -n "${AWS_ENDPOINT_URL:-}" ]]; then
    aws_cfg="$(mktemp -d)/config"
    cat >"${aws_cfg}" <<'EOF'
[default]
s3 =
    addressing_style = path
EOF
    export AWS_CONFIG_FILE="${aws_cfg}"
    export AWS_REQUEST_CHECKSUM_CALCULATION="${AWS_REQUEST_CHECKSUM_CALCULATION:-when_required}"
    export AWS_RESPONSE_CHECKSUM_VALIDATION="${AWS_RESPONSE_CHECKSUM_VALIDATION:-when_required}"
  fi
  if ! command -v aws >/dev/null 2>&1; then
    die "aws CLI not found in image (required for BACKUP_S3)"
  fi
fi

log "Starting backup (host=${PGHOST}:${PGPORT} user=${PGUSER} local=${BACKUP_LOCAL} s3=${BACKUP_S3})"

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

if [[ "${local_on}" -eq 1 ]]; then
  apply_retention "${BACKUP_RETENTION_DAYS}"
fi

if [[ "${failed}" -ne 0 ]]; then
  die "One or more dumps failed"
fi

log "Backup finished successfully"
