from pydantic import BaseModel, Field
from typing import Optional, Literal
from enum import Enum


# ─── Shared enums ────────────────────────────────────────────────────────────

class Label(str, Enum):
    PASS = "PASS"
    NOTE = "NOTE"
    FAIL = "FAIL"


# ─── Ingestion ────────────────────────────────────────────────────────────────

class IngestRequest(BaseModel):
    tool_name: str              # e.g. "Lovable"
    tool_category: str          # e.g. "AI code generation"
    review_date: str            # ISO date string
    aayush_approved: bool = True

class IngestResponse(BaseModel):
    status: str
    chunks_stored: int
    tool_name: str
    message: str


# ─── Rubric ───────────────────────────────────────────────────────────────────

class DimensionRubric(BaseModel):
    what_pass_looks_like: str
    what_note_looks_like: str
    what_fail_looks_like: str
    example_good: Optional[str] = None
    example_bad: Optional[str] = None

class QualityRubric(BaseModel):
    version: str = "2.0-holistic"
    generated_from_n_reviews: int
    relevance: DimensionRubric
    depth: DimensionRubric
    precision: DimensionRubric
    outcomes: DimensionRubric
    coverage: DimensionRubric

class RubricBuildResponse(BaseModel):
    status: str
    rubric_version: str
    message: str


# ─── Evaluation ───────────────────────────────────────────────────────────────

class DimensionScore(BaseModel):
    score: int = Field(..., ge=1, le=10)
    label: Label
    rationale: str
    suggestion: Optional[str] = None     # only present on NOTE or FAIL

class EvaluationResult(BaseModel):
    review_id: str
    tool_name: str
    tool_category: str
    overall_score: float                 # mean across all dimensions
    overall_label: Label
    retrieval_mode: Literal["rag_grounded", "rubric_only"]
    relevance: DimensionScore
    depth: DimensionScore
    precision: DimensionScore
    outcomes: DimensionScore
    coverage: DimensionScore
    critical_gaps: list[str]             # dims that hard-FAIL
    top_suggestions: list[str]           # top 3 actionable items

class EvaluateResponse(BaseModel):
    status: str
    result: EvaluationResult
