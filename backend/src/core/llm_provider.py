import os
from typing import Optional, Dict, Any

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


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


def get_llm(model_type: str = "default") -> ChatOpenAI:
    return ChatOpenAI(
        model=os.getenv("OPENROUTER_FREE_MODEL", "openrouter/free"),
        **_base_kwargs(),
    )


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
