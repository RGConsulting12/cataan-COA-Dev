from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError

from app import __version__
from app.models import GameState, HealthResponse, RecommendResponse
from app.rules_validator import validate_game_state
from app.ollama import (
    OllamaError,
    check_ollama_health,
    load_rules,
    recommend_with_retries,
)
from app.settings import Settings, get_settings

OPENAPI_TAGS = [
    {
        "name": "Health",
        "description": (
            "Liveness and dependency checks. Confirms the API process is running and "
            "that the configured Ollama model is reachable."
        ),
    },
    {
        "name": "Recommendations",
        "description": (
            "Stateless COA (courses of action) recommendations. Each request is "
            "computed solely from the submitted game-state JSON and global rules "
            "context — no per-user session or persisted game history is stored."
        ),
    },
]

app = FastAPI(
    title="Catan COA Advisor",
    version=__version__,
    description=(
        "Stateless recommendation API for *Catan* courses of action (COA). "
        "Submit a complete game-state snapshot; receive exactly three ranked "
        "recommended moves with rationale grounded in the official rules. "
        "Responses depend only on the request payload and backend configuration "
        "(Ollama model, rules document) — not on stored user or session state."
    ),
    openapi_tags=OPENAPI_TAGS,
)

_HEALTH_OK_EXAMPLE = {
    "status": "ok",
    "ollama": "ok",
    "model": "qwen2.5",
}

_HEALTH_502_EXAMPLE = {
    "detail": {
        "status": "error",
        "ollama": "unavailable",
        "message": "connection refused",
    }
}

_RECOMMEND_OK_EXAMPLE = {
    "active_player": "red",
    "recommendations": [
        {
            "rank": 1,
            "action_type": "build_city",
            "summary": "Upgrade settlement on strong ore hex.",
            "details": {"vertex_id": "v1", "cost": {"grain": 2, "ore": 3}},
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

_RECOMMEND_422_EXAMPLE = {
    "detail": [
        {
            "field": "proposed_actions[0].vertex_id",
            "code": "distance_rule_violation",
            "message": "Settlement cannot be placed adjacent to existing settlement at v1",
            "rules_ref": "§6 Building costs — Placement rules (distance rule)",
        }
    ]
}


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Check API and Ollama health",
    description=(
        "Returns service status and confirms connectivity to the configured Ollama "
        "instance and model. Use for load-balancer probes and pre-flight checks "
        "before calling `/recommend`."
    ),
    responses={
        200: {
            "description": "API and Ollama are healthy.",
            "content": {"application/json": {"example": _HEALTH_OK_EXAMPLE}},
        },
        502: {
            "description": "Ollama is unreachable or the configured model is unavailable.",
            "content": {"application/json": {"example": _HEALTH_502_EXAMPLE}},
        },
    },
)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    try:
        check_ollama_health(settings.ollama_base_url, settings.ollama_model)
    except OllamaError as exc:
        raise HTTPException(
            status_code=502,
            detail={"status": "error", "ollama": "unavailable", "message": str(exc)},
        ) from exc
    return HealthResponse(
        status="ok",
        ollama="ok",
        model=settings.ollama_model,
    )


@app.post(
    "/recommend",
    response_model=RecommendResponse,
    tags=["Recommendations"],
    summary="Get ranked courses of action",
    description=(
        "Accepts a full Catan game-state JSON body and returns exactly three ranked "
        "recommended moves (`rank` 1–3) with summaries, structured `details`, "
        "rationale, and `rules_refs`. The engine is **stateless**: each call is "
        "independent; provide the complete current state every time. "
        "Optional `proposed_actions` in the body (or inside JSON `notes`) are "
        "rules-validated before the LLM is invoked. See `docs/GAME-STATE-SCHEMA.md` "
        "and the `examples/` sample library for request shapes."
    ),
    responses={
        200: {
            "description": "Three ranked COA recommendations for the active player.",
            "content": {"application/json": {"example": _RECOMMEND_OK_EXAMPLE}},
        },
        422: {
            "description": "Game state or proposed actions failed schema or rules validation.",
            "content": {"application/json": {"example": _RECOMMEND_422_EXAMPLE}},
        },
        502: {
            "description": "Ollama unavailable, request failed, or LLM returned invalid JSON after retries.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "status": "error",
                            "ollama": "request_failed",
                            "message": "timeout",
                        }
                    }
                }
            },
        },
    },
)
def recommend(
    body: dict[str, Any],
    settings: Settings = Depends(get_settings),
) -> RecommendResponse:
    rules_errors = validate_game_state(body)
    if rules_errors:
        raise HTTPException(status_code=422, detail=rules_errors)

    try:
        game_state = GameState.model_validate(body)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=jsonable_encoder(exc.errors())) from exc

    try:
        check_ollama_health(settings.ollama_base_url, settings.ollama_model)
    except OllamaError as exc:
        raise HTTPException(
            status_code=502,
            detail={"status": "error", "ollama": "unavailable", "message": str(exc)},
        ) from exc

    try:
        rules_text = load_rules(str(settings.rules_path_resolved))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    game_state_json = game_state.model_dump_json()
    try:
        return recommend_with_retries(
            game_state_json=game_state_json,
            rules_text=rules_text,
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
        )
    except OllamaError as exc:
        raise HTTPException(
            status_code=502,
            detail={"status": "error", "ollama": "request_failed", "message": str(exc)},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail={"status": "error", "ollama": "invalid_response", "message": str(exc)},
        ) from exc
