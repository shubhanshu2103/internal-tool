# Review AI — Fullstack Quality Evaluator

Review AI is a full-stack internal tool for **CoreLayer Labs** that evaluates draft AI tool reviews against a corporate corpus of pre-approved reports. It uses a **Retrieval-Augmented Generation (RAG)** pipeline combined with **LLM-as-a-judge** to holistically score drafts, surface specific improvement suggestions, and maintain a living training database of approved reviews.

> **Current version:** `0.3.0`

---

## 🏗️ Repository Structure

```
review-ai/
│
├── backend/                  # FastAPI + ChromaDB + Groq + Jina AI
│   ├── ingestion/            # Document parsing, chunking, embedding
│   ├── evaluation/           # LLM judge, rubric builder, orchestrator
│   ├── retrieval/            # ChromaDB vector store wrapper
│   ├── routes/               # REST API endpoints
│   └── data/                 # Local persistent DBs, rubric, eval outputs
│
└── frontend/                 # React + Vite glassmorphic dashboard
    └── src/
        ├── App.jsx           # Global UI state, Axios API calls
        └── index.css         # Dark-mode glassmorphism + responsive layout
```

---

## ⚡ Tech Stack

### Frontend
| Tool | Purpose |
|---|---|
| React 19 + Vite | UI rendering, HMR dev server |
| Axios | REST calls to the backend |
| Lucide React | Icon set |
| Vanilla CSS (Glassmorphism) | Dark-mode, fully responsive, no CSS framework |

### Backend
| Layer | Tool | Cost |
|---|---|---|
| API framework | FastAPI + Uvicorn | free |
| Document parsing | pymupdf4llm + python-docx | free |
| Embeddings | Jina AI `jina-embeddings-v2-base-en` (768-dim, API) | free (1M tokens) |
| Vector DB | ChromaDB (local persistent) | free |
| LLM Judge | Groq API `llama-3.1-8b-instant` | free (500K TPD) |
| Settings | pydantic-settings + `.env` | free |

**Total running cost: $0** — both Jina and Groq are free-tier API services, no local processes required.

---

## 🚀 Getting Started

You need **two** terminal windows — one for the backend, one for the frontend.

### Prerequisites

