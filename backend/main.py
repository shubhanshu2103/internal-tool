"""
main.py — Review AI Backend

Run with:
  uvicorn main:app --reload --port 8000

API docs auto-generated at:
  http://localhost:8000/docs   (Swagger UI)
  http://localhost:8000/redoc  (ReDoc)
"""

import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.ingest import router as ingest_router
from routes.evaluate import router as evaluate_router
from routes.history import router as history_router
from config import settings


# ── Startup health checks ─────────────────────────────────────────────────────

def _startup_checks():
    """
    Run before accepting traffic. Logs warnings for degraded services,
    raises RuntimeError for anything that would make ALL requests fail.
    """
    errors   = []
    warnings = []

    # 1. Groq API key — without this every evaluation silently 401s
    if not settings.groq_api_key or not settings.groq_api_key.strip():
        errors.append(
            "GROQ_API_KEY is not set in .env. "
            "All LLM evaluations will fail. "
            "Get a free key at console.groq.com."
        )
    else:
        print(f"[startup] ✓ Groq API key present  (model: {settings.groq_model})")

    # 2. Ollama reachable — without this embeddings and ingest fail
    try:
        r = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=4.0)
        if r.status_code != 200:
            warnings.append(
                f"Ollama returned HTTP {r.status_code}. "
                "Embeddings may fail. Restart with: ollama serve"
            )
        else:
            model_names = [m["name"] for m in r.json().get("models", [])]
            # Accept both "nomic-embed-text" and "nomic-embed-text:latest"
            base_names  = [n.split(":")[0] for n in model_names]
            embed_base  = settings.ollama_embed_model.split(":")[0]
            if embed_base not in base_names:
                warnings.append(
                    f"Ollama is running but '{settings.ollama_embed_model}' is not pulled. "
                    f"Run: ollama pull {settings.ollama_embed_model}"
                )
            else:
                print(f"[startup] ✓ Ollama online     (embed model: {settings.ollama_embed_model})")
    except httpx.RequestError as exc:
        warnings.append(
            f"Ollama not reachable at {settings.ollama_base_url} ({exc}). "
            "Start it with: ollama serve   — evaluations will fail until it's up."
        )

    # 3. ChromaDB — test a read so we catch corruption early
    try:
        from retrieval.vector_store import count_chunks
        n = count_chunks()
        print(f"[startup] ✓ ChromaDB online    ({n} chunks in corpus)")
    except Exception as exc:
        warnings.append(f"ChromaDB health check failed: {exc}")

    # 4. Outputs directory writable
    try:
        from pathlib import Path
        out = Path(settings.outputs_dir)
        out.mkdir(parents=True, exist_ok=True)
        test_file = out / ".write_check"
        test_file.write_text("ok")
        test_file.unlink()
        print(f"[startup] ✓ Outputs dir writable ({settings.outputs_dir})")
    except Exception as exc:
        warnings.append(f"Outputs directory not writable: {exc}")

    # ── Print summary ─────────────────────────────────────────────────────────
    for w in warnings:
        print(f"[startup] ⚠  WARNING: {w}")
    for e in errors:
        print(f"[startup] ✗  ERROR:   {e}")

    if errors:
        raise RuntimeError(
            "Critical startup check(s) failed — fix the issues above then restart.\n"
            + "\n".join(errors)
        )

    print("[startup] All checks complete. Server ready.\n")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _startup_checks()
    yield          # server runs here
    # (add shutdown cleanup here if needed)


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Review AI — Quality Evaluator",
    description=(
        "Internal tool for CoreLayer Labs. "
        "Ingests pre-approved reviews as a quality corpus, "
        "then evaluates new draft reviews against that standard."
    ),
    version="0.2.0",
    lifespan=lifespan,
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
app.include_router(history_router)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", tags=["health"])
async def root():
    return {
        "service": "Review AI Backend",
        "version": "0.2.0",
        "status": "running",
        "endpoints": {
            "ingest_file":    "POST /ingest/upload",
            "rebuild_rubric": "POST /ingest/rubric",
            "corpus_status":  "GET  /ingest/status",
            "evaluate_file":  "POST /evaluate/file",
            "evaluate_text":  "POST /evaluate/text",
            "history":        "GET  /history",
            "api_docs":       "GET  /docs",
        },
    }


@app.get("/health", tags=["health"])
async def health():
    """
    Deep health check — reports status of all dependent services.
    Returns 200 even if degraded so load-balancers don't kill the pod,
    but the body shows which services are down.
    """
    status = {"backend": "ok", "groq": "unknown", "ollama": "unknown", "chromadb": "unknown"}

    # Groq key present
    status["groq"] = "ok" if settings.groq_api_key and settings.groq_api_key.strip() else "missing_key"

    # Ollama
    try:
        r = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=3.0)
        status["ollama"] = "ok" if r.status_code == 200 else f"http_{r.status_code}"
    except httpx.RequestError:
        status["ollama"] = "unreachable"

    # ChromaDB
    try:
        from retrieval.vector_store import count_chunks
        status["chromadb"] = f"ok ({count_chunks()} chunks)"
    except Exception as exc:
        status["chromadb"] = f"error: {exc}"

    return status
