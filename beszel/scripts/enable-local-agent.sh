#!/usr/bin/env bash
# Enable Beszel local agent credentials in .env (universal token + hub public key).
#
# Prerequisites:
#   - hub is running (docker compose up -d)
#   - admin account exists in the web UI
#
# Usage:
#   ./scripts/enable-local-agent.sh
#   BESZEL_ADMIN_EMAIL=you@example.com BESZEL_ADMIN_PASSWORD=secret ./scripts/enable-local-agent.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${STACK_DIR}/.env"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}. Run: cp .env.example .env" >&2
  exit 1
fi

# shellcheck disable=SC1091
source "${ENV_FILE}"

HUB_URL="${BESZEL_APP_URL:-http://127.0.0.1:${BESZEL_PORT:-8090}}"
HUB_URL="${HUB_URL%/}"
ADMIN_EMAIL="${BESZEL_ADMIN_EMAIL:-}"
ADMIN_PASSWORD="${BESZEL_ADMIN_PASSWORD:-}"

if [[ -z "${ADMIN_EMAIL}" || -z "${ADMIN_PASSWORD}" ]]; then
  read -r -p "Beszel admin email: " ADMIN_EMAIL
  read -r -s -p "Beszel admin password: " ADMIN_PASSWORD
  echo
fi

auth_json="$(mktemp)"
trap 'rm -f "${auth_json}"' EXIT

curl -fsS \
  -X POST "${HUB_URL}/api/collections/users/auth-with-password" \
  -H "Content-Type: application/json" \
  -d "{\"identity\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASSWORD}\"}" \
  >"${auth_json}"

AUTH_TOKEN="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])' <"${auth_json}")"

PUBLIC_KEY="$(curl -fsS \
  -H "Authorization: ${AUTH_TOKEN}" \
  "${HUB_URL}/api/beszel/getkey" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["key"])')"

UNIVERSAL_TOKEN="$(curl -fsS \
  -H "Authorization: ${AUTH_TOKEN}" \
  "${HUB_URL}/api/beszel/universal-token?enable=1" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')"

upsert_env() {
  local key="$1"
  local value="$2"
  local escaped="${value//\\/\\\\}"
  escaped="${escaped//\"/\\\"}"
  if [[ "${value}" == *" "* ]]; then
    value="\"${escaped}\""
  fi
  local tmp
  tmp="$(mktemp)"
  if grep -q "^${key}=" "${ENV_FILE}"; then
    sed "s|^${key}=.*|${key}=${value}|" "${ENV_FILE}" >"${tmp}"
  else
    cat "${ENV_FILE}" >"${tmp}"
    printf '\n%s=%s\n' "${key}" "${value}" >>"${tmp}"
  fi
  mv "${tmp}" "${ENV_FILE}"
}

upsert_env "BESZEL_AGENT_HUB_URL" "${HUB_URL}"
upsert_env "BESZEL_AGENT_KEY" "${PUBLIC_KEY}"
upsert_env "BESZEL_AGENT_TOKEN" "${UNIVERSAL_TOKEN}"

echo "Updated ${ENV_FILE}:"
echo "  BESZEL_AGENT_HUB_URL=${HUB_URL}"
echo "  BESZEL_AGENT_KEY=<public key>"
echo "  BESZEL_AGENT_TOKEN=<universal token enabled>"
echo
echo "Start the local agent:"
echo "  docker compose --profile local-agent up -d"
