# Documentation index

| Document | Purpose |
|----------|---------|
| [IDEA-BRIEF.md](IDEA-BRIEF.md) | Product intent and scope |
| [PRD.md](PRD.md) | Requirements |
| [GAME-STATE-SCHEMA.md](GAME-STATE-SCHEMA.md) | JSON schema for `POST /recommend` |
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

Interactive API reference: run the app and open `/docs`.
