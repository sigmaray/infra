# WireGuard (wg-easy)

[wg-easy](https://github.com/wg-easy/wg-easy) v15 — WireGuard VPN server with a web UI for managing clients. Suitable for a production VPS.

## Quick start

```bash
cd wg-easy
cp .env.example .env
# set INIT_HOST to your server's public IP or domain
# set a strong INIT_PASSWORD
docker compose up -d
```

Verify:

```bash
docker compose ps
docker compose logs -f wg-easy
```

By default, the web UI is bound to `127.0.0.1` — local access only. Set `WG_EASY_WEB_BIND_ADDRESS=0.0.0.0` in `.env` to accept connections from the internet (see [Remote access](#remote-access)).

Open the web UI:

```bash
# on the server
curl -fsS http://127.0.0.1:51821/
```

Log in with `INIT_USERNAME` / `INIT_PASSWORD` from `.env`.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `INIT_HOST` | — | Public IP or domain VPN clients use to reach this server (required) |
| `INIT_USERNAME` | `admin` | Admin username (first-time setup) |
| `INIT_PASSWORD` | — | Admin password (required) |
| `INIT_ENABLED` | `true` | Run unattended first-time setup on empty data directory |
| `INIT_PORT` | `51820` | WireGuard UDP port used during setup (must match `WG_EASY_WG_PORT`) |
| `INSECURE` | `true` | Allow HTTP for the web UI without HTTPS |
| `WG_EASY_WEB_BIND_ADDRESS` | `127.0.0.1` | Host bind address for the web UI (`0.0.0.0` for internet access) |
| `WG_EASY_WEB_PORT` | `51821` | Host port for the web UI |
| `WG_EASY_WG_PORT` | `51820` | Host port for WireGuard UDP traffic (public) |
| `LANG` | `en` | UI language |

## Layout

```
wg-easy/
├── docker-compose.yml
├── .env.example
└── data/                 # WireGuard config and keys (created on first start, gitignored)
```

## Connecting clients

1. Open the web UI and create a client.
2. Download the `.conf` file or scan the QR code on a phone.
3. Ensure UDP port `WG_EASY_WG_PORT` (default `51820`) is open in your firewall and allowed by your cloud provider security group.

`INIT_HOST` must match what clients can actually reach — use your server's public IP or a DNS name that resolves to it.

### Remote access

To open the web UI from outside the server, set in `.env`:

```bash
WG_EASY_WEB_BIND_ADDRESS=0.0.0.0
```

Then open `WG_EASY_WEB_PORT` (default `51821`) in your firewall and cloud security group.

Test from a remote machine (replace `<server-ip>`):

```bash
curl -fsS http://<server-ip>:51821/
```

Use a strong `INIT_PASSWORD` — authentication is required, but the port is reachable from the internet. Prefer HTTPS via a reverse proxy (`INSECURE=false`) when exposing the UI publicly.

### SSH tunnel (alternative)

If the web UI stays on `127.0.0.1`:

```bash
ssh -L 51821:127.0.0.1:51821 user@your-server.example.com
# then open http://127.0.0.1:51821 in a browser
```

## Production deployment

1. Copy `wg-easy/` to the server (e.g. `~/r/d/wg-easy`).
2. Create `.env`:
   - `INIT_HOST` — public IP or domain
   - `INIT_PASSWORD` — strong admin password
   - `INSECURE=false` if you terminate TLS at a reverse proxy
3. Open UDP `51820` (or your `WG_EASY_WG_PORT`) in the firewall.
4. Run `docker compose up -d`.

### Web UI access

- **Internet** (direct): set `WG_EASY_WEB_BIND_ADDRESS=0.0.0.0`, open TCP `WG_EASY_WEB_PORT` in the firewall. Use a strong password; set `INSECURE=false` and terminate TLS at a reverse proxy when possible.
- **SSH tunnel**: keep the default `127.0.0.1` bind and use `ssh -L 51821:127.0.0.1:51821 user@server`.
- **Reverse proxy** (recommended for team access): use the [`../reverse-proxy`](../reverse-proxy) Caddy stack. Set `INSECURE=false`, keep `WG_EASY_WEB_BIND_ADDRESS=127.0.0.1`, and open the web UI at `https://<WG_EASY_DOMAIN>/`.

WireGuard UDP traffic is published on all interfaces — clients must reach this port directly.

### Migrating from wg-easy v14

1. Back up `data/wg0.json`.
2. Stop the container and clear `data/`.
3. Start v15 with the new `.env` format (`INIT_HOST`, `INIT_PASSWORD`, etc.).
4. Import the old configuration via the setup wizard if needed.

## Operations

```bash
# logs
docker compose logs -f wg-easy

# restart after .env changes
docker compose up -d

# stop (keeps data/)
docker compose down

# stop and delete VPN config (destructive!)
docker compose down
rm -rf data/
```

Check the WireGuard interface:

```bash
docker compose exec wg-easy wg show
```

## Security notes

- Use a strong `INIT_PASSWORD`; it grants full VPN administration.
- Keep the web UI on `127.0.0.1`, behind HTTPS, or restrict firewall access when using `WG_EASY_WEB_BIND_ADDRESS=0.0.0.0`.
- Restrict who can create VPN clients; each client gets full network access through the tunnel.
- Enable IP forwarding on the host if you route client traffic through the VPN (`net.ipv4.ip_forward=1` is set in the container; the host may also need it for NAT).
