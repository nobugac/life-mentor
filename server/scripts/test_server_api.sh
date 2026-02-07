#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${BASE_URL:-http://127.0.0.1:8010}"
DATE="${DATE:-$(date +%F)}"
DEVICE_ID="${DEVICE_ID:-android-test}"
UPDATE_NOTE="${UPDATE_NOTE:-0}"
SKIP_PATH_CHECK="${SKIP_PATH_CHECK:-0}"
SKIP_GARMIN="${SKIP_GARMIN:-0}"

export ROOT_DIR

{
  read -r DATA_ROOT
  read -r MOBILE_ROOT
  read -r STATE_ROOT
} < <(python3 - <<'PY'
import os
from pathlib import Path
import sys

root = Path(os.environ["ROOT_DIR"])
sys.path.insert(0, str(root))
from integrations.config import get_config  # noqa: E402

cfg = get_config()
data_root = Path(str(cfg.get("data_root", root / "data"))).expanduser()
mobile_root = Path(str(cfg.get("mobile_data_root", data_root / "mobile"))).expanduser()
state_root = Path(str(cfg.get("state_root", data_root / "state"))).expanduser()
print(data_root)
print(mobile_root)
print(state_root)
PY
)
DATE_COMPACT="${DATE//-/}"

request_json() {
  local url="$1"
  local expected="$2"
  local payload="$3"
  local response body status
  if ! response="$(curl -sS -w '\n%{http_code}' -H "Content-Type: application/json" -d "${payload}" "${url}")"; then
    echo "Request failed: ${url}" >&2
    return 1
  fi
  body="${response%$'\n'*}"
  status="${response##*$'\n'}"
  if [[ "${status}" != "${expected}" ]]; then
    echo "HTTP ${status} from ${url}" >&2
    echo "${body}" >&2
    return 1
  fi
  if [[ -z "${body}" ]]; then
    echo "Empty response body from ${url}" >&2
    return 1
  fi
  if ! printf '%s' "${body}" | python3 -c 'import json,sys; json.load(sys.stdin)' >/dev/null 2>&1; then
    echo "Invalid JSON from ${url}" >&2
    echo "${body}" >&2
    return 1
  fi
  printf '%s' "${body}"
}

extract_fields() {
  python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get("file") or ""); print(data.get("state") or ""); print(data.get("note") or "")'
}

echo "Base URL: ${BASE_URL}"
echo "Date: ${DATE}"
echo "Data root: ${DATA_ROOT}"
echo "Mobile root: ${MOBILE_ROOT}"
echo "State root: ${STATE_ROOT}"

echo "==> Test 1: /ingest OK"
PAYLOAD_OK="$(cat <<JSON
{
  "deviceId": "${DEVICE_ID}",
  "rangeStart": "${DATE}T00:00:00Z",
  "rangeEnd": "${DATE}T23:59:59Z",
  "generatedAt": "${DATE}T23:59:59Z",
  "usageTotalMs": 3600000,
  "usageByApp": [
    { "packageName": "com.android.chrome", "totalTimeMs": 1200000 },
    { "packageName": "com.twitter.android", "totalTimeMs": 600000 }
  ],
  "health": {}
}
JSON
)"

if ! BODY_OK="$(request_json "${BASE_URL}/ingest" 200 "${PAYLOAD_OK}")"; then
  echo "Test 1 failed." >&2
  exit 1
fi
{
  read -r FILE_NAME
  read -r STATE_PATH
  read -r NOTE_PATH
} < <(printf '%s' "${BODY_OK}" | extract_fields)

if [[ "${SKIP_PATH_CHECK}" != "1" ]]; then
  if [[ -n "${FILE_NAME}" ]]; then
    EXPECTED_RAW="${MOBILE_ROOT}/${DATE_COMPACT}/${FILE_NAME}"
    if [[ ! -f "${EXPECTED_RAW}" ]]; then
      echo "Missing mobile payload: ${EXPECTED_RAW}"
      exit 1
    fi
  fi
  if [[ -n "${STATE_PATH}" && ! -f "${STATE_PATH}" ]]; then
    echo "Missing state file: ${STATE_PATH}"
    exit 1
  fi
fi

echo "==> Test 2: /ingest schema error (missing deviceId)"
BAD_PAYLOAD="$(cat <<JSON
{
  "rangeStart": "${DATE}T00:00:00Z",
  "rangeEnd": "${DATE}T23:59:59Z",
  "generatedAt": "${DATE}T23:59:59Z",
  "usageTotalMs": 1000,
  "usageByApp": [],
  "health": {}
}
JSON
)"
if ! request_json "${BASE_URL}/ingest" 422 "${BAD_PAYLOAD}" >/dev/null; then
  echo "Test 2 failed." >&2
  exit 1
fi

if [[ "${UPDATE_NOTE}" == "1" ]]; then
  echo "==> Test 3: /ingest?update_note=true"
  if ! BODY_NOTE="$(request_json "${BASE_URL}/ingest?update_note=true" 200 "${PAYLOAD_OK}")"; then
    echo "Test 3 failed." >&2
    exit 1
  fi
  {
    read -r _NOTE_FILE
    read -r _NOTE_STATE
    read -r NOTE_PATH
  } < <(printf '%s' "${BODY_NOTE}" | extract_fields)
  if [[ "${SKIP_PATH_CHECK}" != "1" && -n "${NOTE_PATH}" && ! -f "${NOTE_PATH}" ]]; then
    echo "Missing note file: ${NOTE_PATH}"
    exit 1
  fi
else
  echo "==> Test 3: /ingest?update_note=true (skipped, set UPDATE_NOTE=1 to enable)"
fi

if [[ "${SKIP_GARMIN}" != "1" ]]; then
  echo "==> Test 4: /ingest/garmin OK"
  GARMIN_PAYLOAD="$(cat <<JSON
{
  "date": "${DATE}",
  "data": {}
}
JSON
)"
  if ! request_json "${BASE_URL}/ingest/garmin" 200 "${GARMIN_PAYLOAD}" >/dev/null; then
    echo "Test 4 failed." >&2
    exit 1
  fi
else
  echo "==> Test 4: /ingest/garmin (skipped, set SKIP_GARMIN=0 to enable)"
fi

echo "All tests passed."