- Python 3.11+
- Node 18+
- A free [Groq API key](https://console.groq.com)
- A free [Jina AI API key](https://jina.ai) (sign in with Google, key shown on dashboard)

### 1. Backend

```bash
cd backend

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure secrets
cp .env.example .env
# Edit .env and fill in:
#   GROQ_API_KEY=gsk_...
#   JINA_API_KEY=jina_...
```

Start the server:
```bash
uvicorn main:app --reload --port 8000
```

On startup, the server validates all dependencies and prints:
```
[startup] ✓ Groq API key present  (model: llama-3.1-8b-instant)
[startup] ✓ Jina API key present  (model: jina-embeddings-v2-base-en)
[startup] ✓ ChromaDB online       (N chunks in corpus)
[startup] ✓ Outputs dir writable  (./data/outputs)
[startup] All checks complete. Server ready.
```

> Missing `GROQ_API_KEY` or `JINA_API_KEY` raises a `RuntimeError` at boot — the server will not start.

API reference: `http://localhost:8000/docs`

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Dashboard: `http://localhost:5173`

---

## 🧠 How It Works

```
Draft uploaded
      │
      ▼
[1] Chunk draft into semantic sections
      │
      ▼
[2] Embed chunks via Jina AI → search ChromaDB for similar approved reviews
      │
      ▼
[3] Top-5 similar chunks + full rubric → sent to Groq LLM judge
      │
      ▼
[4] Judge scores 5 dimensions holistically (JSON output)
      │
      ▼
[5] Parse + validate scores → compute overall score & approval likelihood
      │
      ▼
[6] Return structured EvaluationResult → render in dashboard
```

### Evaluation Dimensions

| Dimension | What it measures |
|---|---|
| **Relevance** | Is the review focused on the tool's actual use cases? |
| **Depth** | Are edge cases, limitations, and non-happy paths tested? |
| **Precision** | Are claims evidence-backed with exact inputs/outputs? |
| **Outcomes** | Are pass/fail verdicts clear with business impact? |
| **Coverage** | Does the report cover the full evaluation lifecycle? |

Each dimension is scored **1–10** and labelled **PASS / NOTE / FAIL**.

---

## 🖥️ Dashboard Features

| Panel | What it does |
|---|---|
| **Left — Evaluate Draft** | Upload a PDF/DOCX/TXT draft to run RAG evaluation |
| **Centre — Feedback** | Overall score, approval likelihood %, per-dimension cards with rationale + suggestions, RAG reference sources, top recommendations, copyable shareable summary |
| **Right — Ingest Approved** | Directly add a trusted report to the training corpus |
| **Training Corpus** | Collapsible table of ingested reports — view, refresh, delete |
| **Evaluation History** | Full log of past evaluations with PENDING / APPROVED / DECLINED status |

### Responsive Layout

| Screen width | Layout |
|---|---|
| > 1100px | 3-column (Left \| Centre \| Right) |
| 640–1100px | Left + Right on top row, Centre full-width below |
| < 640px | All panels stacked vertically |

### Approve & Train flow

1. Evaluate a draft → review the feedback
2. Click **Approve & Ingest** → file embedded into ChromaDB, rubric rebuilt
3. The approved report now influences all future evaluations

---

## 🔌 API Reference

### Ingestion

| Method | Route | Description |
|---|---|---|
| `POST` | `/ingest/upload` | Ingest an approved review into the corpus |
| `POST` | `/ingest/rubric` | Rebuild the quality rubric from the current corpus |
| `GET` | `/ingest/status` | List all ingested tools with metadata |
| `DELETE` | `/ingest/{tool_name}` | Remove a tool's chunks from the corpus |

### Evaluation

| Method | Route | Description |
|---|---|---|
| `POST` | `/evaluate/file` | Evaluate a draft uploaded as a file |
| `POST` | `/evaluate/text` | Evaluate a draft passed as raw text |

### History

| Method | Route | Description |
|---|---|---|
| `GET` | `/history` | List all past evaluations (newest first) |
| `PATCH` | `/history/{review_id}` | Update disposition (APPROVED / DECLINED) |

### Health

| Method | Route | Description |
|---|---|---|
| `GET` | `/health` | Deep health check — reports Groq, Jina, ChromaDB status |

---

## ⚙️ Environment Variables

```env
# Required
GROQ_API_KEY=gsk_...           # Get free at console.groq.com
JINA_API_KEY=jina_...          # Get free at jina.ai

# Optional overrides (defaults shown)
GROQ_MODEL=llama-3.1-8b-instant
JINA_EMBED_MODEL=jina-embeddings-v2-base-en
```

---

## 🛡️ Reliability & Hallucination Guards

| Guard | Where | What it prevents |
|---|---|---|
| Score-label consistency | `evaluator.py` | PASS with score 20, FAIL with score 90, etc. |
| Rationale echo guard | `evaluator.py` | LLM echoing "PASS" as the rationale text |
| Label-initial mapping | `evaluator.py` | LLM returning "P"/"N"/"F" as score strings |
| Missing dimension fallback | `evaluator.py` | LLM omitting a whole dimension key |
| Rubric nested JSON unwrap | `rubric_builder.py` | LLM wrapping response in extra keys (recursive search) |
| Groq 429 handler | `evaluator.py`, `rubric_builder.py` | Rate limit → human-readable wait message |
| Jina error guards | `embedder.py` | 401 / 429 / 503 / 504 → clean user-facing errors |
| Startup assertions | `main.py` | Missing API keys or DB corrupt — fail fast at boot |

---

## 🌐 Deployment

The tool is fully deployment-ready — no local processes required:

| Component | Service | Notes |
|---|---|---|
| LLM Judge | Groq API | Already external |
| Embeddings | Jina AI API | Already external (switched from local Ollama) |
| Vector DB | ChromaDB | Attach a persistent disk on your hosting provider |
| History | JSON files in `data/outputs/` | Attach same persistent disk |

Deploy to Railway / Render / Fly.io / any VPS. Set `GROQ_API_KEY` and `JINA_API_KEY` as environment variables and mount a persistent volume at `backend/data/`.

---

## 📁 Data Persistence

```
backend/data/
├── chroma_db/          # ChromaDB vector store (approved review embeddings)
├── rubric/rubric.json  # Last-built quality rubric (auto-regenerated on ingest)
└── outputs/            # One JSON per evaluation: {review_id}.json
```
