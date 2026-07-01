#!/usr/bin/env bash
#
# Generate 3proxy.cfg from .env (single source of truth for proxy credentials).
#
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${DIR}/../.env"
CFG_FILE="${DIR}/../3proxy.cfg"

if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
fi

: "${PROXY_USER:?PROXY_USER is required in .env or environment}"
: "${PROXY_PASSWORD:?PROXY_PASSWORD is required in .env or environment}"

cat > "${CFG_FILE}" <<EOF
maxconn 200
nserver 127.0.0.11
nserver 8.8.8.8
nserver 8.8.4.4
nscache 65536
timeouts 1 5 30 60 180 1800 15 60
log
auth strong
users ${PROXY_USER}:CL:${PROXY_PASSWORD}
allow ${PROXY_USER}
proxy -p3128
socks -p1080
EOF

chmod 600 "${CFG_FILE}"
