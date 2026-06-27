# Roadmap — Ensamble delivery slices

## Slice 1 — API skeleton + Ollama recommend (MVP)

**Goal:** FastAPI app with health check and `/recommend` calling Ollama `qwen2.5`, rules doc in system prompt, Pydantic schemas per `docs/GAME-STATE-SCHEMA.md`, fixture test, `requirements.txt`, `.env.example`.

**Boundaries:** No UI. No persistence. No expansion rules. Vertical slice only.

## Slice 2 — Rules validation + prompt hardening

**Goal:** Pre-validate obvious illegal builds (distance rule, affordability, piece limits) before LLM call; structured JSON output with retry; expand pytest with illegal-state cases.

## Slice 3 — CLI client

**Goal:** `python -m cli recommend --file state.json` for table-side use; pretty-print 3 COAs.

## Slice 4 — Sample library + docs

**Goal:** `examples/` folder with 5 annotated game states and expected COA themes; API OpenAPI polish.

## Slice 5 — Optional Streamlit UI (if approved)

**Goal:** Form-based game state entry + recommend button.
