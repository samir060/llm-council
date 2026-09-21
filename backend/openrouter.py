"""OpenRouter API client for making LLM requests."""

import os
import asyncio
from contextvars import ContextVar
from typing import List, Dict, Any, Optional

import httpx

from .config import OPENROUTER_API_URL

_request_api_key: ContextVar[Optional[str]] = ContextVar(
    "openrouter_request_api_key", default=None
)


def set_request_api_key(api_key: Optional[str]):
    key = (api_key or "").strip()
    return _request_api_key.set(key or None)


def reset_request_api_key(token) -> None:
    _request_api_key.reset(token)


def get_api_key() -> str:
    return (_request_api_key.get() or os.getenv("OPENROUTER_API_KEY") or "").strip()


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0,
    retries: int = 2,
) -> Optional[Dict[str, Any]]:
    """Query a single model via OpenRouter API with light retry/fallback handling."""
    api_key = get_api_key()
    if not api_key:
        print(f"Error querying model {model}: OpenRouter API key is missing")
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"model": model, "messages": messages}

    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    OPENROUTER_API_URL,
                    headers=headers,
                    json=payload,
                )

                # Retry transient/rate-limit/provider errors.
                if response.status_code in (408, 409, 429, 500, 502, 503, 504):
                    if attempt < retries:
                        await asyncio.sleep(1.5 * (attempt + 1))
                        continue

                response.raise_for_status()
                data = response.json()

                choices = data.get("choices") or []
                if not choices:
                    err = data.get("error") or data.get("message") or "No choices returned"
                    print(f"Error querying model {model}: {err}")
                    if attempt < retries:
                        await asyncio.sleep(1.0 * (attempt + 1))
                        continue
                    return None

                message = choices[0].get("message") or {}
                content = message.get("content")
                if not content:
                    if attempt < retries:
                        await asyncio.sleep(1.0 * (attempt + 1))
                        continue
                    return None

                return {
                    "content": content,
                    "reasoning_details": message.get("reasoning_details"),
                }

        except Exception as e:
            print(f"Error querying model {model}: {e}")
            if attempt < retries:
                await asyncio.sleep(1.5 * (attempt + 1))
                continue
            return None

    return None


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]],
) -> Dict[str, Optional[Dict[str, Any]]]:
    """Query models with a slight stagger to reduce free-tier burst rate limits."""
    async def delayed_query(index: int, model: str):
        if index:
            await asyncio.sleep(index * 0.8)
        return await query_model(model, messages)

    tasks = [delayed_query(i, model) for i, model in enumerate(models)]
    responses = await asyncio.gather(*tasks)
    return {model: response for model, response in zip(models, responses)}
