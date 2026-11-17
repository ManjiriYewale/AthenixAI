from govscheme.agents.nlu import classify, extract_facts, parse_answer
from govscheme.config import settings
from govscheme.document_processing.ingest import load_documents
from govscheme.infrastructure.bm25 import EvidenceIndex

IDX = EvidenceIndex(load_documents(settings.DOC_DIRS))
LABELLED = [("income certificate bonafide documents", "DEMO-STU-01"), ("land record bank passbook", "DEMO-FRM-01"),
            ("business plan women grant interview", "DEMO-WOM-01"), ("age proof senior support", "DEMO-VER-01")]


def test_extract_facts():
    f = extract_facts("I am 21, I'm a student from Pune, family income 4.5 lakh")
    assert f == {"age": 21, "annual_family_income": 450000, "occupation": "Student", "state": "Maharashtra"}


def test_no_gender_guess_from_topic_words():
    assert "gender" not in extract_facts("any schemes for women?")


def test_parse_answer_and_intent():
    assert parse_answer("age", "about 34") == 34 and parse_answer("occupation", "farmer") == "Farmer"
    assert classify("what documents do I need") == "documents" and classify("hi") == "greeting"


def test_retrieval_precision_at_1_labelled_set():
    hits = sum(IDX.search(q, k=1)[0]["scheme_id"] == sid for q, sid in LABELLED)
    assert hits / len(LABELLED) == 1.0


def test_injection_chunk_flagged_and_citation_has_page():
    assert any(c["suspicious"] for c in IDX.chunks if c["scheme_id"] == "DEMO-FRM-01")
    assert IDX.search("land record", "DEMO-FRM-01")[0]["page"] == 1
