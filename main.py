"""
main.py — Review AI Backend

Run with:
  uvicorn main:app --reload --port 8000

API docs auto-generated at:
  http://localhost:8000/docs   (Swagger UI)
  http://localhost:8000/redoc  (ReDoc)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.ingest import router as ingest_router
from routes.evaluate import router as evaluate_router

app = FastAPI(
    title="Review AI — Quality Evaluator",
    description=(
        "Internal tool for CoreLayer Labs. "
        "Ingests pre-approved reviews as a quality corpus, "
        "then evaluates new draft reviews against that standard."
    ),
    version="0.1.0",
)

# Allow all origins in development — lock this down in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest_router)
app.include_router(evaluate_router)


@app.get("/", tags=["health"])
async def root():
    return {
        "service": "Review AI Backend",
        "version": "0.1.0",
        "status": "running",
        "endpoints": {
            "ingest_file":   "POST /ingest/upload",
            "rebuild_rubric":"POST /ingest/rubric",
            "corpus_status": "GET  /ingest/status",
            "evaluate_file": "POST /evaluate/file",
            "evaluate_text": "POST /evaluate/text",
            "api_docs":      "GET  /docs",
        },
    }


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}
