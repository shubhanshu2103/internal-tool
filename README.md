# Review AI — Quality Evaluator Backend

Internal tool for CoreLayer Labs. Evaluates draft AI tool reviews against a
corpus of pre-approved reviews using RAG + LLM-as-judge.

---

## Stack

| Layer | Tool | Cost |
|---|---|---|
| API framework | FastAPI + Uvicorn | free |
| PDF parsing | pymupdf4llm | free |
| DOCX parsing | python-docx | free |
| Embeddings | OpenAI text-embedding-3-small | ~$0.002 for full corpus |
| Vector DB | ChromaDB (local persistent) | free |
| LLM judge | Anthropic claude-haiku-4-5 | ~$0.006 per review |
| Settings | pydantic-settings + .env | free |

**Total running cost at 100 reviews/month: < $1**

---

## Project structure

```
review_ai_backend/
│
├── main.py                        # FastAPI app, routes registered here
├── config.py                      # Settings from .env
├── models.py                      # All Pydantic request/response schemas
├── requirements.txt
├── test_local.py                  # Smoke test — no API keys needed
│
├── ingestion/
│   ├── parser.py                  # PDF / DOCX / text → normalized markdown
│   ├── chunker.py                 # Split by section heading → Chunk objects
│   └── embedder.py                # text-embedding-3-small wrapper
│
├── retrieval/
│   └── vector_store.py            # ChromaDB: upsert, query, list
│
├── evaluation/
│   ├── rubric_builder.py          # One-time: extract quality rubric from corpus
│   ├── evaluator.py               # Per-section LLM judge call
│   └── orchestrator.py            # Ties the full pipeline together
│
├── routes/
│   ├── ingest.py                  # POST /ingest/upload, POST /ingest/rubric, GET /ingest/status
│   └── evaluate.py                # POST /evaluate/file, POST /evaluate/text
│
└── data/
    ├── chroma_db/                 # Auto-created: vector store persists here
    ├── rubric/rubric.json         # Auto-created after /ingest/rubric
    └── outputs/                   # Future: store evaluation result JSONs
```

---

## Setup

### 1. Clone and install

```bash
cd review_ai_backend
pip install -r requirements.txt
```

### 2. Create .env

```bash
cp .env.example .env
# Then fill in your keys:
```

```env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

Everything else has sensible defaults.

### 3. Smoke test (no API keys needed)

```bash
python test_local.py
```

Expected output: all 4 tests pass, including section detection.

### 4. Run the server

```bash
uvicorn main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

---

## Workflow — step by step

```
Step 1: Ingest approved reviews  →  POST /ingest/upload  (repeat for each)
Step 2: Build the rubric         →  POST /ingest/rubric  (run once after uploads)
Step 3: Check corpus             →  GET  /ingest/status
Step 4: Evaluate a new draft     →  POST /evaluate/text  or  /evaluate/file
```

---

## Curl test commands

### Health check

```bash
curl http://localhost:8000/
```

---

### Step 1 — Ingest an approved review (plain text for testing)

Save a sample review to a file first:

```bash
cat > /tmp/sample_approved.txt << 'EOF'
## Pre-Test Research
Lovable is an AI-powered no-code app builder targeting non-technical founders.
It generates full-stack React + Supabase applications from natural language prompts.
Key differentiator: one-click deployment with built-in hosting.

## Test Design
Test cases:
TC-01: Generate a simple todo app from a single prompt
TC-02: Add authentication to an existing project
TC-03: Handle ambiguous/incomplete prompt
TC-04: Generate with database relationships
TC-05: Export code and run locally

## Hands-On Testing
TC-01 | Input: "build a todo app" | Expected: functional app | Actual: clean React app with CRUD → PASS
TC-02 | Input: "add login" | Expected: auth flow | Actual: Supabase auth added in 2 prompts → PASS
TC-03 | Input: "make it better" | Expected: clarification | Actual: made random UI changes → FAIL
TC-04 | Input: "add comments linked to todos" | Expected: relational schema | Actual: correct FK setup → PASS
TC-05 | Export: code downloaded | Local run: missing env vars not documented → NOTE

## Gap Analysis
- No offline mode tested (not applicable — cloud only)
- Team collaboration features not tested
- Prompt history / undo not evaluated

## Polished Report
Lovable performs strongly on core app generation with reliable Supabase integration.
Critical gap: ambiguous prompt handling degrades gracefully but unpredictably.
Recommended for: MVPs, internal tools, prototype demos.
Overall: PASS with one FAIL on edge case prompt handling.
EOF
```

