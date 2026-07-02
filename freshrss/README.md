# FreshRSS

[FreshRSS](https://freshrss.org/) — self-hosted RSS feed aggregator on the shared `infra` Docker network.

| Access | URL |
|--------|-----|
| Via Caddy | `http://<FRESHRSS_HOST>/` (see [reverse-proxy](../reverse-proxy/README.md)) |
| Direct (host) | `http://127.0.0.1:8081/` (default bind) |
| Docker apps | `http://freshrss:80/` |

## Quick start

Prerequisites: the `infra` network must exist (`docker network create infra` on first deploy).

```bash
cd freshrss
cp .env.example .env
docker compose up -d
```

Open `http://127.0.0.1:8081/` and complete the web installer (SQLite is the simplest option).

Verify:

```bash
docker compose ps
curl -fsS http://127.0.0.1:8081/
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FRESHRSS_BIND_ADDRESS` | `127.0.0.1` | Host bind address (`0.0.0.0` for internet access) |
| `FRESHRSS_PORT` | `8081` | Host port for direct access |
| `TZ` | `Europe/Moscow` | Container timezone |
| `CRON_MIN` | `*/5` | Cron schedule for automatic feed refresh (empty disables cron) |
| `TRUSTED_PROXY` | Docker/private ranges | Trusted reverse-proxy CIDRs for `X-Forwarded-For` |

## Layout

```
freshrss/
├── docker-compose.yml
├── data/                        # SQLite DB and config (created on first start, gitignored)
├── extensions/                  # optional third-party extensions (gitignored)
├── .env.example
└── .env                         # gitignored
```

## Access via Caddy

Keep `FRESHRSS_BIND_ADDRESS=127.0.0.1` and route traffic through [reverse-proxy](../reverse-proxy/README.md):

```bash
cd ../reverse-proxy
# in .env:
#   FRESHRSS_HOST=freshrss.example.com
cp Caddyfile.example Caddyfile
docker compose up -d
```

```bash
curl -fsS -H 'Host: freshrss.infra.local' http://127.0.0.1/
```

## Operations

```bash
docker compose logs -f freshrss
docker compose up -d
docker compose down
```

Refresh feeds manually:

```bash
docker compose exec freshrss cli/actualize-user.php --user admin
```

List users:

```bash
docker compose exec --user www-data freshrss cli/list-users.php
```

## Notes

- Default port `8081` avoids clashing with [static-web](../static-web/) on `8080`.
- Built-in cron (`CRON_MIN`) refreshes feeds in the background; use a gentler schedule like `3,33` if you subscribe to many feeds.
- For PostgreSQL, use the shared [postgres](../postgres/) stack and select it in the FreshRSS web installer.
