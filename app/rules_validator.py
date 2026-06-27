from __future__ import annotations

import json
from typing import Any

BUILD_COSTS: dict[str, dict[str, int]] = {
    "build_road": {"lumber": 1, "brick": 1},
    "build_settlement": {"lumber": 1, "brick": 1, "wool": 1, "grain": 1},
    "build_city": {"grain": 2, "ore": 3},
    "buy_development_card": {"wool": 1, "grain": 1, "ore": 1},
}

PIECE_LIMIT_FIELDS: dict[str, tuple[str, int]] = {
    "build_road": ("roads_remaining", 15),
    "build_settlement": ("settlements_remaining", 5),
    "build_city": ("cities_remaining", 4),
}

PLAY_DEV_CARD_ACTIONS = frozenset(
    {
        "play_knight",
        "play_road_building",
        "play_year_of_plenty",
        "play_monopoly",
    }
)

VIOLATION_RULE_SECTIONS: dict[str, str] = {
    "distance_rule": "§6 Building costs — Placement rules (distance rule)",
    "affordability": "§6 Building costs",
    "piece_limit": "§6 Building costs — Placement rules (piece limits)",
    "robber_placement": "§5 Rolling a 7 / §11 Robber",
    "dev_card_same_turn": "§8 Development cards",
    "robber_blocked_build": "§11 Robber — building restrictions",
    "invalid_robber_state": "§5 Rolling a 7 / §11 Robber",
}


def get_rule_section_for_violation(violation: str) -> str:
    return VIOLATION_RULE_SECTIONS.get(violation, "§13 Common illegal moves")


def _error(
    *,
    field: str,
    code: str,
    message: str,
    violation: str,
) -> dict[str, str]:
    return {
        "field": field,
        "code": code,
        "message": message,
        "rules_ref": get_rule_section_for_violation(violation),
    }


