import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import RecommendResponse

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_game_state.json"

client = TestClient(app)


def _valid_llm_payload() -> dict:
    return {
        "active_player": "red",
        "recommendations": [
            {
                "rank": 1,
                "action_type": "build_city",
                "summary": "Upgrade settlement.",
                "details": {},
                "rationale": "Strong ore hex.",
                "rules_refs": ["§6"],
            },
            {
                "rank": 2,
                "action_type": "maritime_trade",
                "summary": "Trade for ore.",
                "details": {},
                "rationale": "Affordable trade.",
                "rules_refs": ["§7"],
            },
            {
                "rank": 3,
                "action_type": "end_turn",
                "summary": "End turn.",
                "details": {},
                "rationale": "No better move.",
                "rules_refs": ["§4"],
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


def test_ui_loads_at_root(sessions_tmp: Path):
    response = client.get("/ui")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    html = response.text
    assert "Catan COA Session Viewer" in html
    assert 'id="session-header"' in html
    assert 'id="board-svg"' in html
    assert 'id="player-timeline"' in html
    assert 'id="coa-cards"' in html
    assert 'id="fixture-select"' in html

    examples = client.get("/examples")
    assert examples.status_code == 200
    assert "sample1_early_expansion.json" in examples.json()["fixtures"]


def test_ui_with_session_displays_structure(sample_game_state: dict, sessions_tmp: Path):
    created = client.post("/sessions", json={"state": sample_game_state}).json()
    session_id = created["id"]

    with (
        patch("app.main.check_ollama_health"),
        patch("app.main.load_rules", return_value="rules"),
        patch("app.main.recommend_with_retries") as mock_recommend,
    ):
        mock_recommend.return_value = RecommendResponse.model_validate(_valid_llm_payload())
        page = client.get(f"/ui?session_id={session_id}")
        api_session = client.get(f"/sessions/{session_id}")
        recs = client.post(f"/sessions/{session_id}/recommend")

    assert page.status_code == 200
    assert api_session.status_code == 200
    assert recs.status_code == 200
    assert len(recs.json()["recommendations"]) == 3
    assert "hdr-phase" in page.text


def test_ui_unknown_session_returns_404(sessions_tmp: Path):
    response = client.get("/ui?session_id=unknown-session-id")
    assert response.status_code == 404


def test_static_css_loads_with_correct_mimetype():
    response = client.get("/static/css/ui.css")
    assert response.status_code == 200
    assert "text/css" in response.headers.get("content-type", "")
    assert "--accent" in response.text


def test_static_js_loads_with_correct_mimetype():
    response = client.get("/static/js/ui.js")
    assert response.status_code == 200
    assert "javascript" in response.headers.get("content-type", "")
    assert "loadSession" in response.text

    board = client.get("/static/js/board.js")
    assert board.status_code == 200
    assert "javascript" in board.headers.get("content-type", "")
    assert "renderBoard" in board.text


def test_changing_session_via_api_updates_get(sample_game_state: dict, sessions_tmp: Path):
    first = client.post("/sessions", json={"state": sample_game_state, "turn_number": 1}).json()
    second = client.post(
        "/sessions",
        json={"fixture": "sample2_dev_card_engine.json"},
    ).json()

    first_get = client.get(f"/sessions/{first['id']}").json()
    second_get = client.get(f"/sessions/{second['id']}").json()

    assert first_get["id"] != second_get["id"]

    patch_resp = client.patch(
        f"/sessions/{first['id']}",
        json={"turn_number": 9, "state": {"phase": "main"}},
    )
    assert patch_resp.status_code == 200
    updated = client.get(f"/sessions/{first['id']}").json()
    assert updated["turn_number"] == 9
