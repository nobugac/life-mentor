# Prompt Library

Naming
- Use versioned filenames: <domain>_<purpose>_vN.txt
- Store new variants alongside old ones for A/B comparison.

Files
- vision_daily_raw_capture_v1.txt: vision extraction prompt (daily state).
- morning_suggestions_v1.txt: morning tasks + advice (JSON output).
- evening_summary_v1.txt: evening journal analysis (JSON output).

Notes
- Keep prompt versions stable; track updates in docs/project_docs/IMPLEMENTATION_LOG.md.
- Save raw LLM responses with prompt_version for audit.
