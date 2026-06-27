from __future__ import annotations

import json
import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, StrictBool, field_validator, model_validator


class Phase(str, Enum):
    setup = "setup"
    pre_roll = "pre_roll"
    main = "main"
    robber = "robber"


class ResourceCounts(BaseModel):
    lumber: int = Field(ge=0)
    brick: int = Field(ge=0)
    wool: int = Field(ge=0)
    grain: int = Field(ge=0)
    ore: int = Field(ge=0)


class Player(BaseModel):
    id: str
    color: str
    resources: ResourceCounts
    development_cards_in_hand: int = Field(ge=0)
    knights_played: int = Field(ge=0)
    roads_remaining: int = Field(ge=0, le=15)
    settlements_remaining: int = Field(ge=0, le=5)
    cities_remaining: int = Field(ge=0, le=4)
    victory_points: int = Field(ge=0)
    hidden_vp_cards: int = Field(ge=0, default=0)


class Hex(BaseModel):
    id: str
    terrain: str
    number: int | None = None
    robber: bool = False


class BuildingType(str, Enum):
    settlement = "settlement"
    city = "city"


class Vertex(BaseModel):
    id: str
    hexes: list[str]
    owner: str | None = None
    building: BuildingType | None = None


class Edge(BaseModel):
    id: str
    vertices: list[str] = Field(min_length=2, max_length=2)
    owner: str | None = None


class Harbor(BaseModel):
    vertex_id: str
    type: str


class Board(BaseModel):
    hexes: list[Hex] = Field(default_factory=list)
    vertices: list[Vertex] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    harbors: list[Harbor] = Field(default_factory=list)


class Bank(BaseModel):
    resources: ResourceCounts


class GameState(BaseModel):
    phase: Phase
    active_player: str
    dice_rolled: StrictBool
    last_roll: list[int] | None = None
    players: list[Player] = Field(min_length=1)
    board: Board
    bank: Bank
    development_deck_remaining: int = Field(ge=0, le=25)
    longest_road_player: str | None = None
    largest_army_player: str | None = None
    notes: str | None = None

    @field_validator("last_roll")
    @classmethod
    def validate_last_roll(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return value
        if len(value) != 2:
            raise ValueError("last_roll must contain exactly two dice values")
        for die in value:
            if die < 1 or die > 6:
                raise ValueError("each die in last_roll must be between 1 and 6")
        return value

    @model_validator(mode="after")
    def validate_active_player_exists(self) -> GameState:
        player_ids = {player.id for player in self.players}
        if self.active_player not in player_ids:
            raise ValueError("active_player must match a player id")
        return self


class ActionType(str, Enum):
    roll_dice = "roll_dice"
    maritime_trade = "maritime_trade"
    player_trade = "player_trade"
    build_road = "build_road"
    build_settlement = "build_settlement"
    build_city = "build_city"
    buy_development_card = "buy_development_card"
    play_knight = "play_knight"
    play_road_building = "play_road_building"
    play_year_of_plenty = "play_year_of_plenty"
    play_monopoly = "play_monopoly"
    move_robber = "move_robber"
    end_turn = "end_turn"
    pass_action = "pass"


class Recommendation(BaseModel):
    rank: int = Field(ge=1, le=3)
    action_type: ActionType
    summary: str = Field(min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)
    rationale: str = Field(min_length=1)
    rules_refs: list[str] = Field(min_length=1)


class RecommendResponse(BaseModel):
    """Ranked COA recommendations for the active player."""

    active_player: str = Field(
        description="Player id from the submitted game state who receives recommendations.",
        examples=["red"],
    )
    recommendations: list[Recommendation] = Field(
        min_length=3,
        max_length=3,
        description="Exactly three ranked courses of action (ranks 1, 2, and 3).",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "active_player": "red",
                    "recommendations": [
                        {
                            "rank": 1,
                            "action_type": "build_city",
                            "summary": "Upgrade settlement on strong ore hex.",
                            "details": {
                                "vertex_id": "v1",
                                "cost": {"grain": 2, "ore": 3},
                            },
                            "rationale": "Doubles ore production on a high-probability number.",
                            "rules_refs": ["§6 Building costs", "§4 Turn structure"],
                        },
                        {
                            "rank": 2,
                            "action_type": "maritime_trade",
                            "summary": "Trade grain for ore at 4:1.",
                            "details": {"give": {"grain": 4}, "receive": {"ore": 1}},
                            "rationale": "Sets up a city upgrade next turn.",
                            "rules_refs": ["§7 Maritime trade"],
                        },
                        {
                            "rank": 3,
                            "action_type": "end_turn",
                            "summary": "End turn if no better trades appear.",
                            "details": {},
                            "rationale": "Preserves resources when no build is affordable.",
                            "rules_refs": ["§4 Turn structure"],
                        },
                    ],
                }
            ]
        }
    }

    @model_validator(mode="after")
    def validate_ranks(self) -> RecommendResponse:
        ranks = sorted(rec.rank for rec in self.recommendations)
        if ranks != [1, 2, 3]:
            raise ValueError("recommendations must include ranks 1, 2, and 3 exactly once")
        return self


class HealthResponse(BaseModel):
    """Health check payload returned by `GET /health`."""

    status: str = Field(
        description="API process status. `ok` when the service is running.",
        examples=["ok"],
    )
    ollama: str = Field(
        description="Ollama connectivity status. `ok` when the configured model is reachable.",
        examples=["ok"],
    )
    model: str = Field(
        description="Ollama model name used for COA generation.",
        examples=["qwen2.5"],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "ok",
                    "ollama": "ok",
                    "model": "qwen2.5",
                }
            ]
        }
    }


def extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in LLM response")
    return json.loads(stripped[start : end + 1])
