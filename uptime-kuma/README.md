# Uptime Kuma

[Uptime Kuma](https://github.com/louislam/uptime-kuma) — self-hosted uptime monitoring on the shared `infra` Docker network.

| Access | URL |
|--------|-----|
| Via Caddy | `http://<UPTIME_KUMA_HOST>/` (see [reverse-proxy](../reverse-proxy/README.md)) |
| Direct (host) | `http://127.0.0.1:8082/` (default bind) |
| Docker apps | `http://uptime-kuma:3001/` |

## Quick start

Prerequisites: the `infra` network must exist (`docker network create infra` on first deploy).

```bash
cd uptime-kuma
cp .env.example .env
docker compose up -d
```

Open `http://127.0.0.1:8082/` and create the admin account on first visit.

Verify:

```bash
docker compose ps
curl -fsS http://127.0.0.1:8082/
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `UPTIME_KUMA_BIND_ADDRESS` | `127.0.0.1` | Host bind address (`0.0.0.0` for internet access) |
| `UPTIME_KUMA_PORT` | `8082` | Host port for direct access (maps to container port `3001`) |
| `TZ` | `Europe/Moscow` | Container timezone |
| `UPTIME_KUMA_DISABLE_FRAME_SAMEORIGIN` | `0` | Set to `1` to allow iframe embedding |

## Layout

```
uptime-kuma/
├── docker-compose.yml
├── data/                        # SQLite DB and config (created on first start, gitignored)
├── .env.example
└── .env                         # gitignored
```

## Access via Caddy

Keep `UPTIME_KUMA_BIND_ADDRESS=127.0.0.1` and route traffic through [reverse-proxy](../reverse-proxy/README.md). Caddy handles WebSocket upgrades required by the live dashboard.

```bash
cd ../reverse-proxy
# in .env:
#   UPTIME_KUMA_HOST=status.example.com
cp Caddyfile.example Caddyfile
docker compose up -d
```

```bash
curl -fsS -H 'Host: status.infra.local' http://127.0.0.1/
```

## Operations

```bash
docker compose logs -f uptime-kuma
docker compose up -d
docker compose down
```

## VPS deployment

1. Copy `uptime-kuma/` to the server (e.g. `~/r/d/uptime-kuma`).
2. Create `.env` with production settings.
3. Run `docker compose up -d`.
4. Create the admin account via the web UI.
5. Add monitors for your services (HTTP, TCP, ping, Docker containers, etc.).

Recommended: keep the host port on `127.0.0.1` and expose the UI only through Caddy with a real hostname and TLS upstream.

## Backups

Uptime Kuma stores its database under `./data/`. Back up that directory while the container is running (SQLite WAL mode is enabled):

```bash
tar -czf uptime-kuma-backup-$(date +%F).tar.gz data/
```

Restore by stopping the stack, replacing `data/`, and starting again.

## Notes

- Default port `8082` avoids clashing with [static-web](../static-web/) on `8080` and [freshrss](../freshrss/) on `8081`.
- To monitor Docker containers on the same host, add a read-only Docker socket mount in `docker-compose.yml` and configure the Docker monitor type in the UI. This increases attack surface — enable only if needed.
