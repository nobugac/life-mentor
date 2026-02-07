#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_DATA_DIR="${TEST_DATA_DIR:-${ROOT_DIR}/test_data/morning}"
TEST_IMAGES_DIR="${TEST_IMAGES_DIR:-${TEST_DATA_DIR}/images}"
TEST_TEXT_DIR="${TEST_TEXT_DIR:-${TEST_DATA_DIR}/text}"
# Optional: declare image paths here (absolute or relative to repo root).
# Leave empty to read from test_data/morning/images.
IMAGE_PATHS=(
  # "${ROOT_DIR}/test_data/morning/images/example1.jpg"
  # "${ROOT_DIR}/test_data/morning/images/example2.jpg"
)

if [[ -f "${ROOT_DIR}/scripts/env.sh" ]]; then
  # shellcheck source=/dev/null
  source "${ROOT_DIR}/scripts/env.sh"
fi

get_cfg() {
  python3 - <<'PY' "$1"
from integrations.config import get_config
import sys
key = sys.argv[1]
print(get_config().get(key, ""))
PY
}

DATE_TEXT="${DATE_TEXT:-$(date +%F)}"
DATE_IMAGE="${DATE_IMAGE:-$(python3 - <<'PY'
import datetime as dt
print((dt.date.today() - dt.timedelta(days=1)).isoformat())
PY
)}"

VISION_PROMPT_PATH="${VISION_PROMPT_PATH:-$(get_cfg vision_prompt_path)}"
MORNING_PROMPT_PATH="${MORNING_PROMPT_PATH:-$(get_cfg morning_prompt_path)}"
DEBUG_VISION_DIR="${DEBUG_VISION_DIR:-$(get_cfg debug_vision_results_dir)}"
DEBUG_STATE_DIR="${DEBUG_STATE_DIR:-$(get_cfg debug_state_dir)}"
DEBUG_LLM_DIR="${DEBUG_LLM_DIR:-$(get_cfg debug_llm_dir)}"

VISION_PROVIDER="${VISION_PROVIDER:-doubao}"
VISION_MODEL="${VISION_MODEL:-doubao-seed-1-6-vision-250815}"
MORNING_PROVIDER="${MORNING_PROVIDER:-$(get_cfg morning_provider)}"
MORNING_MODEL="${MORNING_MODEL:-$(get_cfg morning_model)}"
PRINT_PROMPT="${PRINT_PROMPT:-0}"
PRINT_PROMPT_FLAG=()
if [[ "${PRINT_PROMPT}" == "1" ]]; then
  PRINT_PROMPT_FLAG=(--print-prompt)
fi

TEXT_INPUT="${TEXT_INPUT:-}"

read_text_file() {
  local path="$1"
  if [[ -f "${path}" ]]; then
    sed 's/\r$//' "${path}"
  fi
}

TEXT_FILE="${TEXT_FILE:-${TEST_TEXT_DIR}/input.txt}"

if [[ -z "${TEXT_INPUT}" ]]; then
  TEXT_INPUT="$(read_text_file "${TEXT_FILE}")"
fi

IMAGES=()
if [[ "${#IMAGE_PATHS[@]}" -gt 0 ]]; then
  IMAGES=("${IMAGE_PATHS[@]}")
elif [[ "$#" -gt 0 ]]; then
  IMAGES=("$@")
else
  if [[ -d "${TEST_IMAGES_DIR}" ]]; then
    while IFS= read -r path; do
      IMAGES+=("${path}")
    done < <(find "${TEST_IMAGES_DIR}" -maxdepth 1 -type f ! -name ".*" | sort)
  fi
fi

if [[ "${#IMAGES[@]}" -eq 0 ]]; then
  echo "No images found. Put test images in ${TEST_IMAGES_DIR} or pass image paths." >&2
  exit 1
fi

echo "Images: ${IMAGES[*]}"
echo "Text date: ${DATE_TEXT}"
echo "Image date: ${DATE_IMAGE}"
echo "Text file: ${TEXT_FILE}"
echo "Vision prompt: ${VISION_PROMPT_PATH}"
echo "Morning prompt: ${MORNING_PROMPT_PATH}"

python3 "${ROOT_DIR}/scripts/debug_vision_prompt.py" \
  --images "${IMAGES[@]}" \
  --date "${DATE_IMAGE}" \
  --prompt "${VISION_PROMPT_PATH}" \
  --provider "${VISION_PROVIDER}" \
  --model "${VISION_MODEL}" \
  --update-state \
  --output-dir "${DEBUG_VISION_DIR}" \
  --state-dir "${DEBUG_STATE_DIR}"

python3 "${ROOT_DIR}/scripts/debug_morning_prompt.py" \
  --date "${DATE_TEXT}" \
  --state-date "${DATE_IMAGE}" \
  --prompt "${MORNING_PROMPT_PATH}" \
  --provider "${MORNING_PROVIDER}" \
  --model "${MORNING_MODEL}" \
  --text "${TEXT_INPUT}" \
  "${PRINT_PROMPT_FLAG[@]}" \
  --output-dir "${DEBUG_LLM_DIR}"
