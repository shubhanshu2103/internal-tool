# Review AI — Fullstack Quality Evaluator

Review AI is a robust, full-stack internal tool for evaluating draft AI tool reviews against a corporate database of pre-approved reviews. It leverages a **Retrieval-Augmented Generation (RAG)** pipeline combined with local **LLM-as-a-judge** architecture to holistically score and provide exact textual suggestions to standardize company reports.

---

## 🏗️ Repository Structure

This is a monorepo containing both the Python AI Backend and the React UI Dashboard.

```
review-ai/
│
├── backend/            # FastAPI, ChromaDB, and Ollama/LLaMA logic
│   ├── ingestion/      # Semantic chunking and vector storage
│   ├── evaluation/     # Heavily engineered LLM Judge pipelines
│   ├── routes/         # REST API endpoints
│   └── data/           # Local persistent databases and generated rubrics
│
└── frontend/           # Premium Glassmorphic React + Vite Dashboard
    └── src/            
        ├── App.jsx     # Global UI state and Axios API coordination
        └── index.css   # Dark-mode component styling
```

---

## ⚡ Tech Stack

### Frontend
- **React + Vite**: Lightning-fast compilation and interactive UI rendering.
- **Axios**: Smooth asynchronous REST logic linking to the local python server.
- **Vanilla CSS (Glassmorphism)**: Tailored, high-fidelity aesthetic without heavy frameworks.

### Backend
- **FastAPI / Uvicorn**: Ultra-fast async API framework handling data parsing (via Pydantic).
- **ChromaDB**: Native local vector-database for storing approved company reviews.
- **pymupdf4llm**: Specialized heuristic Optical Layout extractor for turning PDFs into clean markdown.
- **Ollama**: Local containerized inference for running LLaMA models entirely privately.
- **OpenAI Embeddings**: Lightweight semantic embedding (`text-embedding-3-small`) to rapidly search ChromaDB.

---

## 🚀 Getting Started

You will need **TWO** terminal windows to run this application locally.

### 1. Start the Backend Server
*Make sure Ollama is installed and running on your local machine.*

```bash
cd backend

# Create and activate your virtual environment
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Run the API
uvicorn main:app --reload --port 8000
```
*API reference will be available at `http://localhost:8000/docs`*

### 2. Start the Frontend Dashboard
Open a second terminal window:

```bash
cd frontend

# Install UI dependencies
npm install

# Start the dev server
npm run dev
```
*The dashboard will be available at `http://localhost:5173`*

---

## 🧠 System Architecture & Workflows

Instead of strict keyword matching, the tool evaluates documents **Holistically**. 

1. **Evaluate Drafts (Left Panel)**: Upload unapproved PDF/DOCX reviews. The backend Semantically Searches the vector database for similar past reports, generates a dynamic rubric, and passes the entire context to the local LLM.
2. **Dynamic Feedback (Center Panel)**: The UI renders the AI's grading (out of 10) across 5 core dimensions: `Relevance`, `Depth`, `Precision`, `Outcomes`, and `Coverage`. 
3. **Approve & Train (One-Click)**: Once an unapproved review is heavily scrutinized and modified, clicking "Approve" instantly pipes the active file directly to the `/ingest` routes, physically embedding it entirely into the RAG database to act as training weight for all future evaluations!
4. **Manual Ingest (Right Panel)**: Immediately upload highly trusted corporate documents directly to the database without generating feedback.
