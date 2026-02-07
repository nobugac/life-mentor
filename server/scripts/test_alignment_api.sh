#!/usr/bin/env sh
set -eu

BASE_URL="${BASE_URL:-http://127.0.0.1:8010}"
TOKEN="${TOKEN:-}"
DATE="${1:-$(date +%Y-%m-%d)}"

if ! command -v curl >/dev/null 2>&1; then
  echo "curl not found"
  exit 1
fi

post_json() {
  local path="$1"
  local payload="$2"
  echo "==> POST ${path}"
  set -- -sS -H "Content-Type: application/json" -d "${payload}"
  if [ -n "${TOKEN}" ]; then
    set -- "$@" -H "X-UI-Token: ${TOKEN}" -H "Authorization: Bearer ${TOKEN}"
  fi
  set -- "$@" "${BASE_URL}${path}"
  tmp_file="$(mktemp 2>/dev/null || mktemp -t lm_api)"
  status="$(curl "$@" -o "${tmp_file}" -w "%{http_code}")"
  echo "HTTP ${status}"
  if command -v python3 >/dev/null 2>&1; then
    python3 -m json.tool < "${tmp_file}" || cat "${tmp_file}"
  else
    cat "${tmp_file}"
  fi
  rm -f "${tmp_file}"
  echo
}

post_json "/alignment" "{\"date\":\"${DATE}\"}"
post_json "/morning" "{\"date\":\"${DATE}\",\"text\":\"today quick note\"}"
post_json "/evening" "{\"date\":\"${DATE}\",\"journal\":\"evening summary\",\"did\":\"yes\"}"
