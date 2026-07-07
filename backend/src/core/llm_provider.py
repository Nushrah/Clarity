import os
import logging
from typing import Optional, Dict, Any, List

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()
logger = logging.getLogger(__name__)


def _base_kwargs() -> Dict[str, Any]:
    provider = os.getenv("LLM_PROVIDER", "openrouter").lower()
    if provider != "openrouter":
        raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is missing. Add it to backend/.env")

    return {
        "api_key": api_key,
        "base_url": os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        "temperature": float(os.getenv("LLM_TEMPERATURE", "0.2")),
        "max_retries": 0,
        # Bound each request so a stalled free-tier call fails fast instead of
        # hanging the whole request (e.g. blocking scorecard generation forever).
        "timeout": float(os.getenv("LLM_TIMEOUT", "120")),
        "default_headers": {
            "HTTP-Referer": os.getenv("APP_URL", "http://localhost:5173"),
            "X-Title": "Clarity",
        },
    }


def _configured_model_names() -> List[str]:
    """Return primary + fallback model names from environment, preserving order."""
    names = [
        os.getenv("OPENROUTER_FREE_MODEL", "openrouter/free"),
        os.getenv("OPENROUTER_FALLBACK_MODEL"),
        os.getenv("OPENROUTER_FALLBACK_MODEL_2"),
    ]
    names.extend(
        name.strip()
        for name in os.getenv("OPENROUTER_FALLBACK_MODELS", "").split(",")
        if name.strip()
    )

    seen = set()
    ordered = []
    for name in names:
        if name and name not in seen:
            ordered.append(name)
            seen.add(name)
    return ordered


def _is_retryable_provider_error(exc: Exception) -> bool:
    message = str(exc).lower()
    retryable_markers = (
        "429",
        "rate limit",
        "rate-limited",
        "temporarily unavailable",
        "provider returned error",
        "upstream",
    )
    return any(marker in message for marker in retryable_markers)


class OpenRouterFallbackChat:
    """Small wrapper that falls back across configured OpenRouter models."""

    def __init__(self, model_names: List[str], kwargs: Dict[str, Any]):
        self.model_names = model_names
        self._models = [
            ChatOpenAI(model=model_name, **kwargs)
            for model_name in model_names
        ]

    def invoke(self, prompt):
        last_error = None
        for model_name, model in zip(self.model_names, self._models):
            try:
                return model.invoke(prompt)
            except Exception as exc:
                last_error = exc
                if not _is_retryable_provider_error(exc):
                    raise
                logger.warning("OpenRouter model %s failed; trying fallback if configured.", model_name)
        raise last_error


def get_llm(model_type: str = "default"):
    return OpenRouterFallbackChat(_configured_model_names(), _base_kwargs())


def get_chat_model(
    model_name: Optional[str] = None,
    response_format: Optional[Dict[str, Any]] = None,
) -> ChatOpenAI:
    """Build a chat model for a specific OpenRouter model, optionally with a
    strict JSON-schema response_format. Used by the hiring pipeline's
    model-fallback chain."""
    kwargs = _base_kwargs()
    if response_format:
        kwargs["model_kwargs"] = {"response_format": response_format}
    return ChatOpenAI(
        model=model_name or os.getenv("OPENROUTER_FREE_MODEL", "openrouter/free"),
        **kwargs,
    )
