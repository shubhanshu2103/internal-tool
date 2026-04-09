"""
ingestion/embedder.py

Wraps Jina AI's embedding API for generating chunk embeddings.

Model: jina-embeddings-v2-base-en
  - 768 dimensions — compatible with existing ChromaDB collection
  - Free tier: 1M tokens, no credit card required
  - External API — works in any deployment (no local process needed)
  - Get a free key at: jina.ai
"""

import httpx
from fastapi import HTTPException
from config import settings

JINA_EMBED_URL = "https://api.jina.ai/v1/embeddings"


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of strings using Jina AI.
    Returns a list of 768-dim float vectors.
    Raises clean HTTP errors if the API call fails.
    """
    if not texts:
        return []

    headers = {
        "Authorization": f"Bearer {settings.jina_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.jina_embed_model,
        "input": texts,
    }

    try:
        response = httpx.post(
            JINA_EMBED_URL,
            headers=headers,
            json=payload,
            timeout=30.0,
        )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Jina AI embedding request timed out. Retry in a moment.",
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot reach Jina AI API. Check your internet connection. ({exc})",
        )

    if response.status_code == 401:
        raise HTTPException(
            status_code=401,
            detail=(
                "Jina AI API key is invalid or missing. "
                "Set JINA_API_KEY in your .env file. "
                "Get a free key at: jina.ai"
            ),
        )
    if response.status_code == 429:
        raise HTTPException(
            status_code=429,
            detail=(
                "Jina AI free tier quota exceeded (1M tokens). "
                "Check usage at: cloud.jina.ai"
            ),
        )
    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Jina AI returned unexpected status {response.status_code}: {response.text[:200]}",
        )

    data = response.json()
    # Sort by index to guarantee order matches input
    items = sorted(data["data"], key=lambda x: x["index"])
    return [item["embedding"] for item in items]


def embed_single(text: str) -> list[float]:
    """Convenience wrapper for embedding a single string."""
    return embed_texts([text])[0]
