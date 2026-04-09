# Review AI — Backend

FastAPI backend for Review AI. Handles document ingestion, RAG retrieval, LLM-as-judge evaluation, and evaluation history.

> **Version:** `0.2.0`

---

## Stack

| Layer | Tool | Cost |
|---|---|---|
| API framework | FastAPI + Uvicorn | free |
| PDF parsing | pymupdf4llm | free |
| DOCX parsing | python-docx | free |
| Embeddings | Ollama `nomic-embed-text` (768-dim, local) | free |
| Vector DB | ChromaDB (local persistent) | free |
| LLM judge | Groq API `llama-3.1-8b-instant` | free (500K tokens/day) |
| Settings | pydantic-settings + `.env` | free |

**Total cost: $0**

---

## Project Structure

```
backend/
│
├── main.py                    # FastAPI app entry point, startup health checks
├── config.py                  # Settings loaded from .env via pydantic-settings
├── models.py                  # All Pydantic schemas (request, response, internal)
├── requirements.txt
│
├── ingestion/
│   ├── parser.py              # PDF / DOCX / TXT → normalized markdown
│   ├── chunker.py             # Split by section heading → Chunk objects
│   └── embedder.py            # Ollama nomic-embed-text wrapper (with 503 guard)
│
├── retrieval/
│   └── vector_store.py        # ChromaDB: upsert, query, list, delete
│
├── evaluation/
│   ├── rubric_builder.py      # Builds QualityRubric from corpus via Groq
│   ├── evaluator.py           # JUDGE_SYSTEM prompt + Groq call + score parsing
│   └── orchestrator.py        # Full pipeline: chunk → embed → retrieve → judge → aggregate
│
├── routes/
│   ├── ingest.py              # POST /ingest/upload, POST /ingest/rubric,
│   │                          # GET /ingest/status, DELETE /ingest/{tool_name}
│   ├── evaluate.py            # POST /evaluate/file, POST /evaluate/text
│   └── history.py             # GET /history, PATCH /history/{review_id}
│
└── data/
    ├── chroma_db/             # Auto-created: ChromaDB persists here
    ├── rubric/rubric.json     # Auto-created after POST /ingest/rubric
    └── outputs/               # One JSON per evaluation: {review_id}.json
```

---

## Setup

