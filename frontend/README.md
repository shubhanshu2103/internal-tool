# Review AI — Frontend Dashboard

React + Vite glassmorphic dashboard for the Review AI internal tool.

---

## Stack

| Tool | Purpose |
|---|---|
| React 19 + Vite | UI + HMR dev server |
| Axios | HTTP calls to the FastAPI backend |
| Lucide React | Icon library |
| Vanilla CSS | Dark-mode glassmorphism, fully responsive |

---

## Setup

```bash
npm install
npm run dev
```

Dashboard available at: `http://localhost:5173`

The backend must be running at `http://localhost:8000` before using the dashboard.

---

## Responsive Layout

```
> 1100px (wide screen / desktop)
┌──────────────┬─────────────────────┬──────────────┐
│ Evaluate     │   Feedback Panel    │ Ingest       │
│ Draft        │   (Centre)          │ Approved     │
├──────────────┴─────────────────────┴──────────────┤
│                 Training Corpus                    │
├────────────────────────────────────────────────────┤
│                Evaluation History                  │
└────────────────────────────────────────────────────┘

640–1100px (laptop / zoomed in)
┌──────────────┬──────────────┐
│ Evaluate     │ Ingest       │
│ Draft        │ Approved     │
├──────────────┴──────────────┤
│      Feedback Panel         │
├─────────────────────────────┤
│      Training Corpus        │
├─────────────────────────────┤
│     Evaluation History      │
└─────────────────────────────┘

< 640px (mobile)
All panels stacked vertically
```

Each panel grows with its own content — the page scrolls naturally, no inner scroll zones.

---

## Panel Guide

### Left — Evaluate Draft
- Upload a PDF, DOCX, or TXT draft
- Enter tool name and category
- Click **Run RAG Evaluation** → triggers the full pipeline

### Centre — Feedback
Displays after evaluation completes:
- **Overall score** (X.X / 10) with PASS / NOTE / FAIL badge
- **Approval Likelihood** percentage with colour-coded progress bar
- **Critical Gaps** banner (dimensions that FAILed)
- **Per-dimension cards** — score bar, label pill, rationale, action suggestion
- **Reference Sources** — top RAG chunks used from corpus (tool, section, similarity %)
- **Top Recommendations** — highest-priority fixes sorted by score
- **Shareable Summary** — copyable plain-text report for Slack / email
- **Approve & Ingest** / **Decline Review** action buttons

### Right — Ingest Approved Review
- Upload a pre-approved report directly into the training corpus
- Triggers corpus embedding + rubric rebuild automatically

### Training Corpus (bottom)
- Collapsible table: tool name, category, date added
- Hover a row to reveal delete button — removes from corpus on confirm

### Evaluation History (bottom)
- Full log of every evaluation run
- Columns: tool, category, score, likelihood, status, date
- Statuses: `PENDING` / `APPROVED` / `DECLINED`

---

## Key Files

```
src/
├── App.jsx       # All state, event handlers, API calls, JSX layout
└── index.css     # All styles — variables, panels, cards, tables, responsive breakpoints
```

### Constants (`App.jsx`)

```js
DIM_LABELS  // { relevance: 'Relevance', depth: 'Depth', ... }
DIM_DESC    // One-line description shown under each dimension card title
API_BASE    // 'http://localhost:8000'
```

### State

| State | Type | Purpose |
|---|---|---|
| `evalFile` | File | Draft file selected in left panel |
| `feedback` | object | EvaluationResult returned by the backend |
| `centerStatus` | string | `'APPROVED'` or `'DECLINED'` after action |
| `corpus` | object | Corpus status from GET /ingest/status |
| `history` | object | Evaluation history from GET /history |
| `copied` | bool | Clipboard copy feedback (resets after 2.5s) |

### Handlers

| Handler | What it does |
|---|---|
| `handleEvaluate` | POST /evaluate/file → sets `feedback` |
| `handleIngest` | POST /ingest/upload + POST /ingest/rubric |
| `handleApproveFeedback` | Ingest with `force=true` + PATCH history APPROVED |
| `handleDeclineFeedback` | PATCH history DECLINED |
| `handleDeleteTool` | DELETE /ingest/{tool_name} + refresh corpus |
| `handleCopy` | Write `buildShareableText(feedback)` to clipboard |
| `buildShareableText` | Formats full eval result as copyable plain text |

---

## Styling

All styles in `index.css` using CSS custom properties:

```css
--bg-color          /* #0d0f12 — page background */
--bg-color-glass    /* rgba(18, 22, 28, 0.7) — panel glass background */
--glass-border      /* rgba(255, 255, 255, 0.08) — border colour */
--accent-color      /* #3b82f6 — blue accent */
--success           /* #10b981 — green (PASS) */
--note              /* #f59e0b — amber (NOTE) */
--fail              /* #ef4444 — red (FAIL) */
--text-main         /* #f3f4f6 */
--text-muted        /* #9ca3af */
```

Responsive breakpoints:
- `@media (max-width: 1100px)` — 2-column layout
- `@media (max-width: 640px)` — single-column stack
- `@media (max-width: 500px)` — score/likelihood row stacks vertically
