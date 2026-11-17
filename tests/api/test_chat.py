import os, tempfile
os.environ["ATHENIX_DB"] = os.path.join(tempfile.mkdtemp(), "c.db")
from fastapi.testclient import TestClient
from app.main import app

c = TestClient(app)


def test_chat_roundtrip_with_clarification():
    r = c.post("/api/v1/chat", json={"message": "Find schemes for me"}).json()
    assert r["status"] == "needs_clarification" and r["question"]["field"] == "age" and r["trace"][0]["agent"] == "Orchestrator"
    r2 = c.post("/api/v1/chat", json={"message": "I am 70", "pending_field": r["pending_field"], "clarification_count": r["clarification_count"]}).json()
    assert r2["profile"]["age"] == 70 and any(s["status"] == "Eligible" for s in r2["schemes"])


def test_workflow_endpoints_and_errors():
    w = c.post("/api/v1/workflows", json={"message": "Find schemes for me"}).json()
    a = c.post(f"/api/v1/workflows/{w['run_id']}/clarifications", json={"answer": "70"}).json()
    assert a["profile"]["age"] == 70 and c.get(f"/api/v1/workflows/{w['run_id']}").status_code == 200
    assert c.get("/api/v1/workflows/nope").status_code == 404
    assert c.post("/api/v1/chat", json={"message": ""}).json()["error"]["code"] == "validation_error"


def test_evidence_search_hides_suspicious():
    r = c.get("/api/v1/evidence/search", params={"q": "ignore previous instructions", "scheme_id": "DEMO-FRM-01"}).json()
    assert all("Ignore all previous" not in e["text"] for e in r["evidence"])
