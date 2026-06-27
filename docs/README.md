# Documentation index

| Document | Purpose |
|----------|---------|
| [IDEA-BRIEF.md](IDEA-BRIEF.md) | Product intent and scope |
| [PRD.md](PRD.md) | Requirements |
| [GAME-STATE-SCHEMA.md](GAME-STATE-SCHEMA.md) | JSON schema for `POST /recommend` and nested `GameSession.state` |
| [CATAN-OFFICIAL-RULES.md](CATAN-OFFICIAL-RULES.md) | Rules reference injected into LLM prompts |

## Sample game states

Curated, schema-valid examples for manual testing and onboarding live in [`../examples/README.md`](../examples/README.md):

- `sample1_early_expansion.json` — early roads vs settlement tempo
- `sample2_dev_card_engine.json` — dev cards vs city production
- `sample3_port_trade.json` — 2:1 port and trade politics
- `sample4_robber_phase.json` — robber placement and steal
- `sample5_endgame_race.json` — route to 10 VP

```bash
python -m cli recommend --file examples/sample1_early_expansion.json
```

## Game sessions (slice 5)

**Storage:** JSON files under `data/sessions/{id}.json` — no database, ORM, or external persistence service.

A **GameSession** wraps a validated **GameState** with session metadata:

| Field | Type | Notes |
|-------|------|-------|
| `id` | string (UUID) | Immutable; file name |
| `turn_number` | int ≥ 1 | Display turn for UI header |
| `label` | string? | Optional human label |
| `source_fixture` | string? | Set when created from `examples/` |
| `state` | GameState | Full board snapshot (same schema as `/recommend`) |
| `created_at` / `updated_at` | ISO datetime | Server-managed |

### API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/examples` | List `examples/sample*.json` fixture names |
| `POST` | `/sessions` | Create from `fixture` or inline `state` |
| `GET` | `/sessions/{id}` | Load session (404 if missing) |
| `PATCH` | `/sessions/{id}` | Update `turn_number`, `label`, patchable `state` fields |
| `POST` | `/sessions/{id}/recommend` | Run recommend engine on stored `state` |

**PATCH** accepts only documented fields; extra keys (e.g. `id`, `board`) return **422**.

### Operator flow

1. Start API: `uvicorn app.main:app --reload --port 8085`
2. Open [http://127.0.0.1:8085/ui](http://127.0.0.1:8085/ui)
3. Pick an example fixture → **Create session** (calls `POST /sessions`)
4. UI fetches `GET /sessions/{id}`, renders board/timeline, then `POST /sessions/{id}/recommend` for three read-only COA cards
5. Switch sessions or **Reload** to refresh from the API (no client-side move application)

### Example session JSON (abbreviated)

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "turn_number": 1,
  "label": "sample1 early expansion",
  "source_fixture": "sample1_early_expansion.json",
  "state": {
    "phase": "main",
    "active_player": "orange",
    "dice_rolled": true,
    "players": [],
    "board": {},
    "bank": {}
  },
  "created_at": "2026-06-27T12:00:00+00:00",
  "updated_at": "2026-06-27T12:00:00+00:00"
}
```

Interactive API reference: run the app and open `/docs`.
