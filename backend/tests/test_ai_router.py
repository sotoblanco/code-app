from ai_service import ai_service
from llm import load_settings, validate_settings


def test_ai_status_endpoint(client):
    res = client.get("/ai/status")
    assert res.status_code == 200
    data = res.json()
    assert "configured" in data
    assert "has_key" in data
    assert "provider" in data
    ids = {p["id"] for p in data["providers"]}
    assert {"gemini", "groq", "ollama", "openai", "openrouter", "lmstudio", "custom"} <= ids
    gemini = next(p for p in data["providers"] if p["id"] == "gemini")
    assert gemini["docs_url"] == "https://aistudio.google.com/app/apikey"
    assert gemini["group"] == "free"
    assert gemini["default_model"] == "gemini-3.5-flash-lite"
    assert "gemini-3.5-flash-lite" in gemini["suggested_models"]

    openai_p = next(p for p in data["providers"] if p["id"] == "openai")
    assert openai_p["default_model"] == "gpt-5.6-luna"
    assert "gpt-5.6-luna" in openai_p["suggested_models"]

    groq_p = next(p for p in data["providers"] if p["id"] == "groq")
    assert groq_p["default_model"] == "openai/gpt-oss-20b"
    assert "openai/gpt-oss-20b" in groq_p["suggested_models"]

    openrouter_p = next(p for p in data["providers"] if p["id"] == "openrouter")
    assert openrouter_p["default_model"] == "openai/gpt-5.6-luna"


def test_ai_configure_gemini_key(client, tmp_path, monkeypatch):
    dummy_env = tmp_path / ".env"
    dummy_env.write_text("SOME_VAR=123\n", encoding="utf-8")
    monkeypatch.setenv("ENV_FILE", str(dummy_env))
    monkeypatch.setenv("ALLOW_LOCAL_WELCOME", "true")

    res = client.post(
        "/ai/configure-key",
        json={"provider": "gemini", "api_key": "AIza-test-key", "model": "gemini-3.5-flash-lite"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["provider"] == "gemini"

    content = dummy_env.read_text(encoding="utf-8")
    assert "LLM_PROVIDER=gemini" in content
    assert "LLM_API_KEY=AIza-test-key" in content
    assert "GEMINI_API_KEY=AIza-test-key" in content
    assert ai_service.is_configured is True

    status = client.get("/ai/status").json()
    assert status["has_key"] is True
    assert status["provider"] == "gemini"


def test_bare_api_key_defaults_to_gemini(client, tmp_path, monkeypatch):
    dummy_env = tmp_path / ".env"
    dummy_env.write_text("", encoding="utf-8")
    monkeypatch.setenv("ENV_FILE", str(dummy_env))
    monkeypatch.setenv("ALLOW_LOCAL_WELCOME", "true")

    res = client.post("/ai/configure-key", json={"api_key": "AIza-legacy"})
    assert res.status_code == 200
    assert res.json()["provider"] == "gemini"


def test_ai_configure_ollama_without_key(client, tmp_path, monkeypatch):
    dummy_env = tmp_path / ".env"
    dummy_env.write_text("", encoding="utf-8")
    monkeypatch.setenv("ENV_FILE", str(dummy_env))
    monkeypatch.setenv("ALLOW_LOCAL_WELCOME", "true")

    res = client.post("/ai/configure-key", json={"provider": "ollama"})
    assert res.status_code == 200
    assert res.json()["provider"] == "ollama"
    assert "LLM_PROVIDER=ollama" in dummy_env.read_text(encoding="utf-8")
    assert ai_service.is_configured is True


def test_ai_configure_key_empty(client, monkeypatch):
    monkeypatch.setenv("ALLOW_LOCAL_WELCOME", "true")
    res = client.post("/ai/configure-key", json={"provider": "gemini", "api_key": "   "})
    assert res.status_code == 400


def test_gemini_env_alias_still_configures(monkeypatch):
    for key in ("LLM_PROVIDER", "LLM_API_KEY", "OPENAI_API_KEY", "LLM_MODEL", "LLM_API_BASE"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-legacy-key")
    settings = load_settings()
    assert settings.provider == "gemini"
    assert settings.api_key == "AIza-legacy-key"
    assert settings.is_configured is True


def test_validate_custom_requires_base():
    try:
        validate_settings("custom")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "API base" in str(exc)


def test_ai_configure_ollama_unreachable_friendly_error(client, monkeypatch):
    monkeypatch.setenv("ALLOW_LOCAL_WELCOME", "true")
    res = client.post(
        "/ai/configure-key",
        json={
            "provider": "ollama",
            "api_base": "http://localhost:59999/v1",
            "test_connection": True,
        },
    )
    assert res.status_code == 400
    detail = res.json()["detail"]
    assert "Could not reach Ollama at http://localhost:59999" in detail
    assert "ollama serve" in detail


def test_ai_configure_ollama_reachable_with_test_connection(client, tmp_path, monkeypatch):
    dummy_env = tmp_path / ".env"
    dummy_env.write_text("", encoding="utf-8")
    monkeypatch.setenv("ENV_FILE", str(dummy_env))
    monkeypatch.setenv("ALLOW_LOCAL_WELCOME", "true")

    class MockResponse:
        status_code = 200

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: MockResponse())

    res = client.post(
        "/ai/configure-key",
        json={
            "provider": "ollama",
            "model": "llama3.2",
            "api_base": "http://localhost:11434/v1",
            "test_connection": True,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["saved_to_file"] is True
    assert "connected successfully" in data["message"]
    assert "LLM_PROVIDER=ollama" in dummy_env.read_text(encoding="utf-8")


def test_ai_test_connection_endpoint(client, monkeypatch):
    monkeypatch.setenv("ALLOW_LOCAL_WELCOME", "true")

    class MockResponse:
        status_code = 200

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: MockResponse())

    res = client.post(
        "/ai/test-connection",
        json={"provider": "ollama", "model": "llama3.2"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "Successfully reached Ollama" in data["message"]

    import requests

    def mock_fail(*args, **kwargs):
        raise requests.exceptions.ConnectionError("Connection refused")

    monkeypatch.setattr("requests.get", mock_fail)
    res_fail = client.post(
        "/ai/test-connection",
        json={"provider": "ollama", "api_base": "http://localhost:59999/v1"},
    )
    assert res_fail.status_code == 400
    assert "Could not reach Ollama at http://localhost:59999" in res_fail.json()["detail"]


def test_ai_test_connection_forbidden_non_local(monkeypatch):
    from fastapi.testclient import TestClient

    from main import app

    monkeypatch.setenv("ALLOW_LOCAL_WELCOME", "false")
    remote_client = TestClient(app, client=("203.0.113.1", 12345))
    res = remote_client.post(
        "/ai/test-connection",
        json={"provider": "ollama"},
    )
    assert res.status_code == 403
