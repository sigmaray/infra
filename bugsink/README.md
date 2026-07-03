# Bugsink

[Bugsink](https://www.bugsink.com/) — lightweight self-hosted error tracking compatible with the [Sentry SDK](https://docs.sentry.io/). Collects crash reports, stack traces, and context from your applications on the shared `infra` Docker network.

Bugsink stores data in the shared [PostgreSQL](../postgres/) instance (database `bugsink`), not in a local volume.

| Access | URL |
|--------|-----|
| Via Caddy | `http://<BUGSINK_HOST>/` (see [reverse-proxy](../reverse-proxy/README.md)) |
| Direct (host) | `http://127.0.0.1:8000/` (default bind) |
| Docker apps | `http://bugsink:8000/` |
| Sentry DSN (ingest) | `http://<public-host>/api/<project-id>/` |

## Quick start

Prerequisites:

1. The `infra` network must exist (`docker network create infra` on first deploy).
2. Shared PostgreSQL must be running (`../postgres/`).
3. Create the `bugsink` database:

```bash
cd ../postgres
./scripts/create-database.sh bugsink
```

Deploy Bugsink:

```bash
cd bugsink
cp .env.example .env
# set BUGSINK_SECRET_KEY, BUGSINK_CREATE_SUPERUSER, and BUGSINK_DATABASE_URL
docker compose up -d
```

Open `http://127.0.0.1:8000/` and sign in with credentials from `BUGSINK_CREATE_SUPERUSER` (format `email:password`).

Verify:

```bash
docker compose ps
curl -fsS http://127.0.0.1:8000/health/ready
```

After the admin account works, remove `BUGSINK_CREATE_SUPERUSER` from `.env` to avoid resetting credentials on redeploy.

Alternative — create admin manually:

```bash
docker compose exec bugsink python manage.py createsuperuser
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BUGSINK_BIND_ADDRESS` | `127.0.0.1` | Host bind address (`0.0.0.0` for internet access) |
| `BUGSINK_PORT` | `8000` | Host port for direct access (maps to container port `8000`) |
| `BUGSINK_SECRET_KEY` | — | Django secret key, at least 50 characters (required) |
| `BUGSINK_CREATE_SUPERUSER` | — | Initial admin `email:password` (required on first start) |
| `BUGSINK_DATABASE_URL` | — | PostgreSQL connection string (required) |

Public URL, proxy settings, teams, and projects are configured in the Bugsink web UI.

### Database URL

Password must match `POSTGRES_PASSWORD` in `../postgres/.env`:

```
postgresql://postgres:<POSTGRES_PASSWORD>@postgresql:5432/bugsink
```

Host-native tools (outside Docker) use `127.0.0.1` instead of `postgresql`:

```
postgresql://postgres:<POSTGRES_PASSWORD>@127.0.0.1:<POSTGRES_PORT>/bugsink
```

## Connecting applications

1. Sign in to the Bugsink web UI.
2. Create a team and project.
3. Copy the DSN from the project settings page.
4. Configure your app's Sentry SDK with that DSN.

Example (Python):

```python
import sentry_sdk

sentry_sdk.init(
    dsn="http://<key>@bugsink:8000/<project-id>",
    traces_sample_rate=0,
    send_default_pii=True,
)
```

For apps running on the host (not in Docker), use the public hostname or `127.0.0.1:8000` in the DSN.

See [Bugsink SDK recommendations](https://www.bugsink.com/docs/sdk-recommendations/) for `traces_sample_rate`, PII, and other settings.

## Layout

```
bugsink/
├── docker-compose.yml
├── .env.example
└── .env                         # gitignored
```

No local data directory — state lives in shared PostgreSQL.

## Access via Caddy

Keep `BUGSINK_BIND_ADDRESS=127.0.0.1` and route traffic through [reverse-proxy](../reverse-proxy/README.md).

```bash
cd ../reverse-proxy
# in .env:
#   BUGSINK_HOST=bugsink.example.com
# set public URL and proxy options in the Bugsink web UI
cp Caddyfile.example Caddyfile
docker compose up -d
```

```bash
curl -fsS -H 'Host: bugsink.infra.local' http://127.0.0.1/health/ready
```

When using Caddy with HTTPS, enable the corresponding proxy settings in the Bugsink UI.

## Operations

```bash
docker compose logs -f bugsink
docker compose up -d
docker compose down
```

Create additional admin users after first deploy:

```bash
docker compose exec bugsink python manage.py createsuperuser
```

Upgrade image version in `docker-compose.yml`, then:

```bash
docker compose pull
docker compose up -d
```

Bugsink runs database migrations automatically on startup.

## VPS deployment

1. Deploy [postgres](../postgres/) and create the `bugsink` database.
2. Copy `bugsink/` to the server (e.g. `~/r/d/bugsink`).
3. Create `.env` with production settings:
   - Generate `BUGSINK_SECRET_KEY` with `openssl rand -base64 50`
   - Set `BUGSINK_DATABASE_URL` with the production postgres password
   - Keep `BUGSINK_BIND_ADDRESS=127.0.0.1` when using Caddy
4. Run `docker compose up -d`.
5. Create the admin account and configure public URL in the web UI.
6. Configure [reverse-proxy](../reverse-proxy/) with `BUGSINK_HOST`.
7. Point application Sentry SDKs at the public DSN.

Recommended: keep the host port on `127.0.0.1` and expose the UI only through Caddy with a real hostname and TLS.

## Backups

Back up the `bugsink` database via the shared postgres stack:

```bash
cd ../postgres
docker compose exec -T postgres pg_dump -U postgres -Fc bugsink > bugsink.dump
```

Restore:

```bash
docker compose exec -T postgres pg_restore -U postgres -d bugsink --clean --if-exists < bugsink.dump
```

## Notes

- Default port `8000` does not clash with [static-web](../static-web/) (`8080`), [freshrss](../freshrss/) (`8081`), [uptime-kuma](../uptime-kuma/) (`8083`), or [beszel](../beszel/) (`8090`).
- [Uptime Kuma](../uptime-kuma/) checks endpoint availability; Bugsink captures application errors — they complement each other.
- Pin the image tag in `docker-compose.yml` (`2.2.2`) and upgrade deliberately after reading [release notes](https://github.com/bugsink/bugsink/releases).
