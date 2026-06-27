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
uvicorn app.main:app --reload --port 8085
```

## Run tests

```bash
source .venv/bin/activate
pip install -r requirements.txt
pytest
```

Integration tests (`test_recommend_end_to_end_with_ollama`) call a live local Ollama instance when available; they are skipped if Ollama or `qwen2.5` is not running.

## CLI

Table-side terminal client for ranked COA recommendations. Requires the API running (see Quick start).

```bash
source .venv/bin/activate
pip install -r requirements.txt

# Start the API in another terminal:
# uvicorn app.main:app --reload --port 8085

python -m cli recommend --file tests/fixtures/sample_game_state.json
```

### Example library

Five annotated Catan game states live in [`examples/`](examples/README.md) for demo, onboarding, and manual API/CLI validation. Each file targets a distinct strategic decision (early expansion, dev-card engine, port trading, robber phase, endgame race). See [`examples/README.md`](examples/README.md) for scenario themes and expected COA patterns.

```bash
python -m cli recommend --file examples/sample1_early_expansion.json
```

### Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `recommend` | yes | — | Subcommand: fetch ranked COAs for a game state file |
| `--file PATH` | yes | — | Path to game state JSON (see `docs/GAME-STATE-SCHEMA.md`) |
| `--base-url URL` | no | `http://127.0.0.1:8085` | API base URL for remote hosts |

### Sample output

```text
Active player: red

1. [build_city] Upgrade settlement on strong ore hex. (Rationale:
   Doubles ore production on a high-probability number.)

2. [maritime_trade] Trade grain for ore at 4:1. (Rationale: Sets up a
   city upgrade next turn.)

3. [end_turn] End turn if no better trades appear. (Rationale: Preserves
   resources when no build is affordable.)
```

Long rationales wrap at 72 columns for readability.

### Errors

The CLI exits with a nonzero status and prints a clear message to stderr when:

- **File not found** — missing or unreadable `--file` path
- **Invalid JSON** — malformed game state file
- **Validation error (HTTP 422)** — game state or proposed actions rejected by the API
- **Service error (HTTP 502)** — Ollama unavailable or invalid LLM response
- **Network error** — cannot connect to `--base-url` (e.g. API not running)

Example:

```bash
python -m cli recommend --file NONEXISTENT.json
# File not found: NONEXISTENT.json

python -m cli recommend --file tests/fixtures/sample_game_state.json --base-url http://localhost:9999
# Cannot connect to API at http://localhost:9999. Is the server running?
```

## API

`POST /recommend` — accept game state JSON (see `docs/GAME-STATE-SCHEMA.md`), return exactly 3 ranked COAs with rationale.

Before calling Ollama, the API runs **rules pre-validation** on the request body. Obvious illegal moves (distance rule, affordability, piece limits, robber placement, dev-card same-turn) are rejected with **HTTP 422** and a structured error list:

```json
[
  {
    "field": "proposed_actions[0].vertex_id",
    "code": "distance_rule_violation",
    "message": "Settlement cannot be placed adjacent to existing settlement at v1",
    "rules_ref": "§6 Building costs — Placement rules (distance rule)"
  }
]
```

Optional `proposed_actions` (or the same array inside JSON `notes`) describe candidate moves to validate; legal states with no proposed actions pass through to the LLM. Malformed LLM JSON is retried up to 3 times before **HTTP 502**.

`GET /health` — service and Ollama connectivity check (502 when Ollama is down).

Interactive OpenAPI reference: `http://127.0.0.1:8080/docs` (tags, descriptions, and response examples for `/health` and `/recommend`).

## Docs

- `docs/IDEA-BRIEF.md` — product intent
- `docs/PRD.md` — requirements
- `docs/CATAN-OFFICIAL-RULES.md` — rules reference for the LLM
- `docs/GAME-STATE-SCHEMA.md` — request JSON schema
- `examples/README.md` — curated sample game states for demo and validation
- `ROADMAP.md` — Ensamble delivery slices

## Repository

https://github.com/RGConsulting12/cataan-COA-Dev
