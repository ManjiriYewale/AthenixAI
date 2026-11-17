"""FastAPI app: versioned API under /api/v1 and static frontend hosting."""
import sys
from pathlib import Path
from typing import Literal
from govscheme.infrastructure.vector_store import AthenixVectorStore
from govscheme.application.rag_service import RAGService

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from govscheme.application.service import candidates, evaluate_all
from govscheme.config import settings
from govscheme.infrastructure.db import Repository
from uuid import uuid4
from govscheme.agents import nlu
from govscheme.agents.workflow import Workflow, new_state, to_response
from govscheme.document_processing.ingest import load_documents
from govscheme.infrastructure.bm25 import EvidenceIndex
from govscheme.infrastructure.llm import get_llm

app = FastAPI(title="AthenixAI", version="0.1.0")
repo = Repository(settings.DB_PATH)
if repo.counts()["schemes"] == 0 and settings.SEED_PATH.exists():
    repo.import_file(settings.SEED_PATH)


class Profile(BaseModel):
    """Minimal profile. All fields optional so missing data can be detected and clarified."""
    age: int | None = Field(None, ge=0, le=120)
    state: str | None = Field(None, max_length=60)
    annual_family_income: int | None = Field(None, ge=0, description="INR per year")
    occupation: Literal["Student", "Farmer", "Worker", "Self-employed", "Homemaker", "Unemployed", "Other"] | None = None
    category: Literal["General", "OBC", "SC", "ST", "Other"] | None = None
    gender: Literal["Female", "Male", "Other"] | None = None
    education: str | None = Field(None, max_length=60)


class EvalRequest(BaseModel):
    profile: Profile
    keywords: str = Field("", max_length=100)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"error": {"code": "validation_error", "message": "Invalid profile data.",
                        "details": [e["loc"][-1] for e in exc.errors()]}})


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": "http_error", "message": exc.detail}})


@app.get("/health")
def health() -> dict:
    return {"status": "ok", **repo.counts()}


@app.post("/api/v1/schemes/search")
def search(req: EvalRequest) -> dict:
    found = candidates(repo.schemes(), req.profile.model_dump(exclude_none=True), req.keywords)
    return {"count": len(found), "schemes": [{k: s[k] for k in ("id", "name", "level", "state", "category", "benefit")} for s in found]}


@app.get("/api/v1/schemes/{scheme_id}")
def scheme(scheme_id: str) -> dict:
    for s in repo.schemes():
        if s["id"] == scheme_id:
            return s
    raise HTTPException(404, "Scheme not found.")

@app.get("/api/v1/schemes")
def all_schemes():
    schemes = repo.schemes()

    return {
        "count": len(schemes),
        "schemes": schemes
    }


@app.post("/api/v1/eligibility/evaluate")
def evaluate(req: EvalRequest) -> dict:
    res = evaluate_all(repo.schemes(), req.profile.model_dump(exclude_none=True), req.keywords)
    return {"results": res, "notice": "Discovery aid only. Not an official eligibility certificate; no application is submitted."}


# Load BM25 keyword retrieval
documents = load_documents(settings.DOC_DIRS)

index = EvidenceIndex(documents)

# Initialize existing ChromaDB vector database
vector_store = AthenixVectorStore(
    persist_directory=settings.ROOT / "storage" / "chroma_db"
)

# Connect BM25 + ChromaDB to the five-agent workflow
workflow = Workflow(
    repo.schemes,
    index,
    get_llm(),
    vector_index=vector_store,
)

# Keep the existing standalone RAG service
rag_service = RAGService(vector_store)

RUNS: dict[str, dict] = {}  # in-memory only: private data is not persisted


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    profile: Profile = Profile()
    pending_field: str | None = Field(None, max_length=40)
    clarification_count: int = Field(0, ge=0, le=10)
    skipped_fields: list[str] = Field(default_factory=list, max_length=10)


class AnswerRequest(BaseModel):
    answer: str = Field(..., min_length=1, max_length=200)


def _state(req: ChatRequest) -> dict:
    return new_state(req.message, req.profile.model_dump(exclude_none=True), req.pending_field, req.clarification_count, req.skipped_fields)


@app.post("/api/v1/chat")
def chat(req: ChatRequest) -> dict:
    """Stateless chatbot turn: the client sends its profile and pending question; nothing is stored server-side."""
    return to_response(workflow.run(_state(req)))


@app.post("/api/v1/workflows", status_code=201)
def start_workflow(req: ChatRequest) -> dict:
    s = workflow.run(_state(req))
    rid = uuid4().hex
    RUNS[rid] = s
    while len(RUNS) > 200:
        RUNS.pop(next(iter(RUNS)))
    return {"run_id": rid, **to_response(s)}


@app.get("/api/v1/workflows/{run_id}")
def get_workflow(run_id: str) -> dict:
    if run_id not in RUNS:
        raise HTTPException(404, "Workflow run not found.")
    return {"run_id": run_id, **to_response(RUNS[run_id])}


@app.post("/api/v1/workflows/{run_id}/clarifications")
def answer_clarification(run_id: str, req: AnswerRequest) -> dict:
    s = RUNS.get(run_id)
    if s is None:
        raise HTTPException(404, "Workflow run not found.")
    if not s.get("pending_field"):
        raise HTTPException(409, "No clarification is pending for this run.")
    s["message"] = req.answer
    return {"run_id": run_id, **to_response(workflow.run(s))}


@app.get("/api/v1/evidence/search")
def evidence_search(q: str = Query(..., max_length=200), scheme_id: str | None = None, k: int = 3) -> dict:
    hits = [h for h in index.search(q, scheme_id, max(1, min(k, 10))) if not h["suspicious"]]
    return {"count": len(hits), "evidence": [{k2: h[k2] for k2 in ("scheme_id", "source", "page", "text", "score")} for h in hits]}

@app.get("/api/v1/rag/search")
def rag_search(
    q: str = Query(..., min_length=2, max_length=500),
    k: int = Query(5, ge=1, le=10)
):
    """Retrieve relevant government scheme passages using ChromaDB."""

    try:
        result = rag_service.retrieve(q, k)

        return {
            "status": "success",
            "question": result["question"],
            "total_results": result["total_results"],
            "evidence": result["context"]
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"RAG retrieval failed: {type(exc).__name__}"
        )

app.mount("/", StaticFiles(directory=Path(__file__).resolve().parents[2] / "frontend", html=True), name="web")