### 1. Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) installed and running
- Free [Groq API key](https://console.groq.com)

### 2. Install

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Pull the embed model (one-time)

```bash
ollama pull nomic-embed-text
```

### 4. Configure `.env`

```env
GROQ_API_KEY=gsk_...                    # Required — get free at console.groq.com
GROQ_MODEL=llama-3.1-8b-instant         # 500K tokens/day free tier
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBED_MODEL=nomic-embed-text
```

### 5. Run

```bash
uvicorn main:app --reload --port 8000
```

On startup you will see:
```
[startup] ✓ Groq API key present  (model: llama-3.1-8b-instant)
[startup] ✓ Ollama online         (embed model: nomic-embed-text)
[startup] ✓ ChromaDB online       (N chunks in corpus)
[startup] ✓ Outputs dir writable  (./data/outputs)
[startup] All checks complete. Server ready.
```

Missing `GROQ_API_KEY` raises a `RuntimeError` at boot — the server will not start.

---

## API Reference

### Ingestion

```
POST   /ingest/upload           Ingest an approved review (PDF/DOCX/TXT)
POST   /ingest/rubric           Rebuild quality rubric from current corpus
GET    /ingest/status           List all ingested tools with metadata
DELETE /ingest/{tool_name}      Remove a tool's chunks from the corpus
```

### Evaluation

```
POST   /evaluate/file           Evaluate a draft review uploaded as a file
POST   /evaluate/text           Evaluate a draft review passed as raw text
```

### History

```
GET    /history                 List all past evaluations (newest first)
PATCH  /history/{review_id}     Update disposition: APPROVED | DECLINED
```

### Health

```
GET    /health                  Deep check: reports Groq key, Ollama, ChromaDB status
GET    /                        Service info + endpoint map
```

---

## Workflow

```
Step 1: Ingest approved reviews  →  POST /ingest/upload   (repeat per report)
Step 2: Build the rubric         →  POST /ingest/rubric   (run once after uploads)
Step 3: Evaluate a draft         →  POST /evaluate/file
Step 4: Approve or decline       →  PATCH /history/{id}   (or use the dashboard)
```

---

## Evaluation Pipeline

```
orchestrator.run_evaluation(markdown, tool_name, tool_category)
  │
  ├─ load_rubric()                  ← rubric.json or built-in default
  ├─ chunk_review(markdown)         ← section-aware text splitter
  ├─ embed_texts(chunks)            ← Ollama nomic-embed-text (local, free)
  ├─ retrieve_similar_chunks()      ← ChromaDB cosine similarity, top-5
  │
  └─ evaluate_draft(draft, chunks, rubric)
        │
        └─ Groq llama-3.1-8b-instant
             System: JUDGE_SYSTEM (scoring rules, rationale rules)
             User:   draft + reference chunks + rubric
             Output: JSON with 5 dimension scores
```

### Score Structure

Each of the 5 dimensions returns:

```json
{
  "score":      8,            // 1–10 integer
  "label":      "PASS",       // PASS | NOTE | FAIL
  "rationale":  "...",        // 2-3 sentences citing the draft
  "suggestion": null          // null for PASS, non-null for NOTE/FAIL
}
```

### Label / Score Consistency (enforced in code)

| Label | Score range |
|---|---|
| PASS | 8, 9, 10 |
| NOTE | 4, 5, 6, 7 |
| FAIL | 1, 2, 3 |

### Approval Likelihood Formula

```python
label_score = avg(1.0 if PASS, 0.5 if NOTE, 0.0 if FAIL)
score_norm  = (overall_score - 1) / 9        # normalise 1–10 → 0–1
raw         = label_score * 0.65 + score_norm * 0.35
likelihood  = round(10 + raw * 85)           # → 10–95%
```

---

## Reliability Guards

| Guard | File | Prevents |
|---|---|---|
| Score-label consistency clamp | `evaluator.py` | PASS with score 2, FAIL with score 9 |
| Rationale echo guard | `evaluator.py` | LLM echoing "PASS" as rationale text |
| Label-initial mapping | `evaluator.py` | LLM returning "P"/"N"/"F" as score |
| Missing dimension fallback | `evaluator.py` | LLM omitting a dimension key entirely |
| Groq 429 handler | `evaluator.py`, `rubric_builder.py` | Rate limit → human-readable wait message |
| Ollama 503 guard | `embedder.py` | Connection error → clean HTTP 503 |
| Startup assertions | `main.py` | Missing key / Ollama down detected at boot |

---

## Key Design Decisions

**Why holistic scoring (single LLM call)?**
One pass over the full document lets the judge contextualise content regardless of position, avoiding failures caused by strict section-header dependencies.

**Why Groq instead of local Ollama for the judge?**
The system runs on 8 GB RAM. A 70B model requires ~40 GB. Groq's free API tier (`llama-3.1-8b-instant`, 500K tokens/day) offloads inference while keeping cost at $0.

**Why Ollama for embeddings?**
`nomic-embed-text` is a 274 MB model that produces high-quality 768-dim vectors entirely locally. No API key, no cost, no privacy risk for corporate documents.

**Why ChromaDB local instead of Pinecone?**
Zero infra, zero cost, persists to `./data/chroma_db`. To move to production, swap the three ChromaDB calls in `vector_store.py` for Pinecone equivalents.

**What happens with no corpus?**
`retrieval_mode` switches to `rubric_only`. The judge still scores using the built-in default rubric — it just has no peer examples to compare against.
