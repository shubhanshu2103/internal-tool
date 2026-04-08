"""
routes/ingest.py

POST /ingest/upload   — upload a PDF/DOCX approved review → parse → chunk → embed → store
POST /ingest/rubric   — (re)build the quality rubric from current corpus
GET  /ingest/status   — list what's in the corpus
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from ingestion.parser import parse_file
from ingestion.chunker import chunk_review
from ingestion.embedder import embed_texts
from retrieval.vector_store import upsert_chunks, list_ingested_tools, count_chunks
from evaluation.rubric_builder import build_rubric
from models import IngestResponse, RubricBuildResponse

router = APIRouter(prefix="/ingest", tags=["ingestion"])


@router.post("/upload", response_model=IngestResponse)
async def upload_approved_review(
    file: UploadFile = File(...),
    tool_name: str = Form(...),
    tool_category: str = Form(...),
    review_date: str = Form(...),
):
    """
    Upload a pre-approved review PDF or DOCX.
    Parses → chunks → embeds → stores in vector DB.

    Form fields:
      - file:          the review file
      - tool_name:     e.g. "Lovable"
      - tool_category: e.g. "AI code generation"
      - review_date:   ISO date string e.g. "2025-03-15"
    """
    # Read file bytes
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Parse → markdown
    try:
        markdown = parse_file(file_bytes, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=415, detail=str(e))

    if len(markdown.strip()) < 100:
        raise HTTPException(
            status_code=422,
            detail="Parsed content is too short. Check that the file is readable."
        )

    # Chunk by section
    chunks = chunk_review(markdown)
    if not chunks:
        raise HTTPException(status_code=422, detail="No sections detected in the review.")

    # Embed all chunks in one batch call (cheap)
    embeddings = embed_texts([c.content for c in chunks])

    # Store in Chroma
    stored = upsert_chunks(
        chunks=chunks,
        embeddings=embeddings,
        tool_name=tool_name,
        tool_category=tool_category,
        review_date=review_date,
    )

    return IngestResponse(
        status="success",
        chunks_stored=stored,
        tool_name=tool_name,
        message=f"Stored {stored} section chunks for '{tool_name}'. Run /ingest/rubric to refresh the rubric.",
    )


@router.post("/rubric", response_model=RubricBuildResponse)
async def rebuild_rubric():
    """
    (Re)build the quality rubric from all currently ingested approved reviews.
    Run this after every batch of new uploads.
    Takes ~5–15 seconds. Costs ~$0.003 in API calls.
    """
    try:
        rubric = build_rubric()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return RubricBuildResponse(
        status="success",
        rubric_version=rubric.version,
        message=f"Rubric built from {rubric.generated_from_n_reviews} approved reviews. Saved to disk.",
    )


@router.get("/status")
async def corpus_status():
    """Return current corpus state — what tools are stored and total chunk count."""
    tools = list_ingested_tools()
    return {
        "total_chunks": count_chunks(),
        "total_tools": len(tools),
        "tools": tools,
    }
