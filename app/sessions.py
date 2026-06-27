from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from app.models import GameSession, GameState, RecommendResponse, SessionPatch

REPO_ROOT = Path(__file__).resolve().parent.parent
SESSIONS_DIR = REPO_ROOT / "data" / "sessions"
EXAMPLES_DIR = REPO_ROOT / "examples"


class SessionNotFoundError(FileNotFoundError):
    """Raised when a session JSON file does not exist."""


class FixtureNotFoundError(FileNotFoundError):
    """Raised when an examples fixture file does not exist."""


def ensure_sessions_dir() -> None:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def list_example_states() -> list[str]:
    return sorted(path.name for path in EXAMPLES_DIR.glob("sample*.json"))


def _session_path(session_id: str) -> Path:
    return SESSIONS_DIR / f"{session_id}.json"


def load_session(session_id: str) -> GameSession:
    path = _session_path(session_id)
    if not path.is_file():
        raise SessionNotFoundError(session_id)
    data = json.loads(path.read_text(encoding="utf-8"))
    return GameSession.model_validate(data)


def save_session(session: GameSession) -> None:
    ensure_sessions_dir()
    path = _session_path(session.id)
    path.write_text(
        session.model_dump_json(indent=2),
        encoding="utf-8",
    )


def create_session_from_fixture(fixture_name: str, *, turn_number: int = 1) -> GameSession:
    path = EXAMPLES_DIR / fixture_name
    if not path.is_file():
        raise FixtureNotFoundError(fixture_name)
    state = GameState.model_validate(json.loads(path.read_text(encoding="utf-8")))
    label = fixture_name.removesuffix(".json").replace("_", " ")
    return create_session_from_state(
        state,
        label=label,
        source_fixture=fixture_name,
        turn_number=turn_number,
    )


def create_session_from_state(
    state: GameState,
    *,
    label: str | None = None,
    source_fixture: str | None = None,
    turn_number: int = 1,
) -> GameSession:
    now = datetime.now(timezone.utc)
    session = GameSession(
        id=str(uuid.uuid4()),
        turn_number=turn_number,
        label=label,
        source_fixture=source_fixture,
        state=state,
        created_at=now,
        updated_at=now,
    )
    save_session(session)
    return session


def patch_session(session_id: str, updates: SessionPatch) -> GameSession:
    session = load_session(session_id)
    payload = updates.model_dump(exclude_unset=True)

    if "turn_number" in payload:
        session.turn_number = payload["turn_number"]
    if "label" in payload:
        session.label = payload["label"]
    if "state" in payload:
        state_updates = payload["state"]
        merged = session.state.model_dump()
        merged.update(state_updates)
        try:
            session.state = GameState.model_validate(merged)
        except ValidationError as exc:
            raise exc

    session.updated_at = datetime.now(timezone.utc)
    save_session(session)
    return session


def recommend_for_session(
    session_id: str,
    *,
    rules_text: str,
    model: str,
    base_url: str,
) -> RecommendResponse:
    from app.ollama import recommend_with_retries

    session = load_session(session_id)
    return recommend_with_retries(
        game_state_json=session.state.model_dump_json(),
        rules_text=rules_text,
        model=model,
        base_url=base_url,
    )
