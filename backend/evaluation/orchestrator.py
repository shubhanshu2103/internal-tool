"""
evaluation/orchestrator.py

Orchestrates a full review evaluation holistically:
  1. Chunk the draft to get embeddings
  2. Retrieve similar approved chunks across the whole document
  3. Call judge with the full report and aggregated context
  4. Aggregate into EvaluationResult
"""

import uuid
import json
from datetime import datetime, timezone
from pathlib import Path
from ingestion.chunker import chunk_review
from ingestion.embedder import embed_texts
from retrieval.vector_store import retrieve_similar_chunks
from evaluation.evaluator import evaluate_draft
from evaluation.rubric_builder import load_rubric
from models import (
    EvaluationResult, EvaluateResponse, Label, HistoryEntry, Disposition
)
from config import settings


def _overall_label(score: float) -> Label:
    if score >= 7:
        return Label.PASS
    elif score >= 4:
        return Label.NOTE
    return Label.FAIL


def _approval_likelihood(dims: dict, overall_score: float) -> int:
    """
    Compute 0-100% probability of approval.
    Blends label distribution (65%) with normalised score (35%).
    Scales to 10-95% — never promises certainty in either direction.
    """
    weights = {Label.PASS: 1.0, Label.NOTE: 0.5, Label.FAIL: 0.0}
    label_score = sum(weights[d.label] for d in dims.values()) / len(dims)
    score_norm  = (overall_score - 1) / 9          # 1-10 → 0-1
    raw = label_score * 0.65 + score_norm * 0.35
    return round(10 + raw * 85)                     # → 10-95%


def run_evaluation(
    markdown: str,
    tool_name: str,
    tool_category: str,
) -> EvaluateResponse:
    """
    Full pipeline: chunk (for semantic retrieval) → retrieve → judge holistically → aggregate.
    Returns a complete EvaluateResponse.
    """

    # 1. Load rubric
    rubric = load_rubric()

    # 2. Chunk the draft to use them for vector similarity search
    chunks = chunk_review(markdown)

    # 3a. Embed chunks in batch
    embeddings = embed_texts([c.content for c in chunks])

    # 3b. Retrieve similar approved chunks globally across all segments
    retrieved_dict = {}
    for vec in embeddings:
        retrieved = retrieve_similar_chunks(query_embedding=vec, top_k=2)
        for r in retrieved:
            # deduplicate by document content
            retrieved_dict[r["document"]] = r

    unique_retrieved = list(retrieved_dict.values())
    unique_retrieved.sort(key=lambda x: x["similarity"], reverse=True)
    # Give the LLM top 5 most relevant contextual bites across the report
    top_context = unique_retrieved[:5]

    mode = "rag_grounded" if top_context else "rubric_only"
    print(f"[orchestrator] Holistic evaluation: {mode} ({len(top_context)} chunks retrieved)")

    # 4. Judge the document as a whole
    result_data = evaluate_draft(
        draft_content=markdown,
        retrieved_chunks=top_context,
        rubric=rubric,
    )

    dims = result_data["dimensions"]
    retrieval_mode = result_data["retrieval_mode"]

    # 5a. Extract RAG sources used as reference
    seen_sources = {}
    for c in top_context:
        key = f"{c['metadata']['tool_name']}|{c['metadata'].get('heading','')}"
        if key not in seen_sources:
            seen_sources[key] = {
                "tool_name": c["metadata"]["tool_name"],
                "heading":   c["metadata"].get("heading", "—"),
                "similarity": round(c["similarity"] * 100),
            }
    rag_sources = list(seen_sources.values())[:3]

    # 5b. Extract critical gaps and top suggestions from dimensions
    critical_gaps = []
    items = []
    
    for dim_name, dim in dims.items():
        if dim.label == Label.FAIL:
            critical_gaps.append(f"{dim_name.capitalize()} FAIL (score {dim.score}/10)")
        if dim.suggestion:
            items.append((dim.score, f"[{dim_name.capitalize()}] {dim.suggestion}"))
    
    items.sort(key=lambda x: x[0])  # lowest score first = highest priority
    top_suggestions = [suggestion for _, suggestion in items[:3]]

    scores = [d.score for d in dims.values()]
    overall_score = round(sum(scores) / len(scores), 2) if scores else 1.0
    overall_label = _overall_label(overall_score)
    likelihood    = _approval_likelihood(dims, overall_score)

    review_id = str(uuid.uuid4())

    eval_result = EvaluationResult(
        review_id=review_id,
        tool_name=tool_name,
        tool_category=tool_category,
        overall_score=overall_score,
        overall_label=overall_label,
        approval_likelihood=likelihood,
        retrieval_mode=retrieval_mode,
        relevance=dims["relevance"],
        depth=dims["depth"],
        precision=dims["precision"],
        outcomes=dims["outcomes"],
        coverage=dims["coverage"],
        critical_gaps=critical_gaps,
        top_suggestions=top_suggestions,
        rag_sources=rag_sources,
    )

    # ── Persist to history ────────────────────────────────────────────────────
    outputs_dir = Path(settings.outputs_dir)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    history_entry = HistoryEntry(
        review_id=review_id,
        tool_name=tool_name,
        tool_category=tool_category,
        overall_score=overall_score,
        overall_label=overall_label,
        approval_likelihood=likelihood,
        disposition=Disposition.PENDING,
        evaluated_at=datetime.now(timezone.utc).isoformat(),
    )
    payload = {
        "history": json.loads(history_entry.model_dump_json()),
        "result":  json.loads(eval_result.model_dump_json()),
    }
    (outputs_dir / f"{review_id}.json").write_text(json.dumps(payload, indent=2))

    return EvaluateResponse(status="success", result=eval_result)
