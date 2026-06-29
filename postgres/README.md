# example-postgresql-docker-compose

Shared PostgreSQL 16 for a production VPS. A single instance serves multiple projects: each project gets its own database, and all apps connect as the standard `postgres` user.

Docker apps on the same host connect via `host.docker.internal:5432` (see [flask-weather](../../docker-compose.yml) `docker-compose.yml`).

## Quick start

```bash
cd docs/example-postgresql-docker-compose
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

Connection string format:

```
postgresql://postgres:<POSTGRES_PASSWORD>@host.docker.internal:<POSTGRES_PORT>/<database>
```

Example for [flask-weather](../../README.md) (the `weather` database is created on first start):

```
postgresql://postgres:<POSTGRES_PASSWORD>@host.docker.internal:5432/weather
```

Set this value as `DATABASE_URL` in the project's `.env` file.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_USER` | `postgres` | PostgreSQL user |
| `POSTGRES_PASSWORD` | — | Password (required) |
| `POSTGRES_PORT` | `5432` | Host port |

The port is bound to `127.0.0.1` — PostgreSQL is not exposed to the public internet. Docker containers on the same host reach it via `host.docker.internal`.

## Layout

```
docs/example-postgresql-docker-compose/
├── docker-compose.yml
├── .env.example
├── init/
│   ├── 01-flask-weather.sh       # CREATE DATABASE weather (first start)
│   └── 20-extra-databases.sh.example
└── scripts/
    ├── create-database.sh        # add a database on a running server
    └── setup-vps.sh              # bootstrap Ubuntu VPS and deploy the stack
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

Scripts in `init/` run **only on first initialization** (empty `volume-postgres` volume). If the cluster is already up, use `create-database.sh` instead.

## Operations

```bash
# logs
docker compose logs -f postgres

# stop
docker compose down

# stop and delete data (destructive!)
docker compose down -v

# psql shell
docker compose exec postgres psql -U postgres
```

## VPS deployment

Automated bootstrap (Ubuntu, git, Docker, compose stack):

```bash
curl -fsSL https://raw.githubusercontent.com/sigmaray/flask-weather/main/docs/example-postgresql-docker-compose/scripts/setup-vps.sh | sudo bash
# or from a checkout:
sudo bash docs/example-postgresql-docker-compose/scripts/setup-vps.sh
sudo bash docs/example-postgresql-docker-compose/scripts/setup-vps.sh --swap
```

The script deploys to `~/r/d/postgresql` by default, generates `POSTGRES_PASSWORD` in `.env` when unset, and starts the stack. Override with environment variables (see script header).

Manual alternative:

1. Copy `docs/example-postgresql-docker-compose/` to the server (e.g. `~/r/d/postgresql`).
2. Create `.env` with a production password.
3. Run `docker compose up -d`.

Then deploy applications with `DATABASE_URL` pointing at `host.docker.internal`. For flask-weather, use [scripts/setup-vps.sh](../../scripts/setup-vps.sh) — that script expects PostgreSQL to already be reachable on the host.

## Backups

Dump a single database:

```bash
docker compose exec -T postgres pg_dump -U postgres -Fc weather > weather.dump
```

Restore:

```bash
docker compose exec -T postgres pg_restore -U postgres -d weather --clean --if-exists < weather.dump
```
