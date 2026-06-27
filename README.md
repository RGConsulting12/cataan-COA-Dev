# Catan COA Dev

LLM-assisted **courses of action (COA)** advisor for [*Catan*](https://www.catan.com/) (formerly Settlers of Catan). Given a structured snapshot of the current game state, the app returns **three ranked recommended moves** grounded in the official rules.

## Stack

| Layer | Choice |
|-------|--------|
| API | FastAPI |
| LLM | [Ollama](https://ollama.com) — default model `qwen2.5` |
| Rules context | `docs/CATAN-OFFICIAL-RULES.md` |
| Dev pipeline | [Ensamble](https://github.com/RGConsulting12/openclaw-hub/tree/master/projects/Ensamble) |

## Prerequisites

- Python 3.11+
- Ollama running locally (`ollama serve`)
- Model: `ollama pull qwen2.5`

## Quick start

```bash
# Start Ollama (from openclaw-hub)
~/openclaw-hub/scripts/ollama-serve.sh
~/openclaw-hub/scripts/wait-for-ollama.sh
ollama pull qwen2.5

# App
cp .env.example .env
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

## Run tests

```bash
source .venv/bin/activate
pip install -r requirements.txt
pytest
```

Integration tests (`test_recommend_end_to_end_with_ollama`) call a live local Ollama instance when available; they are skipped if Ollama or `qwen2.5` is not running.

## API

`POST /recommend` — accept game state JSON (see `docs/GAME-STATE-SCHEMA.md`), return exactly 3 ranked COAs with rationale.

`GET /health` — service and Ollama connectivity check (502 when Ollama is down).

## Docs

- `docs/IDEA-BRIEF.md` — product intent
- `docs/PRD.md` — requirements
- `docs/CATAN-OFFICIAL-RULES.md` — rules reference for the LLM
- `ROADMAP.md` — Ensamble delivery slices

## Repository

https://github.com/RGConsulting12/cataan-COA-Dev
