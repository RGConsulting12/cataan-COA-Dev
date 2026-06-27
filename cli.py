"""Terminal client for Catan COA recommendations."""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:8080"
OUTPUT_WIDTH = 72


class CliError(Exception):
    """User-facing CLI error with a clear message."""


def recommend_post(base_url: str, game_state: dict) -> dict:
    """POST game state to ``{base_url}/recommend`` and return parsed JSON."""
    url = f"{base_url.rstrip('/')}/recommend"
    try:
        response = httpx.post(url, json=game_state, timeout=60.0)
    except httpx.ConnectError as exc:
        raise CliError(
            f"Cannot connect to API at {base_url.rstrip('/')}. "
            "Is the server running?"
        ) from exc
    except httpx.TimeoutException as exc:
        raise CliError(
            f"Request timed out connecting to {base_url.rstrip('/')}."
        ) from exc
    except httpx.RequestError as exc:
        raise CliError(f"Network error: {exc}") from exc

    if response.status_code == 200:
        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise CliError("Invalid JSON in API response.") from exc

    detail: Any
    try:
        body = response.json()
        detail = body.get("detail", body)
    except json.JSONDecodeError:
        detail = response.text or f"HTTP {response.status_code}"

    raise CliError(format_api_error(response.status_code, detail))


def format_api_error(status_code: int, detail: Any) -> str:
    """Map API error payloads to user-friendly CLI messages."""
    if status_code == 422:
        messages: list[str] = []
        if isinstance(detail, list):
            for item in detail:
                if not isinstance(item, dict):
                    continue
                if "message" in item:
                    messages.append(str(item["message"]))
                elif "msg" in item:
                    loc = ".".join(str(part) for part in item.get("loc", []))
                    msg = str(item["msg"])
                    messages.append(f"{loc}: {msg}" if loc else msg)
        if messages:
            return "Validation error: " + "; ".join(messages[:3])
        return "Validation error: the game state JSON is invalid."

    if status_code == 502:
        if isinstance(detail, dict):
            ollama = detail.get("ollama", "unavailable")
            message = detail.get(
                "message",
                "The recommendation service is unavailable.",
            )
            return f"Service error ({ollama}): {message}"
        return (
            "Service error: the recommendation service is unavailable. "
            "Check that the API and Ollama are running."
        )

    if isinstance(detail, str):
        return f"API error (HTTP {status_code}): {detail}"
    return f"Unexpected API error (HTTP {status_code})."


def load_game_state(path: Path) -> dict:
    """Read and parse a game-state JSON file."""
    if not path.is_file():
        raise CliError(f"File not found: {path}")
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CliError(f"File not found: {path}") from exc
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise CliError(f"Invalid JSON: {exc.msg} at line {exc.lineno}, column {exc.colno}")
    if not isinstance(data, dict):
        raise CliError("Invalid JSON: root value must be an object.")
    return data


def format_recommendation(rec: dict[str, Any]) -> str:
    """Pretty-print one recommendation block."""
    rank = rec["rank"]
    action_type = rec["action_type"]
    summary = rec["summary"]
    rationale = rec["rationale"]
    line = f"{rank}. [{action_type}] {summary} (Rationale: {rationale})"
    return textwrap.fill(
        line,
        width=OUTPUT_WIDTH,
        subsequent_indent="   ",
        break_long_words=False,
        break_on_hyphens=False,
    )


def format_recommendations(response: dict[str, Any]) -> str:
    """Format the full recommend API response for terminal output."""
    lines: list[str] = []
    active_player = response.get("active_player")
    if active_player:
        lines.append(f"Active player: {active_player}")
        lines.append("")

    recommendations = sorted(
        response["recommendations"],
        key=lambda rec: rec["rank"],
    )
    for index, rec in enumerate(recommendations):
        lines.append(format_recommendation(rec))
        if index < len(recommendations) - 1:
            lines.append("")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli",
        description="Catan COA recommendation terminal client.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    recommend_parser = subparsers.add_parser(
        "recommend",
        help="Get ranked course-of-action recommendations for a game state file.",
    )
    recommend_parser.add_argument(
        "--file",
        required=True,
        metavar="PATH",
        help="Path to a JSON game state file.",
    )
    recommend_parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        metavar="URL",
        help=f"API base URL (default: {DEFAULT_BASE_URL}).",
    )
    return parser


def cmd_recommend(file: str, base_url: str) -> int:
    """Run the recommend subcommand."""
    game_state = load_game_state(Path(file))
    response = recommend_post(base_url, game_state)
    sys.stdout.write(format_recommendations(response))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "recommend":
            return cmd_recommend(args.file, args.base_url)
    except CliError as exc:
        print(exc, file=sys.stderr)
        return 1

    parser.error(f"Unknown command: {args.command}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
