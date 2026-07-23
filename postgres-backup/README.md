# PostgreSQL backups

Scheduled `pg_dump` for the shared [postgres](../postgres/) stack. Runs [supercronic](https://github.com/aptible/supercronic) in its own Compose project — no host cron.

Connects to `postgresql:5432` on the `infra` network. Destinations are configured independently:

- **Local volume** (`BACKUP_LOCAL`) → `./backups`
- **S3** (`BACKUP_S3`) → bucket via AWS CLI (S3-compatible endpoints supported)

Enable at least one. Both can be on at the same time.

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
| `BACKUP_LOCAL` | `true` | Write dumps to `./backups` volume |
| `BACKUP_S3` | `false` | Upload dumps to S3 |
| `BACKUP_RETENTION_DAYS` | `14` | Local retention (`0` = keep forever); ignored if `BACKUP_LOCAL=false` |
| `S3_BUCKET` | — | Bucket name (required if `BACKUP_S3=true`) |
| `S3_PREFIX` | `postgres` | Key prefix (`s3://bucket/prefix/<db>/…`) |
| `AWS_ACCESS_KEY_ID` | — | Access key (required if `BACKUP_S3=true`) |
| `AWS_SECRET_ACCESS_KEY` | — | Secret key (required if `BACKUP_S3=true`) |
| `AWS_DEFAULT_REGION` | `us-east-1` | Region |
| `AWS_ENDPOINT_URL` | _(empty)_ | Custom endpoint (MinIO, R2, …) |
| `BACKUP_CRON` | `0 3 * * *` | supercronic schedule |
| `TZ` | `UTC` | Timezone for the schedule |

Boolean values: `true` / `false` (also `1`/`0`, `yes`/`no`, `on`/`off`).

### Example: disk only (default)

```bash
BACKUP_LOCAL=true
BACKUP_S3=false
```

### Example: S3 only

```bash
BACKUP_LOCAL=false
BACKUP_S3=true
S3_BUCKET=my-pg-backups
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=eu-central-1
```

### Example: disk + S3

```bash
BACKUP_LOCAL=true
BACKUP_S3=true
S3_BUCKET=my-pg-backups
# …
```

S3 object retention is best done with a **bucket lifecycle rule** (expire objects under `S3_PREFIX/` after N days). Local retention stays in `BACKUP_RETENTION_DAYS`.

When `AWS_ENDPOINT_URL` is set (MinIO, R2, …), the backup script uses path-style addressing and relaxes AWS CLI v2 checksum headers so uploads work against S3-compatible APIs.

## Layout

```
postgres-backup/
├── docker-compose.yml
├── Dockerfile
├── backup.sh
├── entrypoint.sh
├── .env.example
└── backups/              # local dumps + backup.log (not in git)
```

## Output

- Local: `./backups/<database>/<database>_YYYYMMDD_HHMMSS.dump` (custom format `-Fc`)
- S3: `s3://<bucket>/<prefix>/<database>/<database>_YYYYMMDD_HHMMSS.dump`
- Log: `./backups/backup.log` and `docker compose logs -f backup`

## Restore

From a local dump (paths relative to `postgres/`):

```bash
docker compose exec -T postgres pg_restore -U postgres -d weather --clean --if-exists \
  < ../postgres-backup/backups/weather/weather_YYYYMMDD_HHMMSS.dump
```

From S3:

```bash
aws s3 cp s3://my-pg-backups/postgres/weather/weather_YYYYMMDD_HHMMSS.dump ./weather.dump
docker compose exec -T postgres pg_restore -U postgres -d weather --clean --if-exists < weather.dump
```

## Operations

```bash
docker compose logs -f backup
docker compose down
```
