"""OpenRouter API client for making LLM requests."""

import os
import asyncio
from contextvars import ContextVar
from typing import List, Dict, Any, Optional

import httpx

from .config import OPENROUTER_API_URL

# A request-scoped key lets the hosted app work without storing the user's
# OpenRouter key in Railway. The browser sends it over HTTPS for each request.
_request_api_key: ContextVar[Optional[str]] = ContextVar(
    "openrouter_request_api_key", default=None
)


def set_request_api_key(api_key: Optional[str]):
    key = (api_key or "").strip()
    return _request_api_key.set(key or None)


def reset_request_api_key(token) -> None:
    _request_api_key.reset(token)


def get_api_key() -> str:
    # Prefer a request-scoped key. Fall back to Railway/local environment.
    return (_request_api_key.get() or os.getenv("OPENROUTER_API_KEY") or "").strip()


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0
) -> Optional[Dict[str, Any]]:
    """Query a single model via OpenRouter API."""
    api_key = get_api_key()
    if not api_key:
        print(f"Error querying model {model}: OpenRouter API key is missing")
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                OPENROUTER_API_URL,
                headers=headers,
                json=payload
            )
            response.raise_for_status()

            data = response.json()
            message = data["choices"][0]["message"]

            return {
                "content": message.get("content"),
                "reasoning_details": message.get("reasoning_details"),
            }

    except Exception as e:
        print(f"Error querying model {model}: {e}")
        return None


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]]
) -> Dict[str, Optional[Dict[str, Any]]]:
    """Query multiple models in parallel."""
    tasks = [query_model(model, messages) for model in models]
    responses = await asyncio.gather(*tasks)
    return {model: response for model, response in zip(models, responses)}
