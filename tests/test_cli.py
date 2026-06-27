import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

import cli

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_game_state.json"
REPO_ROOT = Path(__file__).resolve().parents[1]

SAMPLE_RESPONSE = {
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


@pytest.fixture
def sample_game_state() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "cli", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def test_recommend_post_success(sample_game_state: dict):
    with patch("cli.httpx.post") as mock_post:
        mock_response = mock_post.return_value
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_RESPONSE

        result = cli.recommend_post("http://127.0.0.1:8080", sample_game_state)

    assert result == SAMPLE_RESPONSE
    mock_post.assert_called_once_with(
        "http://127.0.0.1:8080/recommend",
        json=sample_game_state,
        timeout=60.0,
    )


def test_recommend_post_uses_custom_base_url(sample_game_state: dict):
    with patch("cli.httpx.post") as mock_post:
        mock_response = mock_post.return_value
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_RESPONSE

        cli.recommend_post("http://api.example:9000", sample_game_state)

    mock_post.assert_called_once_with(
        "http://api.example:9000/recommend",
        json=sample_game_state,
        timeout=60.0,
    )


def test_cli_recommend_happy_path_prints_three_coas(sample_game_state: dict, capsys):
    with patch("cli.recommend_post", return_value=SAMPLE_RESPONSE):
        exit_code = cli.main(
            ["recommend", "--file", str(FIXTURE_PATH)],
        )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Active player: red" in captured.out
    assert "[build_city]" in captured.out
    assert "[maritime_trade]" in captured.out
    assert "[end_turn]" in captured.out
    assert captured.out.count("(Rationale:") == 3
    assert "1. [build_city]" in captured.out
    assert "2. [maritime_trade]" in captured.out
    assert "3. [end_turn]" in captured.out


def test_cli_recommend_custom_base_url(sample_game_state: dict):
    with patch("cli.recommend_post", return_value=SAMPLE_RESPONSE) as mock_post:
        exit_code = cli.main(
            [
                "recommend",
                "--file",
                str(FIXTURE_PATH),
                "--base-url",
                "http://localhost:9999",
            ],
        )

    assert exit_code == 0
    mock_post.assert_called_once_with("http://localhost:9999", sample_game_state)


def test_cli_file_not_found():
    result = _run_cli("recommend", "--file", "NONEXISTENT.json")
    assert result.returncode != 0
    assert "File not found" in result.stderr


def test_cli_invalid_json(tmp_path: Path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{not valid json", encoding="utf-8")

    result = _run_cli("recommend", "--file", str(bad_file))
    assert result.returncode != 0
    assert "Invalid JSON" in result.stderr


def test_recommend_post_validation_error_422(sample_game_state: dict):
    detail = [
        {
            "field": "proposed_actions[0].vertex_id",
            "code": "distance_rule_violation",
            "message": "Settlement cannot be placed adjacent to existing settlement at v1",
            "rules_ref": "§6 Building costs",
        }
    ]
    with patch("cli.httpx.post") as mock_post:
        mock_response = mock_post.return_value
        mock_response.status_code = 422
        mock_response.json.return_value = {"detail": detail}

        with pytest.raises(cli.CliError) as exc_info:
            cli.recommend_post("http://127.0.0.1:8080", sample_game_state)

    assert "Validation error" in str(exc_info.value)
    assert "Settlement cannot be placed" in str(exc_info.value)


def test_cli_api_validation_error_exit_nonzero(sample_game_state: dict):
    with patch(
        "cli.recommend_post",
        side_effect=cli.CliError(
            "Validation error: active_player must match a player id."
        ),
    ):
        exit_code = cli.main(
            ["recommend", "--file", str(FIXTURE_PATH)],
        )

    assert exit_code == 1


def test_recommend_post_server_error_502(sample_game_state: dict):
    detail = {
        "status": "error",
        "ollama": "invalid_response",
        "message": "Failed to obtain valid recommendations",
    }
    with patch("cli.httpx.post") as mock_post:
        mock_response = mock_post.return_value
        mock_response.status_code = 502
        mock_response.json.return_value = {"detail": detail}

        with pytest.raises(cli.CliError) as exc_info:
            cli.recommend_post("http://127.0.0.1:8080", sample_game_state)

    message = str(exc_info.value)
    assert "Service error" in message
    assert "invalid_response" in message


def test_cli_api_server_error_exit_nonzero():
    with patch(
        "cli.recommend_post",
        side_effect=cli.CliError(
            "Service error (invalid_response): Failed to obtain valid recommendations"
        ),
    ):
        exit_code = cli.main(
            ["recommend", "--file", str(FIXTURE_PATH)],
        )

    assert exit_code == 1


def test_cli_missing_required_arg():
    result = _run_cli("recommend")
    assert result.returncode != 0
    assert "required" in result.stderr.lower()


def test_output_regression_format():
    output = cli.format_recommendations(SAMPLE_RESPONSE)
    expected = (
        "Active player: red\n"
        "\n"
        "1. [build_city] Upgrade settlement on strong ore hex. (Rationale:\n"
        "   Doubles ore production on a high-probability number.)\n"
        "\n"
        "2. [maritime_trade] Trade grain for ore at 4:1. (Rationale: Sets up a\n"
        "   city upgrade next turn.)\n"
        "\n"
        "3. [end_turn] End turn if no better trades appear. (Rationale: Preserves\n"
        "   resources when no build is affordable.)\n"
    )
    assert output == expected


def test_format_recommendation_wraps_long_rationale():
    rec = {
        "rank": 1,
        "action_type": "build_road",
        "summary": "Extend toward a strong wheat port.",
        "rationale": (
            "Secures early road length toward the wheat harbor while blocking "
            "blue from reaching the same intersection next turn."
        ),
    }
    formatted = cli.format_recommendation(rec)
    assert formatted.startswith("1. [build_road]")
    assert "\n   " in formatted


def test_recommend_post_connect_error(sample_game_state: dict):
    with patch(
        "cli.httpx.post",
        side_effect=httpx.ConnectError("connection refused"),
    ):
        with pytest.raises(cli.CliError) as exc_info:
            cli.recommend_post("http://127.0.0.1:8080", sample_game_state)

    assert "Cannot connect to API" in str(exc_info.value)
