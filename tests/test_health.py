from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_200_when_ollama_up():
    with patch("app.main.check_ollama_health") as mock_check:
        mock_check.return_value = None
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["ollama"] == "ok"
    assert body["model"] == "qwen2.5"


def test_health_returns_502_when_ollama_down():
    from app.ollama import OllamaError

    with patch("app.main.check_ollama_health", side_effect=OllamaError("connection refused")):
        response = client.get("/health")

    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail["ollama"] == "unavailable"
