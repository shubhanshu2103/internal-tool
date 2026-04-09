# Review AI — Frontend Dashboard

React + Vite glassmorphic dashboard for the Review AI internal tool.

---

## Stack

| Tool | Purpose |
|---|---|
| React 19 + Vite | UI + HMR dev server |
| Axios | HTTP calls to the FastAPI backend |
| Lucide React | Icon library |
| Vanilla CSS | Dark-mode glassmorphism, no CSS framework |

---

## Setup

```bash
npm install
npm run dev
```

Dashboard available at: `http://localhost:5173`

The backend must be running at `http://localhost:8000` before using the dashboard.

---

## Layout

```
┌─────────────────────────────────────────────────────────────┐
│  Evaluate Draft   │      Feedback Panel      │ Ingest Report │
│  (Left Panel)     │      (Centre Panel)      │ (Right Panel) │
├─────────────────────────────────────────────────────────────┤
│                    Training Corpus                           │
├─────────────────────────────────────────────────────────────┤
│                   Evaluation History                         │
└─────────────────────────────────────────────────────────────┘
```

### Left Panel — Evaluate Draft
- Upload a PDF, DOCX, or TXT draft
- Enter tool name and category
- Click **Run RAG Evaluation** → triggers the full pipeline

### Centre Panel — Feedback
Displays after evaluation completes:
- **Overall score** (X.X / 10) with PASS / NOTE / FAIL badge
- **Approval Likelihood** percentage with colour-coded bar
- **Critical Gaps** banner (dimensions that FAILed)
- **Per-dimension cards** — score bar, label pill, rationale, action suggestion
- **Reference Sources** — top RAG chunks used from the corpus (tool name, section, similarity %)
- **Top Recommendations** — highest-priority suggestions sorted by score
- **Shareable Summary** — plain-text copyable report for sharing via Slack / email
- **Approve & Ingest** / **Decline Review** action buttons

### Right Panel — Ingest Approved Review
- Upload a pre-approved report directly into the training corpus
- Triggers corpus embedding + rubric rebuild automatically

### Training Corpus Section
- Collapsible table of all ingested reports (tool name, category, date)
- Hover to reveal a delete button to remove a report from the corpus

### Evaluation History Section
- Full log of past evaluations with score, likelihood, and status
- Statuses: `PENDING` / `APPROVED` / `DECLINED`

---

## Key Files

```
src/
├── App.jsx       # All state, event handlers, API calls, JSX layout
└── index.css     # All styles — variables, panels, cards, tables, animations
```

### Constants in App.jsx

```js
DIM_LABELS  // Human-readable names for the 5 dimensions
DIM_DESC    // One-line description shown on each dimension card
API_BASE    // Backend URL (http://localhost:8000)
```

### Main handlers

| Handler | What it does |
|---|---|
| `handleEvaluate` | POST /evaluate/file with the draft |
| `handleIngest` | POST /ingest/upload + POST /ingest/rubric |
| `handleApproveFeedback` | Ingest with force=true + PATCH history as APPROVED |
| `handleDeclineFeedback` | PATCH history as DECLINED |
| `handleDeleteTool` | DELETE /ingest/{tool_name} + refresh corpus |
| `handleCopy` | Write `buildShareableText(feedback)` to clipboard |
| `buildShareableText` | Formats the full eval result as copyable plain text |

---

## Styling Notes

All styles live in `index.css` using CSS custom properties:

```css
--bg-color          /* #0d0f12 — page background */
--bg-color-glass    /* rgba(18, 22, 28, 0.7) — panel background */
--glass-border      /* rgba(255, 255, 255, 0.08) — border */
--accent-color      /* #3b82f6 — blue accent */
--success           /* #10b981 — green (PASS) */
--note              /* #f59e0b — amber (NOTE) */
--fail              /* #ef4444 — red (FAIL) */
--text-main         /* #f3f4f6 */
--text-muted        /* #9ca3af */
```
