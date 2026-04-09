"""
evaluation/rubric_builder.py

Manages the global holistic quality rubric used for evaluating AI tool reviews.

Two rubric sources (in priority order):
  1. data/rubric/rubric.json — LLM-built from corpus via POST /ingest/rubric
  2. DEFAULT_RUBRIC          — hardcoded baseline, always valid, used as fallback
"""

import json
import re
from groq import Groq
from groq import RateLimitError as GroqRateLimitError
from fastapi import HTTPException
from pathlib import Path
from retrieval.vector_store import _get_collection
from models import QualityRubric, DimensionRubric
from config import settings

_client = Groq(api_key=settings.groq_api_key)


# ─── Hardcoded default rubric ─────────────────────────────────────────────────

def _dim(p: str, n: str, f: str) -> DimensionRubric:
    return DimensionRubric(
        what_pass_looks_like=p,
        what_note_looks_like=n,
        what_fail_looks_like=f,
    )

DEFAULT_RUBRIC = QualityRubric(
    version="2.0-holistic-default",
    generated_from_n_reviews=0,
    relevance=_dim(
        "Directly evaluates the tool's core advertised capabilities with specific, real-world relevant use-cases.",
        "Mostly relevant but includes some generic evaluations that could apply to any tool.",
        "Evaluations are trivial or entirely disconnected from the tool's actual stated purpose.",
    ),
    depth=_dim(
        "Deeply investigates limitations, edge cases, pricing blocks, and bugs, distinguishing between them.",
        "Covers happy-path well but misses some edge cases or competitive context.",
        "Only scratches the surface; no limitations investigated, very shallow testing.",
    ),
    precision=_dim(
        "Includes exact inputs, exact outputs, version numbers, and concrete environments.",
        "Includes some specifics, but frequently relies on paraphrasing or vague impact claims.",
        "No structured evidence; claims are made with no data to back them up.",
    ),
    outcomes=_dim(
        "Every claim and test has an explicit pass/fail/note verdict tied to a business impact.",
        "Verdicts are present but some are subjective or lacking clear business impact.",
        "No clear outcomes; reader cannot tell if the tool is actually recommended.",
    ),
    coverage=_dim(
        "Comprehensive report covering background research, strict test design, execution evidence, gaps, and final recommendation.",
        "Covers most bases, but might be light on early research or final recommendation.",
        "Crucial phases of evaluation are missing entirely.",
    ),
)


# ─── JSON extraction helper ───────────────────────────────────────────────────

def _extract_json(raw: str) -> dict:
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


# ─── Corpus-based rubric builder ─────────────

RUBRIC_BUILD_SYSTEM = """You are a review quality expert for Review AI (CoreLayer Labs).
You will be given a set of pre-approved high-quality AI tool review excerpts.
Your job is to extract a globally applicable, holistic quality rubric that describes what PASS, NOTE, and FAIL
look like for an AI tool review report across five key dimensions.

The five dimensions are:
  - relevance: is the testing specific to the tool's actual use cases?
  - depth: are edge cases, advanced flows, limitations, and non-happy-paths explored?
  - precision: are steps reproducible? are exact inputs and outputs documented?
  - outcomes: are results clearly evaluated (e.g. PASS/FAIL) with solid evidence and business impact?
  - coverage: does the report comprehensively address the entire evaluation lifecycle?

Write general quality criteria — do NOT copy content from the sample reviews.
Each what_pass_looks_like / what_note_looks_like / what_fail_looks_like must describe
the QUALITY STANDARD universally applicable to any good report."""


def _gather_corpus_text() -> tuple[str, int]:
    collection = _get_collection()
    all_data = collection.get(include=["documents", "metadatas"])

    docs = all_data["documents"]
    metas = all_data["metadatas"]

    if not docs:
        raise ValueError("No approved reviews in vector store. Ingest some first.")

    tool_names = set()
    chunks = []

    for doc, meta in zip(docs, metas):
        tool_names.add(meta["tool_name"])
        chunks.append(f"[{meta['tool_name']} — {meta['heading']}]\n{doc}")

    # Use first 15 chunks to avoid blowing up context window
    combined = "\n\n---\n\n".join(chunks[:15])

    return combined, len(tool_names)


def build_rubric() -> QualityRubric:
    corpus_text, n_reviews = _gather_corpus_text()

    user_message = (
        f"Here are {n_reviews} approved review excerpts.\n\n"
        f"{corpus_text}\n\n"
        "Now write the holistic quality rubric JSON. Remember: describe quality criteria in general terms, "
        "do NOT copy specific content or tool names from the reviews above."
    )

    try:
        response = _client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": RUBRIC_BUILD_SYSTEM},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
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

    rubric_dict = _extract_json(response.choices[0].message.content)
    rubric_dict["generated_from_n_reviews"] = n_reviews
    rubric_dict["version"] = "2.0-holistic"
    rubric = QualityRubric(**rubric_dict)

    rubric_path = Path(settings.rubric_path)
    rubric_path.parent.mkdir(parents=True, exist_ok=True)
    rubric_path.write_text(rubric.model_dump_json(indent=2))

    return rubric


def load_rubric() -> QualityRubric:
    rubric_path = Path(settings.rubric_path)
    if rubric_path.exists():
        try:
            return QualityRubric.model_validate_json(rubric_path.read_text())
        except Exception:
            print("[rubric] Saved rubric is corrupt — falling back to default.")
    print("[rubric] No saved rubric found — using built-in default rubric.")
    return DEFAULT_RUBRIC
