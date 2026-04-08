"""
evaluation/evaluator.py

The LLM judge. Called once per full review draft.

It:
  1. Assembles context: full draft + retrieved similar approved chunks + holistic rubric
  2. Calls Claude/Ollama with structured JSON output instruction
  3. Parses and validates the holistic score JSON
  4. Returns EvaluationResult (or analogous structured data)
"""

import json
import re
import ollama
from pydantic import BaseModel
from typing import Optional, Literal
from models import (
    DimensionScore, Label, QualityRubric
)
from config import settings

_client = ollama.Client(host=settings.ollama_base_url)


# ── Schema passed to Ollama for constrained decoding ─────────────────────────

class _DimRaw(BaseModel):
    rationale: str
    label: Literal["PASS", "NOTE", "FAIL"]
    score: str
    suggestion: Optional[str] = None

class _DraftScoreRaw(BaseModel):
    retrieval_mode: Literal["rag_grounded", "rubric_only"]
    relevance: _DimRaw
    depth: _DimRaw
    precision: _DimRaw
    outcomes: _DimRaw
    coverage: _DimRaw


JUDGE_SYSTEM = """You are a rigorous quality evaluator for Review AI.
You evaluate AI tool review reports holistically.

You will receive:
  1. A draft review report
  2. A few excerpts from similar pre-approved high-quality reviews (if available, for training reference)
  3. A global quality rubric defining PASS / NOTE / FAIL criteria across 5 dimensions

Score the full draft document on the five dimensions. Return ONLY valid JSON — no prose, no fences.

JSON schema format (You must replace the angle brackets with actual generated text):
{
  "retrieval_mode": "rag_grounded",
  "relevance":  { "rationale": "<insert detailed analysis here>", "label": "PASS", "score": 90, "suggestion": null },
  "depth":      { "rationale": "<insert detailed analysis here>", "label": "NOTE", "score": 60, "suggestion": "<insert action item>" },
  "precision":  { "rationale": "<insert detailed analysis here>", "label": "FAIL", "score": 20, "suggestion": "<insert action item>" },
  "outcomes":   { "rationale": "<insert detailed analysis here>", "label": "PASS", "score": 80, "suggestion": null },
  "coverage":   { "rationale": "<insert detailed analysis here>", "label": "PASS", "score": 100, "suggestion": null }
}

Scoring rules (100 is Perfect, 10 is Terrible):
  - 100 is absolutely perfect, do NOT bias to low numbers.
  - generate the rationale first to think through the output, then the label, then the numerical score.
  - PASS: score 80, 90, or 100. Document meets or exceeds the standard in this dimension.
  - NOTE: score 40, 50, 60, or 70. Document is acceptable but has meaningful gaps.
  - FAIL: score 10, 20, or 30. Document is heavily flawed or missing critical substance.
  - IMPORTANT: You MUST output exact lowercase keys: "relevance", "depth", "precision", "outcomes", "coverage". Do NOT output uppercase keys. Do NOT omit any keys.
  - retrieval_mode: "rag_grounded" if approved examples were provided, "rubric_only" if not.
  - suggestion: required for NOTE and FAIL, null for PASS.
  - Be calibrated — do not inflate scores."""


def _build_judge_prompt(
    draft_content: str,
    retrieved_chunks: list[dict],
    rubric: QualityRubric,
) -> str:
    """Assemble the user message for the judge call."""

    lines = []

    # Draft
    lines.append("### Draft Review Report (to be scored):\n")
    lines.append(draft_content[:15000])  # Cap to prevent blowing context
    lines.append("\n")

    # Retrieved approved examples (if any)
    if retrieved_chunks:
        lines.append("### Reference: excerpts from approved reviews (training context):\n")
        for i, chunk in enumerate(retrieved_chunks, 1):
            tool = chunk["metadata"]["tool_name"]
            lines.append(f"**Example {i} (from Tool: {tool}):**")
            lines.append(chunk["document"][:2000])  # Cap per example
            lines.append("")
    else:
        lines.append("*No similar approved sections found — use rubric-only mode.*\n")

    # Holistic Rubric
    lines.append("### Holistic Quality Rubric:\n")
    for dim_name in ["relevance", "depth", "precision", "outcomes", "coverage"]:
        dim = getattr(rubric, dim_name)
        lines.append(f"**{dim_name.upper()}**:")
        lines.append(f"  PASS → {dim.what_pass_looks_like}")
        lines.append(f"  NOTE → {dim.what_note_looks_like}")
        lines.append(f"  FAIL → {dim.what_fail_looks_like}")
        lines.append("")

    lines.append("\nNow return the JSON score for the entire draft report.")
    return "\n".join(lines)


