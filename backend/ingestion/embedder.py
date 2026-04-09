"""
ingestion/embedder.py

Wraps Ollama's nomic-embed-text for generating chunk embeddings locally.

Model: nomic-embed-text
  - 768 dimensions
  - Runs fully local via Ollama — no API key, no cost
  - Pull once with: ollama pull nomic-embed-text
"""

import httpx
import ollama
from fastapi import HTTPException
from config import settings

_client = ollama.Client(host=settings.ollama_base_url)


def _check_ollama_alive():
    """
    Ping Ollama and raise a clean 503 if it's not reachable.
    Called as a fallback inside embed_texts so the user gets a
    human-readable error instead of a raw connection traceback.
    """
    try:
        r = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=3.0)
        if r.status_code != 200:
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Embedding service returned HTTP {r.status_code}. "
                    "Try restarting Ollama: ollama serve"
                ),
            )
        # Check the required model is present
        model_names = [m["name"] for m in r.json().get("models", [])]
        base_names  = [n.split(":")[0] for n in model_names]
        embed_base  = settings.ollama_embed_model.split(":")[0]
        if embed_base not in base_names:
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Ollama is running but the embed model '{settings.ollama_embed_model}' "
                    f"is not installed. Fix with: ollama pull {settings.ollama_embed_model}"
                ),
            )
    except HTTPException:
        raise  # re-raise our own 503s unchanged
    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail=(
                "Embedding service (Ollama) is offline. "
                "Start it with: ollama serve   "
                "then retry your request."
            ),
        )


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of strings. Returns a list of float vectors.
    Raises HTTP 503 with a clear message if Ollama is not running.
    """
    if not texts:
        return []

    try:
        response = _client.embed(
            model=settings.ollama_embed_model,
            input=texts,
        )
        return response.embeddings

    except HTTPException:
        raise  # already formatted

    except Exception:
        # Something went wrong — check if Ollama is the root cause
        _check_ollama_alive()
        # If Ollama is alive but embed still failed, surface a generic 500
        raise HTTPException(
            status_code=500,
            detail=(
                "Embedding failed for an unknown reason. "
                "Check that Ollama is running and the model is loaded."
            ),
        )


def embed_single(text: str) -> list[float]:
    """Convenience wrapper for embedding a single string."""
    return embed_texts([text])[0]
