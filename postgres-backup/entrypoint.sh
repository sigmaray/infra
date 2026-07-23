#!/usr/bin/env bash
# Generate crontab from BACKUP_CRON and run supercronic (PID 1).
# Extra args replace the default command (e.g. docker compose run --rm backup /usr/local/bin/backup.sh).

set -euo pipefail

if [[ $# -gt 0 ]]; then
  exec "$@"
fi

BACKUP_CRON="${BACKUP_CRON:-0 3 * * *}"
CRONTAB="/etc/crontabs/postgres-backup"

umask 027
printf '%s\n' \
  "# Generated from BACKUP_CRON — do not edit in the running container" \
  "${BACKUP_CRON} /usr/local/bin/backup.sh" \
  >"${CRONTAB}"

echo "[backup-entrypoint] schedule: ${BACKUP_CRON}" >&2
echo "[backup-entrypoint] writing dumps to ${BACKUP_DIR:-/backups}" >&2

exec supercronic -passthrough-logs "${CRONTAB}"
