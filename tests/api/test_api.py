import os, tempfile
os.environ["ATHENIX_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
from fastapi.testclient import TestClient
from app.main import app

c = TestClient(app)


def test_health_and_seed():
    assert c.get("/health").json()["schemes"] == 4


def test_verified_rule_gives_eligible():
    r = c.post("/api/v1/eligibility/evaluate", json={"profile": {"age": 70, "state": "Maharashtra"}}).json()
    assert {x["id"]: x["status"] for x in r["results"]}["DEMO-VER-01"] == "Eligible"


def test_validation_error_format_and_404():
    assert c.post("/api/v1/eligibility/evaluate", json={"profile": {"age": -1}}).json()["error"]["code"] == "validation_error"
    assert c.get("/api/v1/schemes/nope").status_code == 404
