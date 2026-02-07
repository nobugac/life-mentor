# LifeMentor — Persistent AI Life Coach

**Gemini API Hackathon 2026 Submission**

LifeMentor gives ordinary people sustained AI attention for personal growth — not one-off replies, but a continuous feedback loop grounded in your own values, goals, and real-world data.

## The Problem

Generic AI stays broad because it lacks persistent personal context. You get motivational one-liners, not actionable guidance that adapts to your life.

## How It Works

```
You handwrite:  Value → Goal → Project  (in markdown, you own it)
Auto-collected:  Phone screen time + Smartwatch sleep/HRV/stress
Gemini analyzes: Pattern recognition + value-aligned micro-adjustments
Daily loop:      Morning advice → Daytime records → Evening reflection → Tomorrow's plan
```

### Daily Flow

| Page | What happens | Gemini's role |
|------|-------------|---------------|
| **Alignment** | See your data patterns + select main value | Gemini analyzes multi-day trends, generates value board and focus experiment |
| **Today** | One-line check-in → get today's practice | Gemini generates a micro-adjustment aligned to your main value + optional inspirations for other values |
| **Record** | Log anything during the day | Gemini parses intent and saves structured context for night analysis |
| **Night** | Quick mood + reflection → mirror + tomorrow's plan | Gemini synthesizes all daily data into adaptive next-day guidance |

### Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────┐
│   Obsidian UI   │────▶│  FastAPI      │────▶│  Gemini API │
│   (Markdown +   │◀────│  Server       │◀────│  3 Flash    │
│    dataviewjs)  │     │  (Python)     │     └─────────────┘
└─────────────────┘     └──────┬───────┘
                               │
                    ┌──────────┴──────────┐
                    │  Local Data Store   │
                    │  state/ records/    │
                    │  llm/ diary/        │
                    └─────────────────────┘
```

## Gemini API Integration

LifeMentor uses **Gemini 3 Flash (`gemini-3-flash`)** via the OpenAI-compatible endpoint for all four core features:

1. **Alignment Analysis** — Multi-day pattern recognition across sleep, screen time, HRV, and stress data. Generates value board summaries and 7-day focus experiments.
2. **Morning Micro-Adjustment** — Given user check-in + historical data, generates one actionable practice aligned to the primary value, plus optional inspirations for secondary values.
3. **Record Parsing** — Real-time intent classification and structured data extraction from free-form user input.
4. **Evening Reflection** — Synthesizes daily records, device data, task completion, and mood into a mirror-style reflection with adaptive tomorrow suggestions.

All prompts are version-controlled in `server/prompts/` and outputs are saved to `server/data/llm/` for full traceability.

## Key Differentiators

- **Value-driven, not generic** — Users handwrite their own Values, Goals, and Projects. AI advice is always anchored to these.
- **Persistent personal context** — Continuous data from phone + smartwatch builds a longitudinal profile, not just one conversation.
- **Local-first, user-owned** — All data stored as local markdown files. Editable, portable, no cloud lock-in.
- **Micro-adjustment loops** — Daily feedback cycle with difficulty adaptation (lower/raise based on completion).

## Quick Start

```bash
# 1. Clone
git clone https://github.com/nobugac/life-mentor.git
cd life-mentor

# 2. Set up server
cd server
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Set Gemini API key
export GEMINI_API_KEY="your-key-here"

# 4. Start server
python ui_server.py  # runs on http://127.0.0.1:8010

# 5. Open demo vault in Obsidian
# Open Obsidian → Open Vault → select demo_vault/
```

## Project Structure

```
├── server/                  # FastAPI backend
│   ├── server/app.py        # API endpoints
│   ├── core/llm_analyzer.py # Gemini integration logic
│   ├── integrations/        # LLM client, config
│   ├── prompts/             # Version-controlled prompts (English)
│   └── config/              # Server configuration
├── demo_vault/              # Obsidian vault (open this)
│   ├── LifeMentor_Extra/    # UI pages (dataviewjs)
│   ├── values/              # User-written values
│   ├── goals/               # User-written goals
│   ├── projects/            # Active experiments
│   └── diary/               # Daily + weekly notes with device data
└── obsidian-plugin/         # Bridge plugin for server communication
```

## Tech Stack

- **LLM**: Gemini 3 Flash (`gemini-3-flash`) via OpenAI-compatible endpoint
- **Backend**: Python, FastAPI
- **Frontend**: Obsidian + dataviewjs (markdown-native UI)
- **Data**: Local JSON state files + markdown diary
- **Devices**: Phone screen time (vision), Garmin smartwatch (sleep/HRV/stress)

## License

MIT
