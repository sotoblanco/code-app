"""Provider-agnostic LLM settings.

Chat, tutoring, course generation, and drawing evaluation use the OpenAI
Chat Completions API so any compatible server works.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

PROVIDER_ORDER = (
    "gemini",
    "groq",
    "ollama",
    "lmstudio",
    "openai",
    "openrouter",
    "custom",
)


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    name: str
    default_model: str
    default_base: str | None
    needs_key: bool
    docs_url: str
    blurb: str
    group: str
    dummy_key: str = "not-needed"
    suggested_models: tuple[str, ...] = ()


PROVIDERS: dict[str, ProviderSpec] = {
    "gemini": ProviderSpec(
        id="gemini",
        name="Google Gemini",
        default_model="gemini-3.5-flash-lite",
        default_base="https://generativelanguage.googleapis.com/v1beta/openai/",
        needs_key=True,
        docs_url="https://aistudio.google.com/app/apikey",
        blurb="Free key from Google AI Studio",
        group="free",
        suggested_models=("gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.1-flash-lite"),
    ),
    "groq": ProviderSpec(
        id="groq",
        name="Groq",
        default_model="openai/gpt-oss-20b",
        default_base="https://api.groq.com/openai/v1",
        needs_key=True,
        docs_url="https://console.groq.com/keys",
        blurb="Fast cloud models, free tier",
        group="free",
        suggested_models=(
            "openai/gpt-oss-20b",
            "llama-3.3-70b-versatile",
            "qwen/qwen3.8-27b",
            "llama-3.1-8b-instant",
        ),
    ),
    "ollama": ProviderSpec(
        id="ollama",
        name="Ollama",
        default_model="llama3.2",
        default_base="http://localhost:11434/v1",
        needs_key=False,
        docs_url="https://ollama.com",
        blurb="Local models, no API key",
        group="free",
        dummy_key="ollama",
        suggested_models=("llama3.2", "qwen2.5-coder:7b", "llama3.3"),
    ),
    "lmstudio": ProviderSpec(
        id="lmstudio",
        name="LM Studio",
        default_model="local-model",
        default_base="http://localhost:1234/v1",
        needs_key=False,
        docs_url="https://lmstudio.ai",
        blurb="Local desktop app, no API key",
        group="free",
        dummy_key="lmstudio",
        suggested_models=("local-model",),
    ),
    "openai": ProviderSpec(
        id="openai",
        name="OpenAI",
        default_model="gpt-5.6-luna",
        default_base="https://api.openai.com/v1",
        needs_key=True,
        docs_url="https://platform.openai.com/api-keys",
        blurb="GPT models",
        group="key",
        suggested_models=("gpt-5.6-luna", "gpt-5-mini", "gpt-5.6-terra", "gpt-6-astra"),
    ),
    "openrouter": ProviderSpec(
        id="openrouter",
        name="OpenRouter",
        default_model="openai/gpt-5.6-luna",
        default_base="https://openrouter.ai/api/v1",
        needs_key=True,
        docs_url="https://openrouter.ai/keys",
        blurb="One key, many models",
        group="key",
        suggested_models=(
            "openai/gpt-5.6-luna",
            "google/gemini-3.5-flash-lite",
            "meta-llama/llama-4-scout",
            "deepseek/deepseek-v4-flash-latest",
        ),
    ),
    "custom": ProviderSpec(
        id="custom",
        name="Custom endpoint",
        default_model="gpt-5.6-luna",
        default_base=None,
        needs_key=False,
        docs_url="",
        blurb="Any OpenAI-compatible URL",
        group="key",
        dummy_key="custom",
        suggested_models=("gpt-5.6-luna",),
    ),
}


@dataclass(frozen=True)
class LLMSettings:
    provider: str
    model: str
    api_key: str
    api_base: str | None

    @property
    def spec(self) -> ProviderSpec | None:
        return PROVIDERS.get(self.provider)

    @property
    def is_configured(self) -> bool:
        spec = self.spec
        if spec is None:
            return False
        if spec.needs_key and not self.api_key:
            return False
        if self.provider == "custom" and not self.api_base:
            return False
        return True

    @property
    def has_key(self) -> bool:
        return bool(self.api_key)

    def effective_key(self) -> str:
        if self.api_key:
            return self.api_key
        spec = self.spec
        return spec.dummy_key if spec else "not-needed"

    def effective_base(self) -> str | None:
        if self.api_base:
            return self.api_base
        spec = self.spec
        return spec.default_base if spec else None


def _first_env(*names: str) -> str:
    for name in names:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return ""


def load_settings() -> LLMSettings:
    """Read LLM_* first, then common aliases so existing .env files still work."""
    provider = _first_env("LLM_PROVIDER").lower()
    api_key = _first_env("LLM_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY")
    model = _first_env("LLM_MODEL")
    api_base = _first_env("LLM_API_BASE", "OPENAI_BASE_URL") or None

    if not provider:
        if os.environ.get("GEMINI_API_KEY", "").strip():
            provider = "gemini"
        elif os.environ.get("OPENAI_API_KEY", "").strip():
            provider = "openai"

    spec = PROVIDERS.get(provider)
    if spec:
        if not model:
            model = spec.default_model
        if not api_base:
            api_base = spec.default_base

    return LLMSettings(
        provider=provider,
        model=model,
        api_key=api_key,
        api_base=api_base,
    )


def validate_settings(
    provider: str,
    api_key: str = "",
    model: str | None = None,
    api_base: str | None = None,
) -> LLMSettings:
    provider = (provider or "").strip().lower()
    if provider not in PROVIDERS:
        known = ", ".join(PROVIDER_ORDER)
        raise ValueError(f"Unknown LLM provider '{provider}'. Choose one of: {known}")

    spec = PROVIDERS[provider]
    key = (api_key or "").strip()
    chosen_model = (model or "").strip() or spec.default_model
    chosen_base = (api_base or "").strip() or spec.default_base

    if spec.needs_key and not key:
        raise ValueError(f"{spec.name} requires an API key.")
    if provider == "custom" and not chosen_base:
        raise ValueError("Custom provider requires an API base URL (OpenAI-compatible).")

    return LLMSettings(
        provider=provider,
        model=chosen_model,
        api_key=key,
        api_base=chosen_base,
    )


def apply_settings_to_env(settings: LLMSettings) -> None:
    os.environ["LLM_PROVIDER"] = settings.provider
    os.environ["LLM_MODEL"] = settings.model
    if settings.api_key:
        os.environ["LLM_API_KEY"] = settings.api_key
    elif "LLM_API_KEY" in os.environ:
        del os.environ["LLM_API_KEY"]
    if settings.api_base:
        os.environ["LLM_API_BASE"] = settings.api_base
    elif "LLM_API_BASE" in os.environ:
        del os.environ["LLM_API_BASE"]


def build_client(settings: LLMSettings):
    from openai import OpenAI

    kwargs: dict[str, object] = {
        "api_key": settings.effective_key(),
        "timeout": 60.0,
    }
    base = settings.effective_base()
    if base:
        kwargs["base_url"] = base
    return OpenAI(**kwargs)


def providers_public() -> list[dict[str, object]]:
    return [
        {
            "id": PROVIDERS[pid].id,
            "name": PROVIDERS[pid].name,
            "needs_key": PROVIDERS[pid].needs_key,
            "default_model": PROVIDERS[pid].default_model,
            "default_base": PROVIDERS[pid].default_base,
            "docs_url": PROVIDERS[pid].docs_url,
            "blurb": PROVIDERS[pid].blurb,
            "group": PROVIDERS[pid].group,
            "suggested_models": list(PROVIDERS[pid].suggested_models),
        }
        for pid in PROVIDER_ORDER
    ]


def is_connection_error(exc: Exception) -> bool:
    """Determine whether an exception represents a network connection failure."""
    import openai
    import requests

    if isinstance(
        exc,
        (
            openai.APIConnectionError,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            ConnectionRefusedError,
            ConnectionError,
            OSError,
        ),
    ):
        return True

    err_str = f"{exc} {getattr(exc, '__cause__', '')}".lower()
    keywords = (
        "connection refused",
        "connect error",
        "connection error",
        "connect call failed",
        "failed to establish a new connection",
        "errno 61",
        "errno 111",
        "timeout",
        "timed out",
    )
    return any(kw in err_str for kw in keywords)


def format_ollama_error(exc: Exception, base_url: str | None = None) -> str:
    """Return a clear, friendly error message when Ollama is unreachable or model missing."""
    base = (base_url or "http://localhost:11434/v1").rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    if not base:
        base = "http://localhost:11434"

    err_str = f"{exc}".lower()
    if (
        "not_found" in err_str
        or "404" in err_str
        or ("model" in err_str and "not found" in err_str)
    ):
        return (
            "Ollama model not found. Make sure to pull the model first using `ollama pull <model>`."
        )

    return f"Could not reach Ollama at {base}. Make sure Ollama is running (`ollama serve`)."