def _parse_notes_context(game_state: dict[str, Any]) -> dict[str, Any]:
    notes = game_state.get("notes")
    if not notes or not isinstance(notes, str):
        return {}
    stripped = notes.strip()
    if not stripped.startswith("{"):
        return {}
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _get_proposed_actions(game_state: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(game_state.get("proposed_actions"), list):
        return [action for action in game_state["proposed_actions"] if isinstance(action, dict)]
    notes_context = _parse_notes_context(game_state)
    proposed = notes_context.get("proposed_actions", [])
    return [action for action in proposed if isinstance(action, dict)] if isinstance(proposed, list) else []


def _dev_card_bought_this_turn(game_state: dict[str, Any]) -> bool:
    if game_state.get("dev_card_bought_this_turn") is True:
        return True
    return _parse_notes_context(game_state).get("dev_card_bought_this_turn") is True


def _player_by_id(game_state: dict[str, Any], player_id: str) -> dict[str, Any] | None:
    for player in game_state.get("players", []):
        if isinstance(player, dict) and player.get("id") == player_id:
            return player
    return None


def _vertex_neighbors(board: dict[str, Any], vertex_id: str) -> set[str]:
    neighbors: set[str] = set()
    for edge in board.get("edges", []):
        if not isinstance(edge, dict):
            continue
        vertices = edge.get("vertices", [])
        if len(vertices) != 2:
            continue
        if vertex_id in vertices:
            other = vertices[1] if vertices[0] == vertex_id else vertices[0]
            neighbors.add(other)
    return neighbors


def _vertices_with_buildings(board: dict[str, Any]) -> dict[str, dict[str, Any]]:
    occupied: dict[str, dict[str, Any]] = {}
    for vertex in board.get("vertices", []):
        if not isinstance(vertex, dict):
            continue
        building = vertex.get("building")
        if building in ("settlement", "city"):
            occupied[vertex["id"]] = vertex
    return occupied


def _vertex_hexes(board: dict[str, Any], vertex_id: str) -> set[str]:
    for vertex in board.get("vertices", []):
        if isinstance(vertex, dict) and vertex.get("id") == vertex_id:
            hexes = vertex.get("hexes", [])
            return {hex_id for hex_id in hexes if isinstance(hex_id, str)}
    return set()


def _robber_hex_ids(board: dict[str, Any]) -> list[str]:
    return [
        hex_tile["id"]
        for hex_tile in board.get("hexes", [])
        if isinstance(hex_tile, dict) and hex_tile.get("robber") is True
    ]


def _check_distance_rule(
    board: dict[str, Any],
    vertex_id: str,
    *,
    field_prefix: str,
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    occupied = _vertices_with_buildings(board)
    if vertex_id in occupied:
        errors.append(
            _error(
                field=f"{field_prefix}.vertex_id",
                code="distance_rule_violation",
                message=f"Vertex {vertex_id} already has a building",
                violation="distance_rule",
            )
        )
        return errors

    for neighbor_id, neighbor in occupied.items():
        if neighbor_id in _vertex_neighbors(board, vertex_id):
            errors.append(
                _error(
                    field=f"{field_prefix}.vertex_id",
                    code="distance_rule_violation",
                    message=(
                        f"Settlement cannot be placed adjacent to existing "
                        f"{neighbor.get('building')} at {neighbor_id}"
                    ),
                    violation="distance_rule",
                )
            )
    return errors


def _check_robber_blocks_build(
    board: dict[str, Any],
    vertex_id: str,
    *,
    field_prefix: str,
) -> list[dict[str, str]]:
    robber_hexes = set(_robber_hex_ids(board))
    if not robber_hexes:
        return []
    touching = _vertex_hexes(board, vertex_id)
    if touching & robber_hexes:
        return [
            _error(
                field=f"{field_prefix}.vertex_id",
                code="robber_blocked_build",
                message=(
                    f"Cannot build on vertex {vertex_id} while robber blocks "
                    "an adjacent hex"
                ),
                violation="robber_blocked_build",
            )
        ]
    return []


def _check_affordability(
    player: dict[str, Any],
    action_type: str,
    *,
    field_prefix: str,
) -> list[dict[str, str]]:
    costs = BUILD_COSTS.get(action_type)
    if not costs:
        return []

    resources = player.get("resources", {})
    if not isinstance(resources, dict):
        resources = {}

    for resource, amount in costs.items():
        available = resources.get(resource, 0)
        if available < amount:
            return [
                _error(
                    field=f"{field_prefix}.{resource}",
                    code="insufficient_resources",
                    message=(
                        f"Insufficient {resource} for {action_type}: "
                        f"need {amount}, have {available}"
                    ),
                    violation="affordability",
                )
            ]
    return []


def _check_piece_limit(
    player: dict[str, Any],
    action_type: str,
    *,
    field_prefix: str,
) -> list[dict[str, str]]:
    limit_info = PIECE_LIMIT_FIELDS.get(action_type)
    if not limit_info:
        return []

    field_name, _max_pieces = limit_info
    remaining = player.get(field_name, 0)
    if remaining <= 0:
        piece_name = field_name.replace("_remaining", "")
        return [
            _error(
                field=f"{field_prefix}.{field_name}",
                code="piece_limit_exceeded",
                message=f"No {piece_name} pieces remaining for this player",
                violation="piece_limit",
            )
        ]
    return []


def _check_build_city_target(
    board: dict[str, Any],
    player_id: str,
    vertex_id: str,
    *,
    field_prefix: str,
) -> list[dict[str, str]]:
    for vertex in board.get("vertices", []):
        if not isinstance(vertex, dict) or vertex.get("id") != vertex_id:
            continue
        if vertex.get("owner") != player_id:
            return [
                _error(
                    field=f"{field_prefix}.vertex_id",
                    code="invalid_city_target",
                    message=f"Vertex {vertex_id} is not owned by active player",
                    violation="piece_limit",
                )
            ]
        if vertex.get("building") != "settlement":
            return [
                _error(
                    field=f"{field_prefix}.vertex_id",
                    code="invalid_city_target",
                    message=f"Vertex {vertex_id} has no settlement to upgrade",
                    violation="piece_limit",
                )
            ]
        return []
    return [
        _error(
            field=f"{field_prefix}.vertex_id",
            code="invalid_city_target",
            message=f"Unknown vertex {vertex_id}",
            violation="piece_limit",
        )
    ]


def _check_robber_move(
    board: dict[str, Any],
    hex_id: str,
    *,
    field_prefix: str,
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    hex_ids = {
        hex_tile["id"]
        for hex_tile in board.get("hexes", [])
        if isinstance(hex_tile, dict) and "id" in hex_tile
    }
    if hex_id not in hex_ids:
        return [
            _error(
                field=f"{field_prefix}.hex_id",
                code="invalid_robber_hex",
                message=f"Hex {hex_id} does not exist on the board",
                violation="robber_placement",
            )
        ]

    current_robber = _robber_hex_ids(board)
    if len(current_robber) != 1:
        errors.append(
            _error(
                field="board.hexes",
                code="invalid_robber_state",
                message="Board must have exactly one robber hex",
                violation="invalid_robber_state",
            )
        )
        return errors

    if hex_id == current_robber[0]:
        errors.append(
            _error(
                field=f"{field_prefix}.hex_id",
                code="robber_same_hex",
                message="Robber must move to a different hex",
                violation="robber_placement",
            )
        )
    return errors


def _validate_proposed_action(
    game_state: dict[str, Any],
    action: dict[str, Any],
    index: int,
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    field_prefix = f"proposed_actions[{index}]"
    action_type = action.get("action_type")
    if not isinstance(action_type, str):
        return [
            _error(
                field=f"{field_prefix}.action_type",
                code="missing_action_type",
                message="Proposed action must include action_type",
                violation="distance_rule",
            )
        ]

    active_player_id = game_state.get("active_player", "")
    player = _player_by_id(game_state, active_player_id)
    if player is None:
        return errors

    board = game_state.get("board", {})
    if not isinstance(board, dict):
        board = {}

    if action_type in BUILD_COSTS:
        errors.extend(
            _check_affordability(player, action_type, field_prefix=field_prefix)
        )
        errors.extend(
            _check_piece_limit(player, action_type, field_prefix=field_prefix)
        )

    if action_type == "build_settlement":
        vertex_id = action.get("vertex_id")
        if not isinstance(vertex_id, str):
            errors.append(
                _error(
                    field=f"{field_prefix}.vertex_id",
                    code="missing_vertex_id",
                    message="build_settlement requires vertex_id",
                    violation="distance_rule",
                )
            )
        else:
            errors.extend(
                _check_distance_rule(board, vertex_id, field_prefix=field_prefix)
            )
            errors.extend(
                _check_robber_blocks_build(board, vertex_id, field_prefix=field_prefix)
            )

    if action_type == "build_city":
        vertex_id = action.get("vertex_id")
        if not isinstance(vertex_id, str):
            errors.append(
                _error(
                    field=f"{field_prefix}.vertex_id",
                    code="missing_vertex_id",
                    message="build_city requires vertex_id",
                    violation="affordability",
                )
            )
        else:
            errors.extend(
                _check_build_city_target(
                    board,
                    active_player_id,
                    vertex_id,
                    field_prefix=field_prefix,
                )
            )

    if action_type == "move_robber":
        hex_id = action.get("hex_id")
        if not isinstance(hex_id, str):
            errors.append(
                _error(
                    field=f"{field_prefix}.hex_id",
                    code="missing_hex_id",
                    message="move_robber requires hex_id",
                    violation="robber_placement",
                )
            )
        else:
            errors.extend(
                _check_robber_move(board, hex_id, field_prefix=field_prefix)
            )

    if action_type in PLAY_DEV_CARD_ACTIONS and _dev_card_bought_this_turn(game_state):
        errors.append(
            _error(
                field=f"{field_prefix}.action_type",
                code="dev_card_same_turn",
                message="Cannot play a development card bought on the same turn",
                violation="dev_card_same_turn",
            )
        )

    return errors


def _validate_board_robber_state(board: dict[str, Any]) -> list[dict[str, str]]:
    if not isinstance(board, dict):
        return []
    robber_hexes = _robber_hex_ids(board)
    if len(robber_hexes) != 1:
        return [
            _error(
                field="board.hexes",
                code="invalid_robber_state",
                message="Board must have exactly one robber hex",
                violation="invalid_robber_state",
            )
        ]
    return []


def validate_game_state(game_state: dict[str, Any]) -> list[dict[str, str]]:
    """Return structured rule violations for obvious illegal moves, or an empty list."""
    errors: list[dict[str, str]] = []

    board = game_state.get("board", {})
    if isinstance(board, dict):
        errors.extend(_validate_board_robber_state(board))

    for index, action in enumerate(_get_proposed_actions(game_state)):
        errors.extend(_validate_proposed_action(game_state, action, index))

    return errors
