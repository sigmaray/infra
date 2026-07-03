# Beszel

[Beszel](https://github.com/henrygd/beszel) — lightweight self-hosted server monitoring (CPU, memory, disk, network, Docker containers, alerts) on the shared `infra` Docker network.

This stack runs the **hub** (web dashboard) and can monitor **the same host** via a local agent — see [Local host monitoring](#local-host-monitoring).

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
| `BESZEL_AGENT_HUB_URL` | `http://127.0.0.1:8090` | Hub URL for the local agent (set by `enable-local-agent.sh`) |
| `BESZEL_AGENT_KEY` | — | Hub public key for the local agent |
| `BESZEL_AGENT_TOKEN` | — | Universal token for the local agent |

## Local host monitoring

Monitor the VPS that runs the hub via a Unix socket (no open ports, no manual **Add System** step).

```bash
cd beszel
cp .env.example .env
docker compose up -d
# create the admin account at http://127.0.0.1:8090/
./scripts/enable-local-agent.sh
docker compose --profile local-agent up -d
```

The script authenticates to the hub, enables a **universal token**, and writes `BESZEL_AGENT_*` variables to `.env`. The agent connects through `./beszel_socket/beszel.sock`; the hub auto-creates a system record on first connection.

Verify in the UI: the systems table should show a new host with a green status.

```bash
docker compose --profile local-agent ps
docker compose logs -f beszel-agent
```

To re-run after token rotation:

```bash
./scripts/enable-local-agent.sh
docker compose --profile local-agent up -d
```

## Layout

```
beszel/
├── docker-compose.yml
├── scripts/
│   └── enable-local-agent.sh  # fetch KEY + universal TOKEN into .env
├── data/                        # PocketBase DB (gitignored)
├── beszel_socket/               # hub ↔ local agent Unix socket (gitignored)
├── beszel_agent_data/           # local agent state (gitignored)
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
docker compose --profile local-agent logs -f beszel-agent
docker compose up -d
docker compose --profile local-agent up -d
docker compose --profile local-agent down
docker compose down
```

## VPS deployment

1. Copy `beszel/` to the server (e.g. `~/r/d/beszel`).
2. Create `.env` with production settings:
   - `BESZEL_APP_URL=https://beszel.example.com` (must match the public URL)
   - Keep `BESZEL_BIND_ADDRESS=127.0.0.1` when using Caddy
3. Run `docker compose up -d`.
4. Create the admin account via the web UI.
5. Run `./scripts/enable-local-agent.sh` and `docker compose --profile local-agent up -d` to monitor the same VPS.
6. Deploy agents on other hosts if needed (see below).
7. Configure alerts (CPU, memory, disk, etc.) in the dashboard.

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

Included in this stack — see [Local host monitoring](#local-host-monitoring). For manual setup, use Host/IP `/beszel_socket/beszel.sock` in the **Add System** dialog instead of the universal-token flow.

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
