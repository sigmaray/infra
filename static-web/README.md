# Static Web

[nginx](https://nginx.org/) serving static files from `public/` on the shared `infra` Docker network.

| Access | URL |
|--------|-----|
| Via Caddy | `http://<STATIC_WEB_HOST>/` (see [reverse-proxy](../reverse-proxy/README.md)) |
| Direct (host) | `http://127.0.0.1:8080/` (default bind) |
| Docker apps | `http://static-web:80/` |

## Quick start

Prerequisites: the `infra` network must exist (`docker network create infra` on first deploy).

```bash
cd static-web
cp .env.example .env
cp public/index.html.example public/index.html
docker compose up -d
```

Verify:

```bash
docker compose ps
curl -fsS http://127.0.0.1:8080/
```

Add your own files under `public/` and restart is not required — nginx serves the mounted volume directly.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `STATIC_WEB_BIND_ADDRESS` | `127.0.0.1` | Host bind address (`0.0.0.0` for internet access) |
| `STATIC_WEB_PORT` | `8080` | Host port for direct access |

## Layout

```
static-web/
├── docker-compose.yml
├── public/                      # static files served by nginx
│   ├── index.html.example
│   └── index.html               # copy from example, gitignored
├── .env.example
└── .env                         # gitignored
```

## Access via Caddy

Keep `STATIC_WEB_BIND_ADDRESS=127.0.0.1` and route traffic through [reverse-proxy](../reverse-proxy/README.md):

```bash
cd ../reverse-proxy
# in .env:
#   STATIC_WEB_HOST=static.example.com
cp Caddyfile.example Caddyfile
docker compose up -d
```

```bash
curl -fsS -H 'Host: static.infra.local' http://127.0.0.1/
```

## Operations

```bash
docker compose logs -f static-web
docker compose up -d
docker compose down
```
