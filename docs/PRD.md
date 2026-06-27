# Product requirements — Catan COA Advisor

## Summary

Local FastAPI service that recommends **three ranked courses of action** for the active player in a base-game **Catan** match, using **Ollama (qwen2.5)** and `docs/CATAN-OFFICIAL-RULES.md` as grounding context.

## Non-goals

- Digital board simulator
- Expansion rules
- Multi-user accounts or cloud hosting (v1)

## Users and permissions

- **Operator:** runs API locally; no auth in v1

## Core workflows

1. **Health check** — verify API and Ollama (`qwen2.5`) are up.
2. **Recommend** — submit game state → receive 3 COAs with rationale.
3. **Pre-LLM rules validation** — before Ollama is invoked, obvious illegal moves in `proposed_actions` (or JSON `notes`) are rejected with HTTP 422 and structured errors (`field`, `code`, `message`, `rules_ref`). Legal states proceed to the LLM; malformed LLM JSON is retried up to 3 times, then HTTP 502.

## API contract (MVP)

### `GET /health`

```json
{
  "status": "ok",
  "ollama": "ok",
  "model": "qwen2.5"
}
```

### `POST /recommend`

**Request:** `GameState` (see `docs/GAME-STATE-SCHEMA.md`)

**Response:**

```json
{
  "active_player": "red",
  "recommendations": [
    {
      "rank": 1,
      "action_type": "build_city",
      "summary": "Upgrade settlement on 6 ore for doubled production.",
      "details": { "vertex_id": "v12", "cost": { "grain": 2, "ore": 3 } },
      "rationale": "...",
      "rules_refs": ["§6 Building costs", "§4 Turn structure"]
    }
  ]
}
```

Exactly **3** recommendations, ranks 1–3, all must be legal per rules doc.

## Data

- **Entities:** none persisted in v1 (stateless API)
- **Sample inputs:** `tests/fixtures/sample_game_state.json`

## Integrations

| System | Purpose |
|--------|---------|
| Ollama | LLM inference |
| Rules markdown | System prompt context |

## Environment

| Variable | Default |
|----------|---------|
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` |
| `OLLAMA_MODEL` | `qwen2.5` |
| `RULES_PATH` | `docs/CATAN-OFFICIAL-RULES.md` |

## Acceptance criteria

- [ ] `GET /health` returns 200 when Ollama is running with configured model
- [ ] `POST /recommend` returns 3 COAs for fixture game state
- [ ] Invalid game state returns 422 with clear validation errors
- [x] Pre-LLM rules validation rejects obvious illegal moves (slice 2)
- [ ] `pytest` passes
- [ ] README documents run instructions

## Open questions

- ~~Add lightweight rules validator before LLM call? (slice 2)~~ — implemented in slice 2

## Human gates

- [x] PRD approved for slice 1 bootstrap
- [ ] Schema v1 frozen after slice 1 review
