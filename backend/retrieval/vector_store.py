"""
retrieval/vector_store.py

ChromaDB wrapper for storing and querying approved review chunks.

Collection schema (one collection: "approved_reviews_holistic"):
  - id:        "{tool_name}__{chunk_index}"
  - embedding: 1536-dim float vector (text-embedding-3-small)
  - document:  raw chunk text (stored for context window injection)
  - metadata:
      tool_name       str   e.g. "Lovable"
      tool_category   str   e.g. "AI code generation"
      heading         str   e.g. "Pricing"
      review_date     str   ISO date
      approved        bool  always True in this collection
      char_count      int

Retrieval strategy:
  - Return top-K most semantically similar chunks across the entire database.
  - If no results above threshold → caller uses rubric-only mode
"""

import chromadb
from chromadb.config import Settings as ChromaSettings
from ingestion.chunker import Chunk
from config import settings


def _get_collection():
    client = chromadb.PersistentClient(
        path=settings.chroma_persist_dir,
        settings=ChromaSettings(anonymized_telemetry=False),
    )
    return client.get_or_create_collection(
        name="approved_reviews_holistic",  # new collection to avoid schema conflicts
        metadata={"hnsw:space": "cosine"},   # cosine similarity for text
    )


def upsert_chunks(
    chunks: list[Chunk],
    embeddings: list[list[float]],
    tool_name: str,
    tool_category: str,
    review_date: str,
) -> int:
    """
    Store chunks + embeddings into Chroma.
    Returns number of chunks stored.
    """
    if len(chunks) != len(embeddings):
        raise ValueError("chunks and embeddings lists must have same length")

    collection = _get_collection()

    ids, docs, metas, vecs = [], [], [], []
    for i, (chunk, vec) in enumerate(zip(chunks, embeddings)):
        chunk_id = f"{tool_name}__{i}"
        ids.append(chunk_id)
        docs.append(chunk.content)
        vecs.append(vec)
        metas.append({
            "tool_name": tool_name,
            "tool_category": tool_category,
            "heading": chunk.heading,
            "review_date": review_date,
            "aayush_approved": True,
            "char_count": chunk.char_count,
        })

    collection.upsert(ids=ids, documents=docs, embeddings=vecs, metadatas=metas)
    return len(ids)


def retrieve_similar_chunks(
    query_embedding: list[float],
    top_k: int | None = None,
) -> list[dict]:
    """
    Retrieve top-K approved chunks across the whole database that are semantically similar.

    Returns list of dicts with keys: id, document, metadata, distance, similarity.

    Only returns chunks above settings.min_similarity threshold.
    Empty list → caller should use rubric-only mode.
    """
    k = top_k or settings.top_k_retrieval
    collection = _get_collection()

    try:
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )
    except Exception:
        return []

    docs     = results["documents"][0]
    metas    = results["metadatas"][0]
    distances = results["distances"][0]   # cosine distance: 0 = identical, 2 = opposite

    output = []
    for doc, meta, dist in zip(docs, metas, distances):
        similarity = 1 - (dist / 2)   # convert cosine distance → similarity [0,1]
        if similarity >= settings.min_similarity:
            output.append({
                "document": doc,
                "metadata": meta,
                "similarity": round(similarity, 4),
            })

    return output


def list_ingested_tools() -> list[dict]:
    """Return distinct tools currently in the vector store."""
    collection = _get_collection()
    all_metas = collection.get(include=["metadatas"])["metadatas"]
    seen = {}
    for m in all_metas:
        key = m["tool_name"]
        if key not in seen:
            seen[key] = {"tool_name": key, "tool_category": m["tool_category"], "review_date": m["review_date"]}
    return list(seen.values())


def count_chunks() -> int:
    return _get_collection().count()
