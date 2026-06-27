import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ollama import OllamaError, build_recommend_prompt, load_rules, recommend_with_retries

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_game_state.json"

client = TestClient(app)


def _valid_llm_payload() -> dict:
    return {
        "message": {
            "content": json.dumps(
                {
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
            )
        }
    }


@pytest.fixture
def sample_game_state() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_recommend_valid_sample_returns_three_coas(sample_game_state: dict):
    with (
        patch("app.main.check_ollama_health"),
        patch("app.main.load_rules", return_value="rules"),
        patch("app.main.recommend_with_retries") as mock_recommend,
    ):
        from app.models import RecommendResponse

        mock_recommend.return_value = RecommendResponse.model_validate(
            json.loads(_valid_llm_payload()["message"]["content"])
        )
        response = client.post("/recommend", json=sample_game_state)

    assert response.status_code == 200
    body = response.json()
    assert body["active_player"] == "red"
    assert len(body["recommendations"]) == 3
    ranks = sorted(rec["rank"] for rec in body["recommendations"])
    assert ranks == [1, 2, 3]
    for rec in body["recommendations"]:
        assert rec["action_type"]
        assert rec["summary"]
        assert rec["rationale"]
        assert isinstance(rec["rules_refs"], list) and rec["rules_refs"]
        assert isinstance(rec["details"], dict)


def test_recommend_malformed_json_returns_422():
    response = client.post(
        "/recommend",
        content=b"{not valid json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422


def test_recommend_missing_required_field_returns_422(sample_game_state: dict):
    del sample_game_state["active_player"]
    response = client.post("/recommend", json=sample_game_state)
    assert response.status_code == 422
    assert any("active_player" in str(err) for err in response.json()["detail"])


def test_recommend_wrong_data_types_returns_422(sample_game_state: dict):
    sample_game_state["dice_rolled"] = "yes"
    response = client.post("/recommend", json=sample_game_state)
    assert response.status_code == 422


def test_recommend_invalid_last_roll_returns_422(sample_game_state: dict):
    sample_game_state["last_roll"] = [7, 1]
    response = client.post("/recommend", json=sample_game_state)
    assert response.status_code == 422


def test_recommend_unknown_active_player_returns_422(sample_game_state: dict):
    sample_game_state["active_player"] = "green"
    response = client.post("/recommend", json=sample_game_state)
    assert response.status_code == 422


def test_recommend_llm_invalid_schema_returns_502(sample_game_state: dict):
    with (
        patch("app.main.check_ollama_health"),
        patch("app.main.load_rules", return_value="rules"),
        patch(
            "app.main.recommend_with_retries",
            side_effect=ValueError("Failed to obtain valid recommendations"),
        ),
    ):
        response = client.post("/recommend", json=sample_game_state)

    assert response.status_code == 502
    assert response.json()["detail"]["ollama"] == "invalid_response"


def test_recommend_ollama_down_returns_502(sample_game_state: dict):
    with patch("app.main.check_ollama_health", side_effect=OllamaError("down")):
        response = client.post("/recommend", json=sample_game_state)

    assert response.status_code == 502


def test_parse_recommend_response_rejects_incomplete_coas():
    from app.ollama import parse_recommend_response

    bad_payload = {
        "message": {
            "content": json.dumps(
                {
                    "active_player": "red",
                    "recommendations": [
                        {
                            "rank": 1,
                            "action_type": "end_turn",
                            "summary": "End",
                            "details": {},
                            "rationale": "Done",
                            "rules_refs": ["§4"],
                        }
                    ],
                }
            )
        }
    }
    with pytest.raises(Exception):
        parse_recommend_response(bad_payload)


def test_load_rules_reads_rules_file():
    rules = load_rules("docs/CATAN-OFFICIAL-RULES.md")
    assert "Catan" in rules
    assert "Building costs" in rules or "building" in rules.lower()


def test_build_recommend_prompt_includes_rules_and_state():
    prompt = build_recommend_prompt('{"phase":"main"}', "RULES_TEXT")
    assert "RULES_TEXT" in prompt
    assert '{"phase":"main"}' in prompt
    assert "exactly three" in prompt.lower() or "three ranked" in prompt.lower()


@pytest.mark.integration
def test_recommend_end_to_end_with_ollama(sample_game_state: dict):
    """Non-blocking integration: skipped when Ollama is unavailable."""
    try:
        with httpx.Client(timeout=5.0) as http_client:
            resp = http_client.get("http://127.0.0.1:11434/api/tags")
            resp.raise_for_status()
            models = {m.get("name", "") for m in resp.json().get("models", [])}
            if not any(name.startswith("qwen2.5") for name in models):
                pytest.skip("qwen2.5 model not installed in Ollama")
    except httpx.HTTPError:
        pytest.skip("Ollama not reachable")

    response = client.post("/recommend", json=sample_game_state)
    if response.status_code == 502:
        pytest.skip(f"Ollama recommend failed: {response.json()}")

    assert response.status_code == 200
    body = response.json()
    assert len(body["recommendations"]) == 3


def test_recommend_rules_violation_distance_returns_422(sample_game_state: dict):
    payload = deepcopy(sample_game_state)
    payload["proposed_actions"] = [
        {"action_type": "build_settlement", "vertex_id": "v2"}
    ]
    response = client.post("/recommend", json=payload)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    assert any(err["code"] == "distance_rule_violation" for err in detail)
    assert all("rules_ref" in err for err in detail)


def test_recommend_rules_violation_affordability_returns_422(sample_game_state: dict):
    payload = deepcopy(sample_game_state)
    payload["players"][0]["resources"]["grain"] = 0
    payload["players"][0]["resources"]["ore"] = 0
    payload["proposed_actions"] = [
        {"action_type": "build_city", "vertex_id": "v1"}
    ]
    response = client.post("/recommend", json=payload)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any(err["code"] == "insufficient_resources" for err in detail)


def test_recommend_rules_violation_does_not_call_ollama(sample_game_state: dict):
    payload = deepcopy(sample_game_state)
    payload["proposed_actions"] = [
        {"action_type": "move_robber", "hex_id": "h3"}
    ]
    with (
        patch("app.main.check_ollama_health") as mock_health,
        patch("app.main.recommend_with_retries") as mock_recommend,
    ):
        response = client.post("/recommend", json=payload)
    assert response.status_code == 422
    mock_health.assert_not_called()
    mock_recommend.assert_not_called()


def test_recommend_malformed_ollama_json_retries_then_502(sample_game_state: dict):
    malformed = {"message": {"content": "not-json"}}
    valid = _valid_llm_payload()

    with (
        patch("app.main.check_ollama_health"),
        patch("app.main.load_rules", return_value="rules"),
        patch("app.ollama.ollama_call", side_effect=[malformed, malformed, malformed]),
    ):
        response = client.post("/recommend", json=sample_game_state)

    assert response.status_code == 502
    assert response.json()["detail"]["ollama"] == "invalid_response"


def test_recommend_well_formed_ollama_output_accepted(sample_game_state: dict):
    with (
        patch("app.main.check_ollama_health"),
        patch("app.main.load_rules", return_value="rules"),
        patch("app.ollama.ollama_call", return_value=_valid_llm_payload()),
    ):
        response = client.post("/recommend", json=sample_game_state)

    assert response.status_code == 200
    assert len(response.json()["recommendations"]) == 3


def test_recommend_with_retries_retries_on_malformed_json(sample_game_state: dict):
    malformed = {"message": {"content": "{bad json"}}
    valid = _valid_llm_payload()

    with patch("app.ollama.ollama_call", side_effect=[malformed, valid]) as mock_call:
        result = recommend_with_retries(
            game_state_json=json.dumps(sample_game_state),
            rules_text="rules",
            model="qwen2.5",
            base_url="http://127.0.0.1:11434",
        )

    assert result.active_player == "red"
    assert len(result.recommendations) == 3
    assert mock_call.call_count == 2


def test_parse_ollama_json_response_accepts_valid_payload():
    from app.ollama import parse_ollama_json_response

    payload = parse_ollama_json_response(_valid_llm_payload()["message"]["content"])
    assert payload["active_player"] == "red"
    assert len(payload["recommendations"]) == 3


def test_parse_ollama_json_response_rejects_malformed():
    from app.ollama import parse_ollama_json_response

    with pytest.raises(Exception):
        parse_ollama_json_response("not json at all")
