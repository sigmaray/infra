# Portainer

[Portainer CE](https://www.portainer.io/) — web UI for managing Docker containers, images, volumes, and networks on the shared `infra` Docker network.

| Access | URL |
|--------|-----|
| Via Caddy | `http://<PORTAINER_HOST>/` (see [reverse-proxy](../reverse-proxy/README.md)) |
| Direct (host) | `https://127.0.0.1:9443/` (default bind, self-signed TLS) |
| Docker apps | `http://portainer:9000/` (HTTP, internal only) |

## Quick start

Prerequisites: the `infra` network must exist (`docker network create infra` on first deploy).

```bash
cd portainer
cp .env.example .env
docker compose up -d
```

Open `https://127.0.0.1:9443/` (accept the self-signed certificate warning) and create the admin account on first visit.

Verify:

```bash
docker compose ps
curl -kfsS https://127.0.0.1:9443/api/status
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORTAINER_BIND_ADDRESS` | `127.0.0.1` | Host bind address (`0.0.0.0` for internet access) |
| `PORTAINER_HTTPS_PORT` | `9443` | Host port for direct HTTPS access (maps to container port `9443`) |
| `TZ` | `Europe/Moscow` | Container timezone |

HTTP on port `9000` is enabled inside the container (`--http-enabled`) for Caddy on the `infra` network. It is **not** published to the host — use Caddy or HTTPS on `9443` for browser access.

## Layout

```
portainer/
├── docker-compose.yml
├── data/                        # Portainer config and TLS certs (created on first start, gitignored)
├── .env.example
└── .env                         # gitignored
```

## Access via Caddy

Keep `PORTAINER_BIND_ADDRESS=127.0.0.1` and route traffic through [reverse-proxy](../reverse-proxy/README.md). Caddy proxies to `portainer:9000` over HTTP on the internal network.

```bash
cd ../reverse-proxy
# in .env:
#   PORTAINER_HOST=portainer.example.com
cp Caddyfile.example Caddyfile
docker compose up -d
```

```bash
curl -fsS -H 'Host: portainer.infra.local' http://127.0.0.1/api/status
```

## Operations

```bash
docker compose logs -f portainer
docker compose up -d
docker compose down
```

## VPS deployment

1. Copy `portainer/` to the server (e.g. `~/r/d/portainer`).
2. Create `.env` with production settings.
3. Run `docker compose up -d`.
4. Create the admin account via the web UI.
5. In Portainer, add the local Docker environment (auto-detected via the mounted socket).

Recommended:

- Keep the host port on `127.0.0.1` and expose the UI only through Caddy with a real hostname and TLS upstream.
- Use a strong admin password.
- Restrict who can reach the UI — Portainer has full control over Docker on the host via `/var/run/docker.sock`.

## Backups

Portainer stores its database and TLS certificates under `./data/`. Back up that directory while the container is running:

```bash
tar -czf portainer-backup-$(date +%F).tar.gz data/
```

Restore by stopping the stack, replacing `data/`, and starting again.

## Security notes

- Mounting `/var/run/docker.sock` gives Portainer root-equivalent access to the host Docker daemon. Deploy only on trusted servers.
- Default port `9443` avoids clashing with [static-web](../static-web/) on `8080`, [freshrss](../freshrss/) on `8081`, and [uptime-kuma](../uptime-kuma/) on `8083`.
- Port `8000` (Edge Agent tunnel) is not exposed by default. Add it to `docker-compose.yml` only if you use Edge Agents.
- For HTTPS in production, terminate TLS at Caddy and keep Portainer HTTP on the internal `infra` network only.
