#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8010}"
DATE="${DATE:-$(date +%F)}"

echo "Base URL: ${BASE_URL}"
echo "Date: ${DATE}"

echo "==> /alignment (debug)"
curl -s -X POST "${BASE_URL}/alignment" \
  -H "Content-Type: application/json" \
  -d "{\"date\":\"${DATE}\",\"debug\":true}" | python3 -m json.tool

echo
echo "==> /morning (debug)"
curl -s -X POST "${BASE_URL}/morning" \
  -H "Content-Type: application/json" \
  -d "{\"date\":\"${DATE}\",\"debug\":true,\"text\":\"ping\"}" | python3 -m json.tool

echo
echo "==> /evening (debug)"
curl -s -X POST "${BASE_URL}/evening" \
  -H "Content-Type: application/json" \
  -d "{\"date\":\"${DATE}\",\"debug\":true,\"journal\":\"ping\"}" | python3 -m json.tool
