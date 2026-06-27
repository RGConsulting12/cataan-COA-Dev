# Roadmap — Ensamble delivery slices

## Completed

| Slice | Goal |
|-------|------|
| **1** | FastAPI `/health` + `/recommend`, Ollama `qwen2.5`, rules doc, Pydantic schemas |
| **2** | Pre-LLM rules validation, structured JSON retry, illegal-state tests |
| **3** | CLI `python -m cli recommend --file state.json` |
| **4** | `examples/` sample library (5 game states), OpenAPI polish |

---

## Slice 5 — Game session API + minimal web UI (in progress)

**Goal:** Persistent game flow with board visualization and side-by-side COA cards.

### Backend
- `GameSession` model: `session_id`, board (fixed after setup), players, turn log, current state snapshot
- Session API:
  - `POST /sessions` — create from board template or example fixture
  - `GET /sessions/{id}` — current state + metadata
  - `PATCH /sessions/{id}` — advance phase, update resources/pieces, append turn log entry
  - `POST /sessions/{id}/recommend` — COAs for current session state (wraps existing recommend logic)
- File-based persistence (JSON under `data/sessions/` or similar); no DB in this slice
- Default API port **8085** (document in README)

### Frontend (minimal web UI)
- Static or lightweight SPA served by FastAPI (`/ui` or `static/`)
- **Hex board viewer** — render from `board.hexes`, `vertices`, `edges` (SVG acceptable)
- **Turn timeline** — show turn number, phase, active player, last roll
- **COA panel** — three side-by-side cards (rank, action_type, summary, rationale) from `/recommend`
- **Session header** — game name, turn count, “board locked at setup” messaging
- Read-only recommend in this slice (no tap-to-apply / ghost overlays yet)

### Boundaries
- Base Catan only; no expansions
- No auth, no cloud deploy
- No board randomization wizard (slice 6)
- No COA apply / ghost overlays (slice 5c)

### Tests
- Session CRUD + recommend integration tests
- UI smoke test optional (or manual checklist in README)

---

## Slice 6 — Setup wizard

**Goal:** New-game flow with random board generator (terrain + number tokens per official rules), initial placement tracking.

---

## Slice 7 — Interactive COA apply

**Goal:** Ghost overlays on board per COA; “Apply” updates session with rules validation before commit.

---

## Slice 8 — Optional enhancements

- Streamlit ops dashboard or import from external tools
- Photo / OCR board capture (research only unless approved)
