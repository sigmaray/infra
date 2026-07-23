# PostgreSQL backups

Scheduled `pg_dump` for the shared [postgres](../postgres/) stack. Runs [supercronic](https://github.com/aptible/supercronic) in its own Compose project — no host cron.

Connects to `postgresql:5432` on the `infra` network. Dumps are written to `./backups` on the host.

## Quick start

```bash
# postgres must already be up
cd ../postgres && docker compose up -d

cd ../postgres-backup
cp .env.example .env
# set POSTGRES_PASSWORD to the same value as postgres/.env
docker compose up -d --build
```

Run a dump immediately:

```bash
docker compose run --rm backup /usr/local/bin/backup.sh
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_USER` | `postgres` | PostgreSQL user |
| `POSTGRES_PASSWORD` | — | Password (required; same as `postgres/.env`) |
| `PGHOST` | `postgresql` | Postgres hostname on `infra` |
| `PGPORT` | `5432` | Postgres port |
| `BACKUP_DATABASES` | _(empty)_ | Comma-separated DBs; empty = all except `postgres` |
| `BACKUP_RETENTION_DAYS` | `14` | Delete dumps older than N days (`0` = keep forever) |
| `BACKUP_CRON` | `0 3 * * *` | supercronic schedule |
| `TZ` | `UTC` | Timezone for the schedule |

## Layout

```
postgres-backup/
├── docker-compose.yml
├── Dockerfile
├── backup.sh
├── entrypoint.sh
├── .env.example
└── backups/              # dumps + backup.log (not in git)
```

## Output

- Files: `./backups/<database>/<database>_YYYYMMDD_HHMMSS.dump` (custom format `-Fc`)
- Log: `./backups/backup.log` and `docker compose logs -f backup`

## Restore

From the postgres stack (paths relative to `postgres/`):

```bash
docker compose exec -T postgres pg_restore -U postgres -d weather --clean --if-exists \
  < ../postgres-backup/backups/weather/weather_YYYYMMDD_HHMMSS.dump
```

## Operations

```bash
docker compose logs -f backup
docker compose down
```
