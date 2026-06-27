import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import GameSession, RecommendResponse

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_game_state.json"
EXAMPLES_DIR = Path(__file__).parent.parent / "examples"

client = TestClient(app)


def _valid_llm_payload() -> dict:
    return {
        "active_player": "red",
        "recommendations": [
            {
                "rank": 1,
                "action_type": "build_city",
                "summary": "Upgrade settlement on strong ore hex.",
                "details": {"vertex_id": "v1"},
                "rationale": "Doubles ore production.",
                "rules_refs": ["§6 Building costs"],
            },
            {
                "rank": 2,
                "action_type": "maritime_trade",
                "summary": "Trade grain for ore at 4:1.",
                "details": {},
                "rationale": "Sets up a city upgrade next turn.",
                "rules_refs": ["§7 Maritime trade"],
            },
            {
                "rank": 3,
                "action_type": "end_turn",
                "summary": "End turn if no better trades appear.",
                "details": {},
                "rationale": "Preserves resources.",
                "rules_refs": ["§4 Turn structure"],
            },
        ],
    }


@pytest.fixture
def sample_game_state() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def sessions_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    monkeypatch.setattr("app.sessions.SESSIONS_DIR", sessions_dir)
    return sessions_dir


def test_post_sessions_with_valid_json_creates_file(sample_game_state: dict, sessions_tmp: Path):
    response = client.post(
        "/sessions",
        json={"state": sample_game_state, "label": "test session", "turn_number": 2},
    )
    assert response.status_code == 201
    body = response.json()
    session_id = body["id"]
    assert body["turn_number"] == 2
    assert body["label"] == "test session"
    assert (sessions_tmp / f"{session_id}.json").is_file()

    stored = json.loads((sessions_tmp / f"{session_id}.json").read_text(encoding="utf-8"))
    GameSession.model_validate(stored)


@pytest.mark.parametrize(
    "fixture_name",
    sorted(p.name for p in EXAMPLES_DIR.glob("sample*.json")),
)
def test_create_session_from_each_example_fixture(fixture_name: str, sessions_tmp: Path):
    response = client.post("/sessions", json={"fixture": fixture_name})
    assert response.status_code == 201
    body = response.json()
    assert body["source_fixture"] == fixture_name

    get_resp = client.get(f"/sessions/{body['id']}")
    assert get_resp.status_code == 200
    session = get_resp.json()
    assert session["state"]["phase"]
    assert session["state"]["players"]


def test_get_session_returns_200_and_correct_session(sample_game_state: dict, sessions_tmp: Path):
    created = client.post("/sessions", json={"state": sample_game_state}).json()
    session_id = created["id"]

    response = client.get(f"/sessions/{session_id}")
    assert response.status_code == 200
    assert response.json()["id"] == session_id
    assert response.json()["state"]["active_player"] == sample_game_state["active_player"]


def test_get_session_missing_returns_404(sessions_tmp: Path):
    response = client.get("/sessions/does-not-exist")
    assert response.status_code == 404


def test_patch_session_allowed_fields_persist(sample_game_state: dict, sessions_tmp: Path):
    created = client.post("/sessions", json={"state": sample_game_state, "turn_number": 1}).json()
    session_id = created["id"]

    response = client.patch(
        f"/sessions/{session_id}",
        json={
            "turn_number": 5,
            "label": "midgame",
            "state": {"phase": "robber", "notes": "Robber phase"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["turn_number"] == 5
    assert body["label"] == "midgame"
    assert body["state"]["phase"] == "robber"
    assert body["state"]["notes"] == "Robber phase"

    reloaded = client.get(f"/sessions/{session_id}").json()
    assert reloaded["turn_number"] == 5
    assert reloaded["state"]["phase"] == "robber"


def test_patch_illegal_fields_returns_422(sample_game_state: dict, sessions_tmp: Path):
    created = client.post("/sessions", json={"state": sample_game_state}).json()
    session_id = created["id"]

    response = client.patch(
        f"/sessions/{session_id}",
        json={"id": "hacked", "created_at": "2000-01-01T00:00:00Z"},
    )
    assert response.status_code == 422


def test_patch_invalid_schema_returns_422(sample_game_state: dict, sessions_tmp: Path):
    created = client.post("/sessions", json={"state": sample_game_state}).json()
    session_id = created["id"]

    response = client.patch(
        f"/sessions/{session_id}",
        json={"state": {"active_player": "not-a-real-player"}},
    )
    assert response.status_code == 422


def test_post_session_recommend_returns_three_coas(sample_game_state: dict, sessions_tmp: Path):
    created = client.post("/sessions", json={"state": sample_game_state}).json()
    session_id = created["id"]

    with (
        patch("app.main.check_ollama_health"),
        patch("app.main.load_rules", return_value="rules"),
        patch("app.main.recommend_with_retries") as mock_recommend,
    ):
        mock_recommend.return_value = RecommendResponse.model_validate(_valid_llm_payload())
        response = client.post(f"/sessions/{session_id}/recommend")

    assert response.status_code == 200
    body = response.json()
    assert len(body["recommendations"]) == 3
    ranks = sorted(rec["rank"] for rec in body["recommendations"])
    assert ranks == [1, 2, 3]
    for rec in body["recommendations"]:
        assert rec["action_type"]
        assert rec["summary"]
        assert rec["rationale"]


def test_recommend_session_missing_returns_404(sessions_tmp: Path):
    with patch("app.main.check_ollama_health"):
        response = client.post("/sessions/missing-id/recommend")
    assert response.status_code == 404


def test_written_session_files_stay_in_schema(sample_game_state: dict, sessions_tmp: Path):
    created = client.post(
        "/sessions",
        json={"state": sample_game_state, "turn_number": 3, "label": "schema check"},
    ).json()
    path = sessions_tmp / f"{created['id']}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    session = GameSession.model_validate(data)
    assert session.state.active_player == sample_game_state["active_player"]


def test_recommend_regression_always_three_coas(sample_game_state: dict, sessions_tmp: Path):
    created = client.post("/sessions", json={"state": sample_game_state}).json()
    with (
        patch("app.main.check_ollama_health"),
        patch("app.main.load_rules", return_value="rules"),
        patch("app.main.recommend_with_retries") as mock_recommend,
    ):
        mock_recommend.return_value = RecommendResponse.model_validate(_valid_llm_payload())
        response = client.post(f"/sessions/{created['id']}/recommend")
    assert len(response.json()["recommendations"]) == 3
