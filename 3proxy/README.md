# Shared 3proxy (HTTP + SOCKS5)

Shared [3proxy](https://3proxy.org/) instance for a production VPS. A single container serves both HTTP/HTTPS and SOCKS5 proxies with username/password authentication.

## Quick start

```bash
cd 3proxy
cp .env.example .env
# set a strong PROXY_PASSWORD
./scripts/generate-3proxy-cfg.sh
docker compose up -d
```

Verify:

```bash
docker compose ps
docker compose logs -f proxy
```

Test from the host (replace credentials from `.env`):

```bash
# HTTP proxy
curl -fsS -x "http://proxy:<PROXY_PASSWORD>@127.0.0.1:3128" https://httpbin.org/ip

# SOCKS5 proxy
curl -fsS --socks5 "proxy:<PROXY_PASSWORD>@127.0.0.1:1080" https://httpbin.org/ip
```

## Connecting applications

By default, ports are bound to `127.0.0.1` — local access only. Set `PROXY_BIND_ADDRESS=0.0.0.0` in `.env` to accept connections from the internet (see [Remote access](#remote-access)).

### Docker apps on the same host (recommended)

Join the `3proxy_default` network created by this stack and connect to the `3proxy` container by name.

In the app's `docker-compose.yml`:

```yaml
services:
  app:
    environment:
      HTTP_PROXY: http://proxy:<PROXY_PASSWORD>@3proxy:3128
      HTTPS_PROXY: http://proxy:<PROXY_PASSWORD>@3proxy:3128
      ALL_PROXY: socks5://proxy:<PROXY_PASSWORD>@3proxy:1080
    networks:
      - proxy

networks:
  proxy:
    external: true
    name: 3proxy_default
```

### Apps on the host (not in Docker)

```bash
export HTTP_PROXY=http://proxy:<PROXY_PASSWORD>@127.0.0.1:3128
export HTTPS_PROXY=http://proxy:<PROXY_PASSWORD>@127.0.0.1:3128
export ALL_PROXY=socks5://proxy:<PROXY_PASSWORD>@127.0.0.1:1080
```

Or pass proxy flags directly to tools that support them (`curl -x`, `git config http.proxy`, etc.).

### Remote access

To connect from outside the server, set in `.env`:

```bash
PROXY_BIND_ADDRESS=0.0.0.0
```

Then open `HTTP_PROXY_PORT` (default `3128`) and `SOCKS_PROXY_PORT` (default `1080`) in your firewall and cloud security group.

Test from a remote machine (replace `<server-ip>` and credentials):

```bash
# HTTP proxy
curl -fsS -x "http://proxy:<PROXY_PASSWORD>@<server-ip>:3128" https://httpbin.org/ip

# SOCKS5 proxy
curl -fsS --socks5 "proxy:<PROXY_PASSWORD>@<server-ip>:1080" https://httpbin.org/ip
```

Use a strong `PROXY_PASSWORD` — authentication is required, but the ports are reachable from the internet.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PROXY_USER` | `proxy` | Proxy username |
| `PROXY_PASSWORD` | — | Proxy password (required) |
| `PROXY_BIND_ADDRESS` | `127.0.0.1` | Host bind address (`0.0.0.0` for internet access) |
| `HTTP_PROXY_PORT` | `3128` | Host port for HTTP proxy |
| `SOCKS_PROXY_PORT` | `1080` | Host port for SOCKS5 proxy |

`PROXY_BIND_ADDRESS` controls which host interface receives published traffic. Use `127.0.0.1` for local-only access or `0.0.0.0` to accept remote clients.

Inside the container, 3proxy always listens on ports `3128` (HTTP) and `1080` (SOCKS5). Changing `HTTP_PROXY_PORT` / `SOCKS_PROXY_PORT` only changes the published host ports.

## Layout

```
3proxy/
├── docker-compose.yml
├── .env.example
├── scripts/
│   └── generate-3proxy-cfg.sh    # generates 3proxy.cfg from .env
└── 3proxy.cfg                    # generated, gitignored
```

## Operations

```bash
# logs
docker compose logs -f proxy

# regenerate config after .env changes
./scripts/generate-3proxy-cfg.sh
docker compose up -d

# stop
docker compose down
```

## VPS deployment

1. Copy `3proxy/` to the server (e.g. `~/r/d/3proxy`).
2. Create `.env` with a production password and `PROXY_BIND_ADDRESS=0.0.0.0` for remote access.
3. Open `HTTP_PROXY_PORT` and `SOCKS_PROXY_PORT` in the firewall.
4. Run `./scripts/generate-3proxy-cfg.sh && docker compose up -d`.

Deploy containerized applications on the `3proxy_default` network with proxy URLs pointing at `3proxy:3128` (HTTP) or `3proxy:1080` (SOCKS5). Host-native apps use `127.0.0.1:<port>`.

## Security notes

- Use a strong `PROXY_PASSWORD`; authentication is required for all connections.
- When `PROXY_BIND_ADDRESS=0.0.0.0`, restrict access with a firewall (allow only trusted IPs if possible).
- The proxy can reach any destination allowed by your server's outbound network policy.
