"""
evaluation/orchestrator.py

Orchestrates a full review evaluation holistically:
  1. Chunk the draft to get embeddings
  2. Retrieve similar approved chunks across the whole document
  3. Call judge with the full report and aggregated context
  4. Aggregate into EvaluationResult
"""

import uuid
from ingestion.chunker import chunk_review
from ingestion.embedder import embed_texts
from retrieval.vector_store import retrieve_similar_chunks
from evaluation.evaluator import evaluate_draft
from evaluation.rubric_builder import load_rubric
from models import (
    EvaluationResult, EvaluateResponse, Label
)


def _overall_label(score: float) -> Label:
    if score >= 7:
        return Label.PASS
    elif score >= 4:
        return Label.NOTE
    return Label.FAIL


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
    # Give the LLM top 10 most relevant contextual bites across the report
    top_context = unique_retrieved[:10]

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

    # 5. Extract critical gaps and top suggestions from dimensions
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

    eval_result = EvaluationResult(
        review_id=str(uuid.uuid4()),
        tool_name=tool_name,
        tool_category=tool_category,
        overall_score=overall_score,
        overall_label=overall_label,
        retrieval_mode=retrieval_mode,
        relevance=dims["relevance"],
        depth=dims["depth"],
        precision=dims["precision"],
        outcomes=dims["outcomes"],
        coverage=dims["coverage"],
        critical_gaps=critical_gaps,
        top_suggestions=top_suggestions,
    )

    return EvaluateResponse(status="success", result=eval_result)
