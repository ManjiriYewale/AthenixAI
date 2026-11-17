# AthenixAI – Government Scheme Discovery (core build)

Deterministic, explainable eligibility. The LLM never decides eligibility. Discovery aid only, not an official certificate.

## Run
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --app-dir apps/api --reload      # open http://127.0.0.1:8000
pytest                                                # 9 tests
python scripts/import_seed.py data/imports/your_reviewed_schemes.json
```

## Status
Built: SQLite schema + validated import, rule engine (5 outcomes, 4 statuses, field mapping), search/evaluate/scheme API,
consistent errors, mock grounded explanation, interactive responsive frontend (light/dark), unit + API tests.
Not yet built: BM25 + document pipeline, five agents + controller, real LLM provider, admin + auth, frontend Node tests,
evaluation metrics, PostgreSQL export. Empty package folders mark where they go.

## Data warning
`data/samples/demo_schemes.json` is SYNTHETIC. Your real 9 schemes / 31 rules / 29 documents were not in the project
document. Export them to the same JSON shape and import. Never bulk-mark rules `verified`.

## Chatbot + agentic RAG (added)
Open the site and click "Ask AthenixAI". Five agents (Orchestrator, Retrieval, Eligibility, Clarification, Guidance) answer
with citations, ask at most 3 clarifying questions, and abstain when no source supports a claim. See `docs/AGENTS.md`.
Endpoints: `POST /api/v1/chat`, `POST /api/v1/workflows`, `GET /api/v1/workflows/{id}`, `POST /api/v1/workflows/{id}/clarifications`,
`GET /api/v1/evidence/search`. Tests: `pytest` (22). Put real guideline files in `documents/` named after the scheme id.
Real LLM: set `LLM_PROVIDER=openai_compat`, `LLM_API_KEY`, `LLM_MODEL` in `.env` (not tested here; mock is the default).
Not built: ChromaDB/embeddings, LangGraph, PostgreSQL, Streamlit (the blueprint's stack; this project keeps your existing HTML/FastAPI/SQLite), admin and login.
