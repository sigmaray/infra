# Caddy reverse proxy

[Caddy](https://caddyserver.com/) reverse proxy for HTTP services on the shared `infra` Docker network.

| Component | Container | Host ports | Backend |
|-----------|-----------|------------|---------|
| Caddy (HTTP) | `reverse-proxy` | `80` | `wg-easy:51821`, `static-web:80` by hostname |

**Not proxied** (by design):

- **postgres** — database protocol; stays on `127.0.0.1` only inside the postgres stack
- **3proxy** — HTTP CONNECT and SOCKS5 are not HTTP routes; expose them from [`../3proxy`](../3proxy) directly.

## Quick start

Prerequisites: the `infra` network must exist (`docker network create infra` on first deploy).

```bash
cd reverse-proxy
cp .env.example .env
cp Caddyfile.example Caddyfile
# edit .env and Caddyfile for production
docker compose up -d
```

Configure wg-easy for access via Caddy:

```bash
cd ../wg-easy
# in .env:
#   INIT_HOST=<public IP or domain>
#   INSECURE=true
#   WG_EASY_WEB_BIND_ADDRESS=127.0.0.1
docker compose up -d
```

Verify:

```bash
docker compose ps
docker compose logs -f caddy

# local (Host header required when not using *.localhost DNS)
curl -fsS -H 'Host: wg.infra.local' http://127.0.0.1/

# with /etc/hosts or *.localhost resolver
curl -fsS http://wg.localhost/
curl -fsS http://static.localhost/
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WG_EASY_HOST` | `wg.localhost` | Primary hostname for wg-easy web UI |
| `WG_EASY_ALT_HOST` | `wg.infra.local` | Alternate hostname (useful with `Host:` header) |
| `WG_EASY_WEB_PORT` | `51821` | wg-easy container port on `infra` network |
| `STATIC_WEB_HOST` | `static.localhost` | Primary hostname for static file web server |
| `STATIC_WEB_ALT_HOST` | `static.infra.local` | Alternate hostname for static web |
| `CADDY_HTTP_PORT` | `80` | Host port for Caddy HTTP |
| `CADDY_BIND_ADDRESS` | `0.0.0.0` | Bind for Caddy (`127.0.0.1` for local only) |

Caddy reads hostnames from `.env` via `env_file` and substitutes variables in `Caddyfile`. Copy `Caddyfile.example` to `Caddyfile` and edit it for your domains and services.

## Layout

```
reverse-proxy/
├── docker-compose.yml
├── Caddyfile.example
├── Caddyfile                    # copy from example, gitignored
├── .env.example
└── .env                         # gitignored
```

## Access patterns

### wg-easy web UI

1. **Via Caddy (recommended):** set `WG_EASY_HOST=wg.example.com`, point DNS to the server, open TCP `80`. Keep `WG_EASY_WEB_BIND_ADDRESS=127.0.0.1` in wg-easy.
2. **Direct:** set `WG_EASY_WEB_BIND_ADDRESS=0.0.0.0` and open TCP `51821` in the firewall.
3. **SSH tunnel:** keep default `127.0.0.1` bind and use `ssh -L`.

### static-web

1. **Via Caddy (recommended):** set `STATIC_WEB_HOST=static.example.com`, point DNS to the server. Keep `STATIC_WEB_BIND_ADDRESS=127.0.0.1` in static-web.
2. **Direct:** set `STATIC_WEB_BIND_ADDRESS=0.0.0.0` and open TCP `8080` in the firewall.

### 3proxy (HTTP + SOCKS5)

Manage proxy access in [`../3proxy`](../3proxy). Docker apps can join `3proxy_default` to connect directly to `3proxy:3128` / `3proxy:1080`; host and remote clients use the ports published by the 3proxy stack.

## Operations

```bash
# logs
docker compose logs -f caddy

# validate Caddyfile
docker run --rm -v "$(pwd)/Caddyfile:/etc/caddy/Caddyfile:ro" \
  --env-file .env caddy:2.10.0-alpine caddy validate --config /etc/caddy/Caddyfile

# restart after .env or Caddyfile changes
docker compose up -d

# stop
docker compose down
```

## VPS deployment

1. Copy `reverse-proxy/` to the server (e.g. `~/r/d/reverse-proxy`).
2. Ensure `infra` network exists (`postgres/` or `3proxy/` running, or `docker network create infra`).
3. Create `.env` with production hostnames (`WG_EASY_HOST=wg.example.com`).
4. Copy and edit `Caddyfile` (`cp Caddyfile.example Caddyfile`).
5. Open TCP `80` in the firewall.
6. Point `WG_EASY_HOST` DNS at the server.
7. Run `docker compose up -d`.

Recommended startup order:

```bash
# 1. Shared infrastructure (creates infra network)
cd ~/r/d/postgresql && docker compose up -d
cd ~/r/d/3proxy && ./scripts/generate-3proxy-cfg.sh && docker compose up -d

# 2. VPN with web UI on infra network
cd ~/r/d/wg-easy && docker compose up -d

# 2b. Static file web server
cd ~/r/d/static-web && cp public/index.html.example public/index.html && docker compose up -d

# 3. Reverse proxy (Caddy)
cd ~/r/d/reverse-proxy && cp Caddyfile.example Caddyfile && docker compose up -d
```

## Security notes

- Keep wg-easy web UI on `127.0.0.1` when using Caddy — only reverse-proxy should be internet-facing on port 80.
- Restrict proxy ports (`3128`, `1080`) in the 3proxy stack/firewall; require strong `PROXY_PASSWORD`.
- postgres is not exposed through this stack.
- For HTTPS in production, terminate TLS at an upstream load balancer or extend `Caddyfile` with automatic HTTPS (`https://` site blocks).
