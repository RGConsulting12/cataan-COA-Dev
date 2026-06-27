from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from app import __version__
from app.models import (
    GameSession,
    GameState,
    HealthResponse,
    RecommendResponse,
    SessionCreateRequest,
    SessionPatch,
)
from app.rules_validator import validate_game_state
from app.ollama import (
    OllamaError,
    check_ollama_health,
    load_rules,
    recommend_with_retries,
)
from app import sessions as session_store
from app.settings import Settings, get_settings

REPO_ROOT = Path(__file__).resolve().parent.parent

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
    {
        "name": "Sessions",
        "description": (
            "File-backed game sessions under `data/sessions/`. Create from inline "
            "JSON or `examples/sample*.json` fixtures; retrieve, patch header fields, "
            "and request COA recommendations for the stored state."
        ),
    },
    {
        "name": "UI",
        "description": "Minimal read-only web UI for inspecting sessions and COAs.",
    },
]

app = FastAPI(
    title="Catan COA Advisor",
    version=__version__,
    description=(
        "Stateless recommendation API for *Catan* courses of action (COA). "
        "Submit a complete game-state snapshot; receive exactly three ranked "
        "recommended moves with rationale grounded in the official rules. "
        "File-backed game sessions and a minimal `/ui` viewer are available for "
        "local operator use — no database or authentication."
    ),
    openapi_tags=OPENAPI_TAGS,
)

app.mount("/static", StaticFiles(directory=str(REPO_ROOT / "static")), name="static")

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


def _run_recommend(game_state: GameState, settings: Settings) -> RecommendResponse:
    rules_errors = validate_game_state(game_state.model_dump())
    if rules_errors:
        raise HTTPException(status_code=422, detail=rules_errors)

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

    try:
        return recommend_with_retries(
            game_state_json=game_state.model_dump_json(),
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

    return _run_recommend(game_state, settings)


@app.get(
    "/examples",
    tags=["Sessions"],
    summary="List available example game-state fixtures",
)
def list_examples() -> dict[str, list[str]]:
    return {"fixtures": session_store.list_example_states()}


@app.post(
    "/sessions",
    response_model=GameSession,
    status_code=201,
    tags=["Sessions"],
    summary="Create a persisted game session",
    description=(
        "Create a session from `examples/sample*.json` via `fixture`, or from an "
        "inline `state` object. Sessions are stored as JSON files under "
        "`data/sessions/{id}.json`."
    ),
)
def create_session(body: SessionCreateRequest) -> GameSession:
    try:
        if body.fixture:
            return session_store.create_session_from_fixture(
                body.fixture,
                turn_number=body.turn_number,
            )
        assert body.state is not None
        return session_store.create_session_from_state(
            body.state,
            label=body.label,
            turn_number=body.turn_number,
        )
    except session_store.FixtureNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Fixture not found: {exc}") from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=jsonable_encoder(exc.errors())) from exc


@app.get(
    "/sessions/{session_id}",
    response_model=GameSession,
    tags=["Sessions"],
    summary="Retrieve a game session",
)
def get_session(session_id: str) -> GameSession:
    try:
        return session_store.load_session(session_id)
    except session_store.SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}") from exc


@app.patch(
    "/sessions/{session_id}",
    response_model=GameSession,
    tags=["Sessions"],
    summary="Update patchable session fields",
    description=(
        "Patchable top-level fields: `turn_number`, `label`. "
        "Patchable `state` fields: `phase`, `active_player`, `dice_rolled`, "
        "`last_roll`, `notes`. Protected fields (`id`, `created_at`, board, players) "
        "cannot be changed via PATCH."
    ),
)
def update_session(session_id: str, body: SessionPatch) -> GameSession:
    try:
        return session_store.patch_session(session_id, body)
    except session_store.SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}") from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=jsonable_encoder(exc.errors())) from exc


@app.post(
    "/sessions/{session_id}/recommend",
    response_model=RecommendResponse,
    tags=["Sessions"],
    summary="Recommend COAs for a stored session",
)
def recommend_session(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> RecommendResponse:
    try:
        session = session_store.load_session(session_id)
    except session_store.SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}") from exc

    return _run_recommend(session.state, settings)


@app.get(
    "/ui",
    tags=["UI"],
    summary="Minimal session viewer (read-only)",
)
def ui_page(
    session_id: str | None = Query(default=None, description="Optional session to load"),
) -> FileResponse:
    if session_id:
        try:
            session_store.load_session(session_id)
        except session_store.SessionNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}") from exc

    return FileResponse(
        REPO_ROOT / "static" / "ui.html",
        media_type="text/html",
    )
