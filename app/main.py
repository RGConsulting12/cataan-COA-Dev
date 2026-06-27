from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException

from app.models import GameState, HealthResponse, RecommendResponse
from app.ollama import (
    OllamaError,
    check_ollama_health,
    load_rules,
    recommend_with_retries,
)
from app.settings import Settings, get_settings

app = FastAPI(title="Catan COA Advisor", version="0.1.0")


@app.get("/health", response_model=HealthResponse)
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


@app.post("/recommend", response_model=RecommendResponse)
def recommend(
    game_state: GameState,
    settings: Settings = Depends(get_settings),
) -> RecommendResponse:
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
