"""
ingestion/embedder.py

Wraps Ollama's nomic-embed-text for generating chunk embeddings locally.

Model: nomic-embed-text
  - 768 dimensions
  - Runs fully local via Ollama — no API key, no cost
  - Pull once with: ollama pull nomic-embed-text
"""

import ollama
from config import settings

_client = ollama.Client(host=settings.ollama_base_url)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of strings. Returns a list of float vectors.
    """
    if not texts:
        return []

    response = _client.embed(
        model=settings.ollama_embed_model,
        input=texts,
    )
    return response.embeddings


def embed_single(text: str) -> list[float]:
    """Convenience wrapper for embedding a single string."""
    return embed_texts([text])[0]
