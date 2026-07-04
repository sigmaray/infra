# IPsec VPN (hwdsl2/ipsec-vpn-server)

[hwdsl2/ipsec-vpn-server](https://github.com/hwdsl2/docker-ipsec-vpn-server) — IPsec VPN with IPsec/L2TP, Cisco IPsec and IKEv2. Suitable for a production VPS.

## Quick start

```bash
cd ipsec-vpn
cp .env.example .env
# set VPN_IPSEC_PSK (20+ random chars), VPN_USER, VPN_PASSWORD
docker network create infra  # once per host
docker compose up -d
```

Verify:

```bash
docker compose ps
docker compose logs ipsec-vpn
```

On first start, the container prints VPN login details and sets up IKEv2. Search the logs for `Connect to your new VPN with these details:` and `IKEv2 setup successful`.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VPN_IPSEC_PSK` | — | IPsec pre-shared key (required, 20+ random characters) |
| `VPN_USER` | `vpnuser` | Username for IPsec/L2TP and Cisco IPsec |
| `VPN_PASSWORD` | — | Password for IPsec/L2TP and Cisco IPsec (required) |
| `VPN_DNS_NAME` | — | FQDN for IKEv2 server address (recommended in production) |
| `VPN_CLIENT_NAME` | `vpnclient` | Name for the first IKEv2 client |
| `VPN_DNS_SRV1` | Google DNS | Primary DNS for VPN clients |
| `VPN_DNS_SRV2` | Google DNS | Secondary DNS for VPN clients |
| `VPN_PUBLIC_IP` | auto-detected | Public IP when auto-detection fails |
| `VPN_PROTECT_CONFIG` | — | Set to `yes` to password-protect IKEv2 export files |
| `IPSEC_VPN_IKE_PORT` | `500` | Host UDP port for IKE (ISAKMP) |
| `IPSEC_VPN_NAT_PORT` | `4500` | Host UDP port for IPsec NAT-T |

See [upstream vpn.env.example](https://github.com/hwdsl2/docker-ipsec-vpn-server/blob/master/vpn.env.example) for additional options (`VPN_ADDL_USERS`, etc.).

**Note:** In `.env`, do not put quotes around values or spaces around `=`. Avoid `\`, `"`, and `'` inside values.

## Layout

```
ipsec-vpn/
├── docker-compose.yml
├── .env.example
└── data/                 # IKEv2 certificates and VPN config (created on first start, gitignored)
```

## Connecting clients

### IKEv2 (recommended)

1. After first start, export client config from the container:

   ```bash
   docker compose exec ipsec-vpn ls -l /etc/ipsec.d
   docker cp ipsec-vpn:/etc/ipsec.d/vpnclient.mobileconfig ./   # iOS / macOS
   docker cp ipsec-vpn:/etc/ipsec.d/vpnclient.p12 ./            # Windows / Linux
   docker cp ipsec-vpn:/etc/ipsec.d/vpnclient.sswan ./          # Android
   ```

2. Import the profile on your device. See [IKEv2 client docs](https://github.com/hwdsl2/setup-ipsec-vpn/blob/master/docs/ikev2-howto.md).

3. Set `VPN_DNS_NAME` to your server's FQDN before the first start when possible — clients will use it as the IKEv2 server address.

### IPsec/L2TP and Cisco IPsec

Use the credentials from `docker compose logs ipsec-vpn`:

- **Server:** your server's public IP or `VPN_DNS_NAME`
- **IPsec PSK:** `VPN_IPSEC_PSK`
- **Username / password:** `VPN_USER` / `VPN_PASSWORD`

Client setup guides:

- [IPsec/L2TP](https://github.com/hwdsl2/setup-ipsec-vpn/blob/master/docs/clients.md)
- [Cisco IPsec (XAuth)](https://github.com/hwdsl2/setup-ipsec-vpn/blob/master/docs/clients-xauth.md)

## Production deployment

1. Copy `ipsec-vpn/` to the server (e.g. `~/r/d/ipsec-vpn`).
2. Create `.env`:
   - `VPN_IPSEC_PSK` — at least 20 random characters
   - `VPN_PASSWORD` — strong password
   - `VPN_DNS_NAME` — FQDN pointing to the server (for IKEv2)
   - `VPN_PUBLIC_IP` — if the server is behind NAT or auto-detection is wrong
3. Open **UDP 500** and **UDP 4500** in the host firewall and cloud security group.
4. Enable IP forwarding on the host (if not already):

   ```bash
   echo 'net.ipv4.ip_forward=1' | sudo tee /etc/sysctl.d/99-ipsec-vpn.conf
   sudo sysctl -p /etc/sysctl.d/99-ipsec-vpn.conf
   ```

5. Run `docker compose up -d`.

### Firewall

| Port | Protocol | Purpose |
|------|----------|---------|
| 500 | UDP | IKE (ISAKMP) |
| 4500 | UDP | IPsec NAT-T |

On Ubuntu with UFW:

```bash
sudo ufw allow 500/udp
sudo ufw allow 4500/udp
```

### Access

| Path | Notes |
|------|-------|
| VPN clients | Direct UDP to the server — not proxied via Caddy |
| Admin | `docker compose logs`, `docker compose exec ipsec-vpn ipsec status` |

Unlike HTTP services in this repo, IPsec VPN is not routed through [`../reverse-proxy`](../reverse-proxy).

## Operations

```bash
# logs (includes credentials on first start)
docker compose logs -f ipsec-vpn

# IPsec status
docker compose exec ipsec-vpn ipsec status

# manage IKEv2 clients
docker compose exec ipsec-vpn ikev2.sh --help

# restart after .env changes (see note below)
docker compose up -d

# stop (keeps data/)
docker compose down

# stop and delete IKEv2 certs and VPN config (destructive!)
docker compose down
rm -rf data/
```

**Changing credentials:** If you modify VPN user credentials in `.env` after the first start, remove and recreate the container (`docker compose down && docker compose up -d`). For IKEv2 options that were already applied, you may need to clear `data/` and set up again.

### Backup

Back up the `data/` directory — it contains IKEv2 certificates and keys:

```bash
tar czf ipsec-vpn-data-$(date +%F).tar.gz data/
```

## Security notes

- Use a strong `VPN_IPSEC_PSK` (20+ random characters) and `VPN_PASSWORD`.
- Prefer IKEv2 over IPsec/L2TP when possible.
- Each VPN user can connect from multiple devices, but IPsec/L2TP has limitations behind the same NAT — use IKEv2 or Cisco IPsec in that case.
- Restrict who receives VPN credentials; connected clients get network access through the tunnel.
- Keep the image updated: `docker compose pull && docker compose up -d`.

## References

- [Docker image on Docker Hub](https://hub.docker.com/r/hwdsl2/ipsec-vpn-server)
- [GitHub repository](https://github.com/hwdsl2/docker-ipsec-vpn-server)
- [IKEv2 how-to](https://github.com/hwdsl2/setup-ipsec-vpn/blob/master/docs/ikev2-howto.md)
