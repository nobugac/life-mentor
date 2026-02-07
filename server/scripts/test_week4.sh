#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PORT:-8010}"
DATE="${1:-$(date +%F)}"

if [[ -f "${ROOT_DIR}/scripts/env.sh" ]]; then
  # shellcheck source=/dev/null
  source "${ROOT_DIR}/scripts/env.sh"
fi

python3 "${ROOT_DIR}/ui_server.py" --port "${PORT}" >/tmp/life_mentor_ui.log 2>&1 &
PID=$!

cleanup() {
  kill "${PID}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

ready=0
for _ in {1..20}; do
  if curl -sf "http://localhost:${PORT}/" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 0.2
done

if [[ "${ready}" -ne 1 ]]; then
  echo "Server failed to start on port ${PORT}."
  tail -n 50 /tmp/life_mentor_ui.log || true
  exit 1
fi

request_json() {
  local url="$1"
  local payload="$2"
  local response body status
  response="$(curl -sS -w '\n%{http_code}' -H "Content-Type: application/json" -d "${payload}" "${url}")"
  body="${response%$'\n'*}"
  status="${response##*$'\n'}"
  if [[ "${status}" != "200" ]]; then
    echo "HTTP ${status} from ${url}"
    echo "${body}"
    exit 1
  fi
  if ! echo "${body}" | python3 -m json.tool >/dev/null 2>&1; then
    echo "Invalid JSON response from ${url}:"
    echo "${body}"
    exit 1
  fi
  echo "${body}" | python3 -m json.tool
}

request_json "http://localhost:${PORT}/morning" \
  "{\"date\":\"${DATE}\",\"text\":\"早间测试，散步10分钟\"}"

request_json "http://localhost:${PORT}/evening" \
  "{\"date\":\"${DATE}\",\"journal\":\"今天完成了本地 UI 测试，整体流程顺利。\"}"

echo "UI log: /tmp/life_mentor_ui.log"