def _extract_json(raw: str) -> dict:
    """Robust json extraction"""
    text = raw.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fenced:
        try:
            return json.loads(fenced.group(1).strip())
        except json.JSONDecodeError:
            pass
    brace = re.search(r"\{[\s\S]*\}", text)
    if brace:
        try:
            return json.loads(brace.group(0))
        except json.JSONDecodeError:
            pass
    raise ValueError(f"No valid JSON found in model response:\n{raw[:500]}")


def evaluate_draft(
    draft_content: str,
    retrieved_chunks: list[dict],
    rubric: QualityRubric,
) -> dict:
    """
    Score the full draft document holistically.
    Returns the mapped dimension scores as a dict.
    """
    retrieval_mode = "rag_grounded" if retrieved_chunks else "rubric_only"
    prompt = _build_judge_prompt(draft_content, retrieved_chunks, rubric)

    response = _client.chat(
        model=settings.ollama_chat_model,
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        format="json",
    )

    raw = response.message.content
    print(f"\n[DEBUG] Raw LLM Response length: {len(raw)} chars")
    print(f"[DEBUG] LLM Output: {raw}\n")
    data = _extract_json(raw)
    print(f"[DEBUG] Extracted Dict: {data}\n")

    def _find_key(obj, k):
        # Recursively search for a key (case-insensitive)
        if isinstance(obj, dict):
            # check exact first
            if k in obj: return obj[k]
            # check case-insensitive
            for key_str, val in obj.items():
                if str(key_str).lower() == k.lower():
                    return val
            # dig deeper
            for val in obj.values():
                found = _find_key(val, k)
                if found is not None: return found
        return None

    def parse_dim(key: str) -> DimensionScore:
        d = _find_key(data, key)
        
        # If the LLM got lazy and directly assigned the dimension to a label string (e.g. "RELEVANCE": "PASS")
        if isinstance(d, str):
            lbl = d.strip().upper()
            if lbl == "PASS":
                d = {"score": 100, "label": "PASS", "rationale": "The model definitively evaluated this as a PASS, though it omitted the textual rationale."}
            elif lbl == "NOTE":
                d = {"score": 50, "label": "NOTE", "rationale": "The model evaluated this as acceptable but with gaps (NOTE), though it omitted the textual rationale."}
            else:
                d = {"score": 10, "label": "FAIL", "rationale": "The model evaluated this as a FAIL. It omitted the textual rationale."}
                
        if not isinstance(d, dict):
            # Safe fallback if the LLM completely omitted this dimension
            d = {"score": 10, "label": "FAIL", "rationale": f"[Parsing default] LLM omitted {key} entirely."}
            
        raw_score = d.get("score", 10)
        # handle cases where score might be parsed as a string or list
        if isinstance(raw_score, list):
            raw_score = raw_score[0] if raw_score else 1
            
        try:
            clamped_score = max(1, min(100, int(raw_score)))
            if clamped_score > 10:
                clamped_score = clamped_score // 10
        except (ValueError, TypeError):
            clamped_score = 1
            
        label_raw = d.get("label", "FAIL")
        if isinstance(label_raw, list): label_raw = label_raw[0] if label_raw else "FAIL"
        if str(label_raw).upper() not in ["PASS", "NOTE", "FAIL"]:
            label_raw = "FAIL"
            
        # extract rationale string properly if the LLM wrapped it in array
        rationale_raw = d.get("rationale", "No rationale generated.")
        if isinstance(rationale_raw, list):
            rationale_raw = " ".join(str(x) for x in rationale_raw)
            
        return DimensionScore(
            score=clamped_score,
            label=Label(label_raw.upper()),
            rationale=str(rationale_raw),
            suggestion=d.get("suggestion"),
        )

    dims = {k: parse_dim(k) for k in ["relevance", "depth", "precision", "outcomes", "coverage"]}
    
    return {
        "retrieval_mode": data.get("retrieval_mode", retrieval_mode),
        "dimensions": dims
    }
