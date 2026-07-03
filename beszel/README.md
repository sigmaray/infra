# Beszel

[Beszel](https://github.com/henrygd/beszel) — lightweight self-hosted server monitoring (CPU, memory, disk, network, Docker containers, alerts) on the shared `infra` Docker network.

This stack runs the **hub** (web dashboard). Deploy a **beszel-agent** on each host you want to monitor — see [Agent deployment](#agent-deployment).

| Access | URL |
|--------|-----|
| Via Caddy | `http://<BESZEL_HOST>/` (see [reverse-proxy](../reverse-proxy/README.md)) |
| Direct (host) | `http://127.0.0.1:8090/` (default bind) |
| Docker apps | `http://beszel:8090/` |

## Quick start

Prerequisites: the `infra` network must exist (`docker network create infra` on first deploy).

```bash
cd beszel
cp .env.example .env
docker compose up -d
```

Open `http://127.0.0.1:8090/` and create the admin account on first visit.

Verify:

```bash
docker compose ps
curl -fsS http://127.0.0.1:8090/
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BESZEL_BIND_ADDRESS` | `127.0.0.1` | Host bind address (`0.0.0.0` for internet access) |
| `BESZEL_PORT` | `8090` | Host port for direct access (maps to container port `8090`) |
| `BESZEL_APP_URL` | `http://127.0.0.1:8090` | Public URL for links and OAuth (set to Caddy hostname in production) |
| `TZ` | `Europe/Moscow` | Container timezone |

## Layout

```
beszel/
├── docker-compose.yml
├── data/                        # PocketBase DB and config (created on first start, gitignored)
├── .env.example
└── .env                         # gitignored
```

## Access via Caddy

Keep `BESZEL_BIND_ADDRESS=127.0.0.1` and route traffic through [reverse-proxy](../reverse-proxy/README.md).

```bash
cd ../reverse-proxy
# in .env:
#   BESZEL_HOST=beszel.example.com
# in beszel/.env:
#   BESZEL_APP_URL=https://beszel.example.com
cp Caddyfile.example Caddyfile
docker compose up -d
```

```bash
curl -fsS -H 'Host: beszel.infra.local' http://127.0.0.1/
```

## Operations

```bash
docker compose logs -f beszel
docker compose up -d
docker compose down
```

## VPS deployment

1. Copy `beszel/` to the server (e.g. `~/r/d/beszel`).
2. Create `.env` with production settings:
   - `BESZEL_APP_URL=https://beszel.example.com` (must match the public URL)
   - Keep `BESZEL_BIND_ADDRESS=127.0.0.1` when using Caddy
3. Run `docker compose up -d`.
4. Create the admin account via the web UI.
5. Add systems and deploy agents on each monitored host (see below).
6. Configure alerts (CPU, memory, disk, etc.) in the dashboard.

Recommended: keep the host port on `127.0.0.1` and expose the UI only through Caddy with a real hostname and TLS upstream.

## Agent deployment

The hub does not collect metrics itself — install a **beszel-agent** on every host you want to monitor. Agents connect outbound to the hub; no inbound ports are required on monitored hosts when using the hub's generated token/key flow.

### Remote host (Docker)

On each monitored server, create a directory and `docker-compose.yml`:

```yaml
services:
  beszel-agent:
    image: henrygd/beszel-agent:0.18.7
    container_name: beszel-agent
    restart: unless-stopped
    network_mode: host
    volumes:
      - ./beszel_agent_data:/var/lib/beszel-agent
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      KEY: "<public-key-from-hub>"
      PORT: "45876"
```

Steps in the hub UI:

1. Click **Add System**, enter a name and the agent's reachable IP and port (e.g. `192.168.1.100:45876`).
2. Copy the generated public key into the agent's `KEY` environment variable.
3. Run `docker compose up -d` on the target host.

`network_mode: host` is required for accurate network and system metrics. The read-only Docker socket mount enables container statistics.

### Same host as hub (Unix socket)

To monitor the VPS that runs the hub, use a shared Unix socket instead of TCP. See the [official hub + local agent guide](https://beszel.dev/guide/hub-installation) for the full `beszel_socket` setup.

## Backups

Beszel stores its PocketBase database under `./data/`. Back up that directory regularly:

```bash
tar -czf beszel-backup-$(date +%F).tar.gz data/
```

Restore by stopping the stack, replacing `data/`, and starting again. Beszel also supports automatic backups to disk or S3-compatible storage from the web UI.

## Notes

- Default port `8090` avoids clashing with [static-web](../static-web/) on `8080`, [freshrss](../freshrss/) on `8081`, and [uptime-kuma](../uptime-kuma/) on `8083`.
- [Uptime Kuma](../uptime-kuma/) checks endpoint availability; Beszel tracks resource usage and container metrics — they complement each other.
- Pin agent image version to match the hub (`0.18.7`).
