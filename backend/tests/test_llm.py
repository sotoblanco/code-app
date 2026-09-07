from llm import load_settings, validate_settings


def _clear_llm_env(monkeypatch):
    for key in (
        "LLM_PROVIDER",
        "LLM_API_KEY",
        "LLM_MODEL",
        "LLM_API_BASE",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "GEMINI_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)


def test_unconfigured_without_env(monkeypatch):
    _clear_llm_env(monkeypatch)
    settings = load_settings()
    assert settings.provider == ""
    assert settings.is_configured is False


def test_openai_alias_from_openai_api_key(monkeypatch):
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    settings = load_settings()
    assert settings.provider == "openai"
    assert settings.is_configured is True


def test_ollama_does_not_need_a_key(monkeypatch):
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    settings = load_settings()
    assert settings.is_configured is True
    assert settings.has_key is False
    assert settings.effective_base() == "http://localhost:11434/v1"


def test_validate_openai_requires_key():
    try:
        validate_settings("openai", api_key="")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "API key" in str(exc)


def test_default_models_and_suggested_options():
    from llm import PROVIDERS

    assert PROVIDERS["gemini"].default_model == "gemini-3.5-flash-lite"
    assert "gemini-3.5-flash-lite" in PROVIDERS["gemini"].suggested_models
    assert PROVIDERS["openai"].default_model == "gpt-5.6-luna"
    assert "gpt-5.6-luna" in PROVIDERS["openai"].suggested_models
    assert PROVIDERS["groq"].default_model == "openai/gpt-oss-20b"
    assert "openai/gpt-oss-20b" in PROVIDERS["groq"].suggested_models
    assert PROVIDERS["openrouter"].default_model == "openai/gpt-5.6-luna"


def test_is_connection_error_and_format_ollama_error():
    from llm import format_ollama_error, is_connection_error

    # Connection error tests
    err1 = ConnectionRefusedError("[Errno 61] Connection refused")
    assert is_connection_error(err1) is True

    msg1 = format_ollama_error(err1, "http://localhost:11434/v1")
    assert "Could not reach Ollama at http://localhost:11434" in msg1
    assert "ollama serve" in msg1

    # Custom endpoint
    msg_custom = format_ollama_error(err1, "http://192.168.1.50:11434/v1")
    assert "Could not reach Ollama at http://192.168.1.50:11434" in msg_custom

    # Model not found test
    err_not_found = Exception("404 Not Found: model 'llama3.2' not found")
    msg2 = format_ollama_error(err_not_found, "http://localhost:11434/v1")
    assert "Ollama model not found" in msg2
    assert "ollama pull" in msg2

    # Unrelated error
    err_val = ValueError("Invalid input")
    assert is_connection_error(err_val) is False


def test_ai_service_ollama_unreachable_friendly_messaging(monkeypatch):
    import pytest

    from ai_service import ai_service
    from llm import validate_settings

    settings = validate_settings("ollama", api_base="http://localhost:59999/v1")
    ai_service.configure(
        provider=settings.provider,
        model=settings.model,
        api_base=settings.api_base,
    )

    class MockCompletions:
        def create(self, *args, **kwargs):
            raise ConnectionRefusedError("[Errno 61] Connection refused")

    class MockChat:
        completions = MockCompletions()

    class MockClient:
        chat = MockChat()

    monkeypatch.setattr(ai_service, "client", MockClient())

    # Test chat() returns friendly string
    chat_res = ai_service.chat([{"role": "user", "content": "Hello"}])
    assert "Could not reach Ollama at http://localhost:59999" in chat_res
    assert "ollama serve" in chat_res

    # Test complete() raises RuntimeError with friendly string
    with pytest.raises(RuntimeError) as exc_info:
        ai_service.complete("Hello")
    assert "Could not reach Ollama at http://localhost:59999" in str(exc_info.value)
    assert "ollama serve" in str(exc_info.value)

    # Test evaluate_drawing() returns friendly error dict
    draw_res = ai_service.evaluate_drawing("draw a line", b"dummy1", b"dummy2")
    assert "Could not reach Ollama at http://localhost:59999" in draw_res.get("error", "")
    assert "ollama serve" in draw_res.get("error", "")
