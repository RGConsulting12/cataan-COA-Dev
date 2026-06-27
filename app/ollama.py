from __future__ import annotations

from pathlib import Path

import httpx

from app.models import RecommendResponse, extract_json_object


class OllamaError(Exception):
    """Raised when Ollama is unreachable or returns an error."""


def load_rules(path: str) -> str:
    rules_file = Path(path)
    if not rules_file.is_file():
        raise FileNotFoundError(f"Rules file not found: {path}")
    return rules_file.read_text(encoding="utf-8")


def ollama_call(prompt: str, model: str, base_url: str) -> dict:
    url = f"{base_url.rstrip('/')}/api/chat"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "format": "json",
    }
    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as exc:
        raise OllamaError(str(exc)) from exc


def check_ollama_health(base_url: str, model: str) -> None:
    tags_url = f"{base_url.rstrip('/')}/api/tags"
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(tags_url)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        raise OllamaError(str(exc)) from exc

    models = data.get("models", [])
    model_names = {entry.get("name", "") for entry in models}
    prefixes = {name.split(":")[0] for name in model_names if name}
    if model not in prefixes and not any(name.startswith(f"{model}:") for name in model_names):
        raise OllamaError(f"Model '{model}' is not installed in Ollama")


def build_recommend_prompt(game_state_json: str, rules_text: str) -> str:
    schema_hint = """
Return ONLY valid JSON with this exact shape:
{
  "active_player": "<player id>",
  "recommendations": [
    {
      "rank": 1,
      "action_type": "<one of: roll_dice, maritime_trade, player_trade, build_road, build_settlement, build_city, buy_development_card, play_knight, play_road_building, play_year_of_plenty, play_monopoly, move_robber, end_turn, pass>",
      "summary": "<short action summary>",
      "details": {},
      "rationale": "<why this move is good>",
      "rules_refs": ["<section references from rules doc>"]
    },
    { "rank": 2, ... },
    { "rank": 3, ... }
  ]
}
"""
    return (
        "You are a Catan base-game advisor. Recommend exactly three ranked legal courses "
        "of action for the active player. Use only base-game rules. "
        "Return JSON only, no markdown.\n\n"
        f"{schema_hint}\n\n"
        f"OFFICIAL RULES:\n{rules_text}\n\n"
        f"GAME STATE:\n{game_state_json}"
    )


def parse_recommend_response(raw_response: dict) -> RecommendResponse:
    message = raw_response.get("message", {})
    content = message.get("content", "")
    if not content:
        raise ValueError("Empty LLM response content")
    payload = extract_json_object(content)
    return RecommendResponse.model_validate(payload)


def recommend_with_retries(
    *,
    game_state_json: str,
    rules_text: str,
    model: str,
    base_url: str,
    max_retries: int = 3,
) -> RecommendResponse:
    prompt = build_recommend_prompt(game_state_json, rules_text)
    last_error: str | None = None

    for attempt in range(max_retries):
        full_prompt = prompt
        if last_error:
            full_prompt += (
                "\n\nYour previous JSON did not match the required schema. "
                f"Validation errors:\n{last_error}\n"
                "Return ONLY corrected JSON with exactly 3 recommendations (ranks 1-3)."
            )
        raw = ollama_call(full_prompt, model=model, base_url=base_url)
        try:
            return parse_recommend_response(raw)
        except Exception as exc:
            last_error = str(exc)

    raise ValueError(f"Failed to obtain valid recommendations after {max_retries} attempts: {last_error}")
