"""
routes/evaluate.py

POST /evaluate/file   — upload draft review as file, get scored
POST /evaluate/text   — paste draft review as plain text, get scored
GET  /evaluate/{review_id} — fetch a previously stored result 
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from ingestion.parser import parse_file, parse_plain_text
from evaluation.orchestrator import run_evaluation
from models import EvaluateResponse

router = APIRouter(prefix="/evaluate", tags=["evaluation"])


class TextEvalRequest(BaseModel):
    text: str
    tool_name: str
    tool_category: str


@router.post("/file", response_model=EvaluateResponse)
async def evaluate_review_file(
    file: UploadFile = File(...),
    tool_name: str = Form(...),
    tool_category: str = Form(...),
):
    """
    Upload a draft review PDF/DOCX and get a full quality score report.

    Returns JSON with:
      - overall_score (1–10)
      - overall_label (PASS / NOTE / FAIL)
      - per-section scores across 5 dimensions
      - critical_gaps list
      - top_suggestions list
    """
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="File is empty.")

    try:
        markdown = parse_file(file_bytes, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=415, detail=str(e))

    if len(markdown.strip()) < 50:
        raise HTTPException(status_code=422, detail="Parsed content too short.")

    return run_evaluation(markdown, tool_name, tool_category)


@router.post("/text", response_model=EvaluateResponse)
async def evaluate_review_text(body: TextEvalRequest):
    """
    Submit a review as plain text (useful for testing from Postman/curl).
    Same response shape as /evaluate/file.
    """
    if len(body.text.strip()) < 50:
        raise HTTPException(status_code=422, detail="Text too short to evaluate.")

    markdown = parse_plain_text(body.text)
    return run_evaluation(markdown, body.tool_name, body.tool_category)