Then ingest it:

```bash
curl -X POST http://localhost:8000/ingest/upload \
  -F "file=@/tmp/sample_approved.txt" \
  -F "tool_name=Lovable" \
  -F "tool_category=AI app builder" \
  -F "review_date=2025-03-15"
```

Expected response:
```json
{
  "status": "success",
  "chunks_stored": 5,
  "tool_name": "Lovable",
  "message": "Stored 5 section chunks for 'Lovable'. Run /ingest/rubric to refresh the rubric."
}
```

---

### Step 2 — Build the rubric

```bash
curl -X POST http://localhost:8000/ingest/rubric
```

Expected response:
```json
{
  "status": "success",
  "rubric_version": "1.0",
  "sections_covered": 5,
  "message": "Rubric built from 1 approved reviews. Saved to disk."
}
```

---

### Step 3 — Check corpus status

```bash
curl http://localhost:8000/ingest/status
```

Expected:
```json
{
  "total_chunks": 5,
  "total_tools": 1,
  "tools": [
    { "tool_name": "Lovable", "tool_category": "AI app builder", "review_date": "2025-03-15" }
  ]
}
```

---

### Step 4 — Evaluate a new draft review (text mode — easiest for testing)

```bash
curl -X POST http://localhost:8000/evaluate/text \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "Bolt.new",
    "tool_category": "AI app builder",
    "text": "## Pre-Test Research\nBolt.new is a browser-based AI coding tool by StackBlitz.\n\n## Test Design\nTC-01: Generate landing page\nTC-02: Add a form\n\n## Hands-On Testing\nTC-01: Generated cleanly. PASS.\nTC-02: Form added but no validation. NOTE.\n\n## Gap Analysis\nMobile responsiveness not tested.\n\n## Polished Report\nBolt.new is fast but shallow on form handling. Recommended for quick prototypes."
  }'
```

Expected response shape:
```json
{
  "status": "success",
  "result": {
    "review_id": "...",
    "tool_name": "Bolt.new",
    "tool_category": "AI app builder",
    "overall_score": 6.4,
    "overall_label": "NOTE",
    "sections": [
      {
        "section": "test_design",
        "present_in_draft": true,
        "retrieval_mode": "rag_grounded",
        "relevance": { "score": 7, "label": "PASS", "rationale": "...", "suggestion": null },
        "depth":     { "score": 4, "label": "NOTE", "rationale": "...", "suggestion": "Add edge cases..." },
        ...
        "overall_section_score": 5.6
      },
      ...
    ],
    "critical_gaps": ["hands_on_testing → depth FAIL (score 3/10)"],
    "top_suggestions": [
      "[test_design/depth] Add edge case test cases for empty inputs and error states.",
      "..."
    ]
  }
}
```

---

### Evaluate via file upload

```bash
curl -X POST http://localhost:8000/evaluate/file \
  -F "file=@/tmp/your_draft_review.pdf" \
  -F "tool_name=SomeNewTool" \
  -F "tool_category=AI writing assistant"
```

---

## Key design decisions

**Why section-level scoring (5 calls) instead of one big call?**
Smaller context per call = more precise scoring. Each section is independently
auditable. One bad section doesn't corrupt the whole review score.

**What happens if there's no similar tool in the corpus?**
`retrieval_mode` switches to `"rubric_only"`. The judge still scores against the
quality rubric extracted from all approved reviews — just without concrete examples
to compare against. Quality rubric is tool-agnostic by design.

**Why claude-haiku for judging?**
It's a structured scoring task with a well-defined rubric and JSON output format.
Haiku handles this cleanly at ~10x lower cost than Sonnet. If scores seem
uncalibrated after testing, swap `judge_model` in config.py to `claude-sonnet-4-5`.

**Why Chroma (local) instead of Pinecone?**
Zero cost, zero infra, runs on your laptop. Chroma persists to disk at
`./data/chroma_db`. When you move to production/server, swap to Pinecone
free tier by changing one function in `retrieval/vector_store.py`.
