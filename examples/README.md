# Catan COA sample library

Curated game-state snapshots for **demo, onboarding, and manual validation** of the COA (courses of action) advisor. Each file is a complete, schema-valid JSON document you can POST to `POST /recommend` or pass to the CLI:

```bash
python -m cli recommend --file examples/sample1_early_expansion.json
```

See `docs/GAME-STATE-SCHEMA.md` for field definitions. These samples contain **no `proposed_actions`** — they exercise the LLM recommendation path only.

## Why these five?

The library covers the main **decision axes** where strong Catan play diverges and where COA trees branch:

| Axis | Sample |
|------|--------|
| Early spatial tempo | `sample1_early_expansion.json` |
| Dev-card vs visible VP | `sample2_dev_card_engine.json` |
| Trading & port politics | `sample3_port_trade.json` |
| Robber & interaction | `sample4_robber_phase.json` |
| Endgame win path | `sample5_endgame_race.json` |

Use them to sanity-check API/CLI behavior, compare model outputs across scenarios, and onboard developers without crafting ad-hoc JSON.

---

## Sample 1 — Early expansion (`sample1_early_expansion.json`)

| Field | Value |
|-------|-------|
| **Phase** | `main` (turn 3–4 feel) |
| **Theme** | Roads vs settlement timing |
| **Active player** | Orange (2 VP, lumber/brick surplus) |

**Scenario:** Fresh post-setup board. Orange rolled 11, holds wood and brick, and has one road aimed toward an open intersection (`v5`). Opponents are tied at 2 VP.

**Decision node:** Invest surplus in **roads** to secure contested production vs **banking** for a settlement next turn.

**Expected COA style:**

1. **Build road** toward `v5` — secure expansion and longest-road potential.
2. **Maritime trade** — convert excess lumber if a settlement is one resource away.
3. **End turn** — only if no affordable tempo gain; avoid wasteful trades.

**Pattern label:** `early_tempo` / `spatial_control`

---

## Sample 2 — Dev-card engine (`sample2_dev_card_engine.json`)

| Field | Value |
|-------|-------|
| **Phase** | `main` |
| **Theme** | Ore–wheat–sheep commitment |
| **Active player** | Red (5 visible VP + 1 hidden; holds largest army) |

**Scenario:** Mid-game. Red sits on strong ore/wheat numbers, already has largest army (2 knights), and can afford either another **development card** or a **city** upgrade on `v1`.

**Decision node:** Double down on **hidden VP / army race** vs **visible production** via city.

**Expected COA style:**

1. **Buy development card** — press largest-army lead and hidden VP upside.
2. **Build city** on `v1` — permanent ore/grain boost on pip-heavy hexes.
3. **Play knight** — only if robber denial on leader blue's ore is urgent (card held).

**Pattern label:** `dev_engine` / `production_vs_variance`

---

## Sample 3 — Port trade politics (`sample3_port_trade.json`)

| Field | Value |
|-------|-------|
| **Phase** | `main` |
| **Theme** | Brick cartel + 2:1 port |
| **Active player** | Brown (4 VP, brick-heavy hand) |

**Scenario:** Brown controls a **2:1 brick port** and sits on brick hex `h1` (8). Needs ore for a city while yellow leads at 6 VP on ore production.

**Decision node:** **Port trade** vs **player trade** — whom to trade with and whether to protect brick scarcity.

**Expected COA style:**

1. **Maritime trade** at 2:1 port — brick → ore without empowering yellow.
2. **Player trade** with purple — acceptable if terms don't help the leader.
3. **Build road/settlement** — if ore unavailable; extend before dumping brick at 4:1.

**Pattern label:** `cartel_port` / `trade_politics`

---

## Sample 4 — Robber phase (`sample4_robber_phase.json`)

| Field | Value |
|-------|-------|
| **Phase** | `robber` |
| **Theme** | Knight → robber + steal |
| **Active player** | Blue (5 VP, knight in hand) |

**Scenario:** Blue played a knight and must **move the robber** and **steal**. Red leads at 7 VP (including hidden VP) with a city on grain `h1` (9). White holds longest road and largest army.

**Decision node:** Block **VP leader** vs **production leader**; steal from whom on the target hex.

**Expected COA style:**

1. **Move robber** to `h1` or `h2` — deny red's grain/ore income.
2. **Steal from red** on placement — leader denial plus resource swing.
3. **Build** after robber — if hand supports road/settlement and robber isn't on blue's hexes.

**Pattern label:** `interaction_timing` / `leader_denial`

---

## Sample 5 — Endgame race (`sample5_endgame_race.json`)

| Field | Value |
|-------|-------|
| **Phase** | `main` |
| **Theme** | Route to 10 VP |
| **Active player** | Red (8 VP: 2 cities + 1 hidden VP + 2 dev cards) |

**Scenario:** One point from victory. Blue at 7 VP threatens **longest road** extension; green at 7 VP holds **largest army** (3 knights). Red has ore for a city but only one settlement remaining.

**Decision node:** **Visible city VP** vs **dev-card VP/knight** vs **blocking** via trade or build.

**Expected COA style:**

1. **Build city** — fastest visible win if affordable.
2. **Buy development card** — hidden VP or knight to contest army/robber.
3. **Maritime trade** — close a one-resource gap for city; avoid trades that enable blue's road.

**Pattern label:** `endgame_tempo` / `win_condition_race`

---

## Testing checklist

```bash
# Schema + rules (no Ollama)
pytest -v

# Full recommend path (requires API + Ollama)
uvicorn app.main:app --port 8080
python -m cli recommend --file examples/sample1_early_expansion.json
# … repeat for sample2–sample5
```

Compare outputs against the **expected COA style** sections above — rankings may vary by model, but top recommendations should align with the documented pattern labels.
