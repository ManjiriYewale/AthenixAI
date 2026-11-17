"""Deterministic language helpers: intent, fact extraction, answer parsing. No LLM, no invention."""
from __future__ import annotations
import re

ORDER = ["age", "annual_family_income", "occupation", "gender", "category", "state"]
QUESTIONS = {"age": "What is your age?", "annual_family_income": "What is your annual family income in rupees? (e.g. 4.5 lakh)",
             "occupation": "What is your occupation?", "gender": "What is your gender?",
             "category": "Which social category do you belong to?", "state": "Which state do you live in?"}
CHOICES = {"occupation": ["Student", "Farmer", "Worker", "Self-employed", "Homemaker", "Unemployed", "Other"],
           "gender": ["Female", "Male", "Other"], "category": ["General", "OBC", "SC", "ST", "Other"], "state": ["Maharashtra", "Other state"]}
TOPICS = {"scholarship": "scholarship", "education": "education", "agriculture": "agriculture", "entrepreneur": "entrepreneur",
          "business": "entrepreneur", "senior": "senior", "pension": "senior", "elderly": "senior"}
OCC = {"student": "Student", "farmer": "Farmer", "worker": "Worker", "labourer": "Worker", "homemaker": "Homemaker",
       "unemployed": "Unemployed", "entrepreneur": "Self-employed", "self-employed": "Self-employed", "self employed": "Self-employed"}
ME = r"(?:i am|i'm|im|i work as|my occupation is)\s+(?:an?\s+)?"
SKIP = re.compile(r"\b(skip|don'?t know|do not know|not sure|prefer not|no idea)\b", re.I)


def classify(text: str) -> str:
    t = text.lower()
    if len(t) < 25 and re.match(r"\s*(hi|hello|hey|namaste)\b", t):
        return "greeting"
    if re.search(r"document|papers|certificate|proof", t): return "documents"
    if re.search(r"\bapply|application|how (do|to|can)", t): return "apply"
    if re.search(r"eligib|qualify|can i get|am i", t): return "eligibility"
    return "discover"


def classify_query_type(text: str) -> str:
    """Identify the specific information requested by the user."""

    t = text.lower()

    if re.search(r"document|papers|certificate|proof|what should i submit", t):
        return "documents"

    if re.search(r"apply|application|registration|enrollment|how (do|to|can)", t):
        return "application"

    if re.search(r"eligib|qualify|who can get|who is eligible|can i get|am i", t):
        return "eligibility"

    if re.search(r"benefit|amount|financial assistance|subsidy|how much|installment|payment", t):
        return "benefits"

    if re.search(r"what is|overview|objective|purpose|explain|about the scheme", t):
        return "overview"

    return "general"



def topic_keywords(text: str) -> str:
    """
    Identify both general scheme categories and specific scheme names.
    This helps the retrieval agent find the correct schemes.
    """
    t = text.lower()
    keywords = {v for k, v in TOPICS.items() if k in t}

    scheme_aliases = {
        r"\bpm[\s-]?kisan\b": "pm-kisan",
        r"\bpmfby\b|\bpm[\s-]?fasal[\s-]?bima\b": "pmfby",
        r"\bkcc\b|kisan credit card": "kcc",
        r"\bpm[\s-]?kusum\b": "pm-kusum",
        r"\bpmay[\s-]?g\b|awas yojana gramin": "pmay-g",
        r"\bpmay[\s-]?u\b|awas yojana urban": "pmay-u",
        r"\bnmmss\b": "nmmss",
        r"\bpm[\s-]?yasasvi\b": "pm-yasasvi",
        r"\bpmjay\b|ayushman bharat": "pmjay",
        r"\bpmuy\b|ujjwala yojana": "ujjwala",
        r"\bmgnrega\b|nrega": "mgnrega",
        r"\bpm[\s-]?svanidhi\b": "pm-svanidhi",
        r"\bpmjdy\b|jan dhan yojana": "pmjdy",
        r"\bpm[\s-]?mvy\b|matru vandana": "pmmvy",
        r"\bpm[\s-]?kmy\b": "pm-kmy",
    }

    for pattern, scheme_keyword in scheme_aliases.items():
        if re.search(pattern, t):
            keywords.add(scheme_keyword)

    return " ".join(sorted(keywords))


def parse_income(text: str) -> int | None:
    t = text.lower().replace(",", "")
    if m := re.search(r"(\d+(?:\.\d+)?)\s*(?:lakh|lakhs|lac|lacs)\b", t): return int(float(m.group(1)) * 100000)
    if m := re.search(r"(\d+(?:\.\d+)?)\s*k\b", t): return int(float(m.group(1)) * 1000)
    if m := re.search(r"\b(\d{4,9})\b", t): return int(m.group(1))
    return None


def extract_facts(text: str) -> dict:
    t = text.lower()
    f: dict = {}
    m = re.search(r"\b(?:age(?: is)?|aged|i am|i'm|im)\s*(\d{1,3})\b", t) or re.search(r"\b(\d{1,3})\s*(?:years?|yrs?)\s*old", t)
    if m and 0 <= int(m.group(1)) <= 120: f["age"] = int(m.group(1))
    if re.search(r"income|earn|salary|lakh|lac\b", t) and (inc := parse_income(t)) is not None: f["annual_family_income"] = inc
    occ = r"(student|farmer|worker|labourer|homemaker|unemployed|entrepreneur|self[- ]employed)"
    if m := re.search(ME + occ, t) or (re.search(r"\b(i am|i'm|im|my)\b", t) and re.search(r"\b(?:an?|as)\s+" + occ, t)): f["occupation"] = OCC[m.group(1)]
    if m := re.search(ME + r"(woman|female|girl|lady|man|male|boy)\b", t): f["gender"] = "Female" if m.group(1) in ("woman", "female", "girl", "lady") else "Male"
    if re.search(r"maharashtra|mumbai|pune|nagpur", t): f["state"] = "Maharashtra"
    if m := re.search(r"\b(?:i am|i'm|category(?: is)?|belong to)\s*(?:an?\s+)?(obc|sc|st|general)\b", t): f["category"] = m.group(1).upper() if m.group(1) != "general" else "General"
    return f


def parse_answer(field: str, text: str):
    """Validate a free-text answer for one requested field; None if it cannot be understood."""
    if field == "age":
        m = re.search(r"\d{1,3}", text); return int(m.group()) if m and int(m.group()) <= 120 else None
    if field == "annual_family_income": return parse_income(text)
    for c in CHOICES.get(field, []):
        if c.lower() in text.lower(): return c
    return extract_facts(text).get(field)
