# Shared PostgreSQL

Shared PostgreSQL 16 for a production VPS. A single instance serves multiple projects: each project gets its own database, and all apps connect as the standard `postgres` user.

## Quick start

```bash
docker network create infra 2>/dev/null || true
cd postgres
cp .env.example .env
# set a strong POSTGRES_PASSWORD
docker compose up -d
```

Verify:

```bash
docker compose ps
docker compose exec postgres pg_isready -U postgres
```

## Connecting applications

The host port is bound to `127.0.0.1` only — PostgreSQL is not exposed to the public internet. How you connect depends on where the app runs.

### Docker apps on the same host (recommended)

Join the `infra` network and connect to the `postgresql` container by name. This is the reliable pattern on Linux VPS.

In the app's `docker-compose.yml`:

```yaml
services:
  app:
    networks:
      - infra

networks:
  infra:
    external: true
    name: infra
```

Connection string (the `weather` database is created on first start):

```
postgresql://postgres:<POSTGRES_PASSWORD>@postgresql:5432/weather
```

See [`../docs/go-client`](../docs/go-client) for a working example.

### Apps on the host (not in Docker)

Connect via the loopback address and the published host port:

```
postgresql://postgres:<POSTGRES_PASSWORD>@127.0.0.1:<POSTGRES_PORT>/weather
```

### Do not use `host.docker.internal` on Linux

On Linux, `host.docker.internal` does not reach PostgreSQL when the port is published on `127.0.0.1` only. Use the Docker network pattern above for containerized apps, or `127.0.0.1` for host-native apps.

Set `DATABASE_URL` in the project's `.env` file.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_USER` | `postgres` | PostgreSQL user |
| `POSTGRES_PASSWORD` | — | Password (required) |
| `POSTGRES_PORT` | `5432` | Host port |

The port is bound to `127.0.0.1` — PostgreSQL is not exposed to the public internet.

## Layout

```
postgres/
├── docker-compose.yml
├── .env.example
├── data/                         # PostgreSQL cluster (bind mount, not in git)
├── init/
│   ├── 01-flask-weather.sh       # CREATE DATABASE weather (first start)
│   └── 20-extra-databases.sh.example
└── scripts/
    └── create-database.sh        # add a database on a running server
```

## Adding a database for a new project

### Server is already running

```bash
./scripts/create-database.sh myapp
```

The script is idempotent: re-running it is safe if the database already exists.

### Before first start

Copy the template and edit the database name:

```bash
cp init/20-extra-databases.sh.example init/20-myapp.sh
chmod +x init/20-myapp.sh
```

Scripts in `init/` run **only on first initialization** (empty `data/` directory). If the cluster is already up, use `create-database.sh` instead.

## Operations

```bash
# logs
docker compose logs -f postgres

# stop
docker compose down

# stop and delete data (destructive!)
docker compose down
rm -rf data

# psql shell
docker compose exec postgres psql -U postgres
```

## VPS deployment

1. Copy `postgres/` to the server (e.g. `~/r/d/postgresql`).
2. Create `.env` with a production password.
3. Run `docker compose up -d`.

Deploy containerized applications on the `infra` network with `DATABASE_URL` pointing at `postgresql:5432`. Host-native apps use `127.0.0.1:<POSTGRES_PORT>`.

## Backups

Automated scheduled dumps live in a separate stack: [`../postgres-backup/`](../postgres-backup/).

Manual one-off dump:

```bash
docker compose exec -T postgres pg_dump -U postgres -Fc weather > weather.dump
```

Restore:

```bash
docker compose exec -T postgres pg_restore -U postgres -d weather --clean --if-exists < weather.dump
```
