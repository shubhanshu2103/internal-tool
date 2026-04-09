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
from groq import Groq
from groq import RateLimitError as GroqRateLimitError
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Optional, Literal
from models import (
    DimensionScore, Label, QualityRubric
)
from config import settings

_client = Groq(api_key=settings.groq_api_key)


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

JSON schema format:
{
  "retrieval_mode": "rag_grounded",
  "relevance":  { "rationale": "<2-3 sentences citing specific content from the draft>", "label": "PASS", "score": "90", "suggestion": null },
  "depth":      { "rationale": "<2-3 sentences citing specific content from the draft>", "label": "NOTE", "score": "60", "suggestion": "<concrete, actionable instruction referencing the draft>" },
  "precision":  { "rationale": "<2-3 sentences citing specific content from the draft>", "label": "FAIL", "score": "20", "suggestion": "<concrete, actionable instruction referencing the draft>" },
  "outcomes":   { "rationale": "<2-3 sentences citing specific content from the draft>", "label": "PASS", "score": "80", "suggestion": null },
  "coverage":   { "rationale": "<2-3 sentences citing specific content from the draft>", "label": "PASS", "score": "100", "suggestion": null }
}

Scoring rules (score range: 10–100):
  - Think through your rationale first, then decide the label, then pick the score.
  - PASS: score must be 80, 90, or 100. The document meets or exceeds the standard for this dimension.
  - NOTE: score must be 40, 50, 60, or 70. The document is acceptable but has meaningful gaps.
  - FAIL: score must be 10, 20, or 30. The document is heavily flawed or missing critical substance.
  - CRITICAL: score and label MUST be consistent. PASS → score 80/90/100. NOTE → score 40/50/60/70. FAIL → score 10/20/30. Never mix them.
  - The 'score' field must be a STRING containing exactly one of: "10","20","30","40","50","60","70","80","90","100".
  - retrieval_mode: "rag_grounded" if approved examples were provided, "rubric_only" if not.
  - suggestion: REQUIRED (non-null) for NOTE and FAIL. Must be null for PASS.

Rationale rules — STRICTLY ENFORCED:
  - The rationale MUST reference specific content, sections, claims, or evidence actually present in the draft.
  - NEVER write a URL alone as the rationale. NEVER write a generic statement that could apply to any document.
  - Minimum 2 full sentences. Be concrete: quote or paraphrase what the draft says (or fails to say).
  - Example of BAD rationale: "The review lacks detail." — too vague.
  - Example of GOOD rationale: "The draft identifies the tool's core use case as code generation but provides no benchmarks or comparative data against alternatives. The outcomes section states results were 'good' without quantifying time saved or error reduction."

Suggestion rules:
  - Suggestions must be specific and actionable, referencing what is missing or wrong in THIS draft.
  - NEVER write a generic suggestion. Reference the actual gap found in the rationale."""


def _build_judge_prompt(
    draft_content: str,
    retrieved_chunks: list[dict],
    rubric: QualityRubric,
) -> str:
    """Assemble the user message for the judge call."""

    lines = []

    # Draft
    lines.append("### Draft Review Report (to be scored):\n")
    lines.append(draft_content[:8000])   # Cap to reduce token usage
    lines.append("\n")

    # Retrieved approved examples (if any)
    if retrieved_chunks:
        lines.append("### Reference: excerpts from approved reviews (training context):\n")
        for i, chunk in enumerate(retrieved_chunks, 1):
            tool = chunk["metadata"]["tool_name"]
            lines.append(f"**Example {i} (from Tool: {tool}):**")
            lines.append(chunk["document"][:1000])  # Cap per example
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

    try:
        response = _client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.4,
        )
    except GroqRateLimitError as e:
        msg = str(e)
        wait = "a few minutes"
        if "Please try again in" in msg:
            wait = msg.split("Please try again in")[1].split(".")[0].strip()
        raise HTTPException(
            status_code=429,
            detail=f"Daily evaluation limit reached. Please try again in {wait}. Upgrade your Groq plan at console.groq.com for more quota."
        )

    raw = response.choices[0].message.content
    print(f"\n[DEBUG] Raw LLM Response length: {len(raw)} chars")
    data = _extract_json(raw)
    print(f"[DEBUG] Extracted Dict: {data}\n")

    def _find_key(obj, k):
        # LLM hallucination: returning a completely flat object without top-level dimension keys
        if isinstance(obj, dict) and 'rationale' in [str(key).lower() for key in obj.keys()] and k.lower() in ["relevance", "depth", "precision", "outcomes", "coverage"]:
            return obj
            
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
        elif isinstance(obj, list):
            for item in obj:
                found = _find_key(item, k)
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
                
        # If the LLM outputted a pure number (e.g. "RELEVANCE": 0.8)
        elif isinstance(d, (int, float)):
            num = float(d)
            if num <= 1.0:
                calc_score = int(num * 100)
            elif num <= 10.0:
                calc_score = int(num * 10)
            else:
                calc_score = int(num)
                
            if calc_score >= 80:
                calc_label = "PASS"
            elif calc_score >= 40:
                calc_label = "NOTE"
            else:
                calc_label = "FAIL"
                
            d = {"score": calc_score, "label": calc_label, "rationale": f"The model assigned a raw numerical score of {num} but omitted the textual rationale."}
                
        if not isinstance(d, dict):
            # Safe fallback if the LLM completely omitted this dimension
            d = {"score": 10, "label": "FAIL", "rationale": f"[Parsing default] LLM omitted {key} entirely."}
            
        raw_score = d.get("score", 10)
        # handle cases where score might be parsed as a string or list
        if isinstance(raw_score, list):
            raw_score = raw_score[0] if raw_score else 1

        # LLM sometimes returns the label initial instead of a number (e.g. "N", "F", "P")
        if isinstance(raw_score, str):
            _s = raw_score.strip().upper()
            if _s in ("P", "PASS"):
                raw_score = 90
            elif _s in ("N", "NOTE"):
                raw_score = 50
            elif _s in ("F", "FAIL"):
                raw_score = 20

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

        # Enforce score-label consistency — LLM sometimes mismatches them
        _lbl = str(label_raw).upper()
        if _lbl == "PASS" and clamped_score < 8:
            clamped_score = 8
        elif _lbl == "NOTE" and clamped_score < 4:
            clamped_score = 4
        elif _lbl == "NOTE" and clamped_score > 7:
            clamped_score = 7
        elif _lbl == "FAIL" and clamped_score > 3:
            clamped_score = 3
            
        # extract rationale string properly if the LLM wrapped it in array
        rationale_raw = d.get("rationale", "No rationale generated.")
        if isinstance(rationale_raw, list):
            rationale_raw = " ".join(str(x) for x in rationale_raw)
        # Guard: LLM sometimes echoes the label word as the rationale
        if not rationale_raw or str(rationale_raw).strip().upper() in ("PASS", "NOTE", "FAIL", "[]", "N/A", ""):
            rationale_raw = "No detailed rationale was provided by the model for this dimension."
            
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
