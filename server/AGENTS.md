# Repository Guidelines

## Project Structure & Module Organization
- `core/`: domain logic for advice, goals, state, and journaling.
- `integrations/`: adapters for LLMs, Obsidian IO, and config loading.
- `config/config.yaml`: absolute paths and feature flags (update for your vault).
- `prompts/`: prompt templates used by chat/UI flows.
- `data/`, `debug/`, `vision_images/`, `vision_results/`, `.backup/`: runtime outputs and caches.
- Entry points: `manage_day.py` (daily note updates), `chat_bot.py` (intent parsing), `ui_server.py` and `dev_ui.py` (web UI); `scripts/` holds test flows and env helpers, `test_data/` has sample inputs.

## Build, Test, and Development Commands
- `./run_chat.sh [args]`: run the CLI chat flow with env setup.
- `./run_ui.sh --port 8000`: start the HTTP UI server.
- `./run_ui_dev.sh --port 8000`: run the UI with auto-reload on file changes.
- `python manage_day.py --date 2026-01-01 --morning --text "..."`: direct daily update.
- `pip install openai`: required for LLM calls (per `chat_bot.py` and `ui_server.py`).
- `source ./set_env.sh`: load API keys; test scripts use `scripts/env.sh`.

## Coding Style & Naming Conventions
- Python: 4-space indentation, type hints where present, small functions, explicit IO.
- Naming: `snake_case` for functions/vars, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants.
- Keep config keys stable; add new keys rather than repurposing existing ones.

## Testing Guidelines
- No unit test framework; use script-driven flows in `scripts/`:
- `scripts/test_mvp.sh 2026-01-02`
- `scripts/test_week2.sh 2026-01-02`
- Tests write to the Obsidian vault paths plus `data/` and `.backup/`; review outputs before reruns.

## Commit & Pull Request Guidelines
- Git history is not available in this workspace; use short imperative summaries (e.g., "Add vision cache").
- PRs should include purpose, behavior changes, test commands run, and note updates to prompts or `config/config.yaml`. Add screenshots for UI changes.

## Security & Configuration Tips
- Keep API keys out of source; use env vars (`ARK_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`).
- Set `LIFE_MENTOR_CONFIG` when using a custom config path.
