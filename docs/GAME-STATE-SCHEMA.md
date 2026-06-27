# Game state schema (v1 draft)

JSON shape for `POST /recommend`. Implement as Pydantic models in slice 1.

## Top level

```json
{
  "phase": "main",
  "active_player": "red",
  "dice_rolled": true,
  "last_roll": [4, 5],
  "players": [],
  "board": {},
  "bank": {},
  "development_deck_remaining": 20,
  "longest_road_player": "blue",
  "largest_army_player": null,
  "notes": "Optional free text for edge cases"
}
```

## `phase`

| Value | Meaning |
|-------|---------|
| `setup` | Initial placement (if advising setup picks) |
| `pre_roll` | Active player's turn, dice not yet rolled |
| `main` | After roll (or 7 resolved), trade/build phase |
| `robber` | Active player must place robber (rolled 7 or knight) |

## `players[]`

```json
{
  "id": "red",
  "color": "red",
  "resources": { "lumber": 2, "brick": 1, "wool": 0, "grain": 3, "ore": 1 },
  "development_cards_in_hand": 1,
  "knights_played": 2,
  "roads_remaining": 10,
  "settlements_remaining": 2,
  "cities_remaining": 3,
  "victory_points": 6,
  "hidden_vp_cards": 0
}
```

## `board`

Simplified graph representation:

```json
{
  "hexes": [
    { "id": "h1", "terrain": "fields", "number": 9, "robber": false }
  ],
  "vertices": [
    { "id": "v1", "hexes": ["h1", "h2", "h3"], "owner": "red", "building": "settlement" }
  ],
  "edges": [
    { "id": "e1", "vertices": ["v1", "v2"], "owner": "red" }
  ],
  "harbors": [
    { "vertex_id": "v5", "type": "3:1" }
  ]
}
```

**`building`:** `null` | `settlement` | `city`

## `bank`

```json
{
  "resources": { "lumber": 10, "brick": 8, "wool": 12, "grain": 9, "ore": 11 }
}
```

## COA `action_type` enum (for responses)

- `roll_dice` (only when `dice_rolled: false` and phase allows)
- `maritime_trade`
- `player_trade`
- `build_road`
- `build_settlement`
- `build_city`
- `buy_development_card`
- `play_knight`
- `play_road_building`
- `play_year_of_plenty`
- `play_monopoly`
- `move_robber`
- `end_turn`
- `pass` (no productive action — low rank only if truly best)
