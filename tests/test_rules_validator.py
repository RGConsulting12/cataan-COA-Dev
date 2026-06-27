import json
from copy import deepcopy
from pathlib import Path

import pytest

from app.rules_validator import (
    get_rule_section_for_violation,
    validate_game_state,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_game_state.json"


@pytest.fixture
def base_state() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _with_proposed(state: dict, actions: list[dict], **context: object) -> dict:
    payload = deepcopy(state)
    payload["proposed_actions"] = actions
    for key, value in context.items():
        payload[key] = value
    return payload


def test_get_rule_section_for_violation_known_types():
    assert "§6" in get_rule_section_for_violation("distance_rule")
    assert "§8" in get_rule_section_for_violation("dev_card_same_turn")
    assert get_rule_section_for_violation("unknown") == "§13 Common illegal moves"


def test_validate_legal_state_no_proposed_actions(base_state: dict):
    assert validate_game_state(base_state) == []


def test_reject_settlement_adjacent_to_existing_building(base_state: dict):
    state = _with_proposed(
        base_state,
        [{"action_type": "build_settlement", "vertex_id": "v2"}],
    )
    errors = validate_game_state(state)
    assert errors
    assert any(err["code"] == "distance_rule_violation" for err in errors)
    assert any(err["field"].endswith("vertex_id") for err in errors)
    assert all("rules_ref" in err for err in errors)


def test_reject_city_build_insufficient_resources(base_state: dict):
    state = deepcopy(base_state)
    state["players"][0]["resources"]["grain"] = 1
    state["players"][0]["resources"]["ore"] = 2
    state = _with_proposed(
        state,
        [{"action_type": "build_city", "vertex_id": "v1"}],
    )
    errors = validate_game_state(state)
    assert errors
    assert any(err["code"] == "insufficient_resources" for err in errors)
    assert any("grain" in err["field"] or "ore" in err["field"] for err in errors)
    assert any("§6" in err["rules_ref"] for err in errors)


def test_reject_build_when_piece_limit_reached(base_state: dict):
    state = deepcopy(base_state)
    state["players"][0]["roads_remaining"] = 0
    state = _with_proposed(state, [{"action_type": "build_road", "edge_id": "e9"}])
    errors = validate_game_state(state)
    assert errors
    assert any(err["code"] == "piece_limit_exceeded" for err in errors)

    state = deepcopy(base_state)
    state["players"][0]["settlements_remaining"] = 0
    state = _with_proposed(
        state,
        [{"action_type": "build_settlement", "vertex_id": "v9"}],
    )
    errors = validate_game_state(state)
    assert any(err["code"] == "piece_limit_exceeded" for err in errors)

    state = deepcopy(base_state)
    state["players"][0]["cities_remaining"] = 0
    state = _with_proposed(
        state,
        [{"action_type": "build_city", "vertex_id": "v1"}],
    )
    errors = validate_game_state(state)
    assert any(err["code"] == "piece_limit_exceeded" for err in errors)


def test_reject_robber_placement_on_same_hex(base_state: dict):
    state = _with_proposed(
        base_state,
        [{"action_type": "move_robber", "hex_id": "h3"}],
    )
    errors = validate_game_state(state)
    assert errors
    assert any(err["code"] == "robber_same_hex" for err in errors)
    assert any("§" in err["rules_ref"] for err in errors)


def test_reject_robber_placement_on_unknown_hex(base_state: dict):
    state = _with_proposed(
        base_state,
        [{"action_type": "move_robber", "hex_id": "h99"}],
    )
    errors = validate_game_state(state)
    assert any(err["code"] == "invalid_robber_hex" for err in errors)


def test_reject_dev_card_played_same_turn_as_purchase(base_state: dict):
    state = _with_proposed(
        base_state,
        [{"action_type": "play_knight"}],
        dev_card_bought_this_turn=True,
    )
    errors = validate_game_state(state)
    assert errors
    assert any(err["code"] == "dev_card_same_turn" for err in errors)
    assert any("§8" in err["rules_ref"] for err in errors)


def test_dev_card_same_turn_via_notes_json(base_state: dict):
    state = deepcopy(base_state)
    state["notes"] = json.dumps(
        {
            "dev_card_bought_this_turn": True,
            "proposed_actions": [{"action_type": "play_monopoly"}],
        }
    )
    errors = validate_game_state(state)
    assert any(err["code"] == "dev_card_same_turn" for err in errors)


def test_allow_legal_proposed_actions(base_state: dict):
    state = deepcopy(base_state)
    state["players"][0]["resources"] = {
        "lumber": 3,
        "brick": 3,
        "wool": 2,
        "grain": 4,
        "ore": 4,
    }
    state["board"]["vertices"].append(
        {"id": "v9", "hexes": ["h1", "h2"], "owner": None, "building": None}
    )
    state["board"]["vertices"].append(
        {"id": "v10", "hexes": ["h1", "h2"], "owner": None, "building": None}
    )
    state["board"]["edges"].append(
        {"id": "e9", "vertices": ["v1", "v9"], "owner": "red"}
    )
    state["board"]["edges"].append(
        {"id": "e10", "vertices": ["v9", "v10"], "owner": "red"}
    )
    state = _with_proposed(
        state,
        [
            {"action_type": "build_settlement", "vertex_id": "v10"},
            {"action_type": "build_city", "vertex_id": "v1"},
        ],
    )
    assert validate_game_state(state) == []


def test_reject_invalid_robber_board_state(base_state: dict):
    state = deepcopy(base_state)
    state["board"]["hexes"].append(
        {"id": "h4", "terrain": "desert", "number": None, "robber": True}
    )
    errors = validate_game_state(state)
    assert any(err["code"] == "invalid_robber_state" for err in errors)
