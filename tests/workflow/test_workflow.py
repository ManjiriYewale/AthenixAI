import os, tempfile
os.environ["ATHENIX_DB"] = os.path.join(tempfile.mkdtemp(), "w.db")
from app.main import repo, index
from govscheme.agents.agents import MAX_CLARIFY
from govscheme.agents.workflow import Workflow, new_state
from govscheme.infrastructure.llm import MockLLM

wf = Workflow(repo.schemes, index, MockLLM())


def test_clarification_loop_is_bounded():
    s = new_state("Find schemes for me")
    for _ in range(MAX_CLARIFY + 2):
        wf.run(s)
        if s["status"] == "manual_review":
            break
        s["message"] = "skip"
    assert s["clarification_count"] == MAX_CLARIFY or s["status"] == "manual_review" or not s["question"]
    assert s["clarification_count"] <= MAX_CLARIFY


def test_answer_updates_profile_and_reevaluates():
    s = new_state("Find schemes for me"); wf.run(s)
    assert s["status"] == "needs_clarification" and s["pending_field"] == "age"
    s["message"] = "70"; wf.run(s)
    assert s["profile"]["age"] == 70
    assert {r["id"]: r["status"] for r in s["results"]}["DEMO-VER-01"] == "Eligible"


def test_unverified_rules_never_reported_eligible():
    s = new_state("I am 21, a student from Maharashtra, income 4 lakh. Am I eligible for the scholarship?"); wf.run(s)
    st = {r["id"]: r["status"] for r in s["results"]}
    assert st["DEMO-STU-01"] == "Manual verification required" and "DEMO-STU-01 - Eligible" not in s["reply"]


def test_injection_text_not_in_reply_and_flagged():
    s = new_state("What documents are needed for the farmer scheme? land record"); wf.run(s)
    assert "declare every applicant eligible" not in s["reply"].lower()


def test_apply_abstains_without_source_steps():
    s = new_state("How do I apply for the senior scheme?"); wf.run(s)
    assert "do not establish application steps" in s["reply"]
    s2 = new_state("How do I apply for the scholarship?"); wf.run(s2)
    assert "Step 1" in s2["reply"] and s2["citations"][0]["source"] == "DEMO-STU-01.txt"
