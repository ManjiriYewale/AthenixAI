"""Use cases: candidate search, evaluation, and a grounded template explanation (mock LLM)."""
from __future__ import annotations
from datetime import date
from typing import Any
from govscheme.domain.engine import Outcome, Rule, Status, evaluate_scheme, to_canonical


def _rule(r: dict[str, Any]) -> Rule:
    f = lambda v: date.fromisoformat(v) if v else None
    return Rule(r["criterion"], r["operator"], r["expected"], r.get("description") or "", r.get("source_reference") or "",
                r.get("verification_status") or "verification_required", r.get("last_verified_at"),
                f(r.get("effective_from")), f(r.get("effective_to")))


def candidates(schemes: list[dict], profile: dict, keywords: str = "") -> list[dict]:
    """
    Find schemes using state and specific scheme/category keywords.
    Return only relevant candidates when keywords are supplied.
    """
    words = [w.lower() for w in keywords.split() if w]
    out = []

    for s in schemes:
        if (
            s["level"] == "State"
            and profile.get("state")
            and s["state"] != profile["state"]
        ):
            continue

        text = " ".join(
            str(s.get(k) or "")
            for k in ("name", "description", "benefit", "category")
        ).lower()

        hits = sum(word in text for word in words)

        if words and hits == 0:
            continue

        out.append((hits, s))

    return [
        scheme
        for _, scheme in sorted(out, key=lambda item: -item[0])
    ]



def explain(name: str, status: Status, criteria: list) -> str:
    """Deterministic explanation built only from evaluated results; abstains where sources are unverified."""
    lead = {Status.ELIGIBLE: "You appear to meet the verified conditions", Status.NOT_ELIGIBLE: "You do not meet a verified condition",
            Status.POTENTIAL: "You are potentially eligible, but some information is missing",
            Status.MANUAL: "Manual verification is required, because the available sources do not establish these conditions"}[status]
    notes = [f"{c.criterion.replace('_', ' ')}: {c.reason}" for c in criteria if c.outcome in (Outcome.FAILED, Outcome.MISSING, Outcome.UNVERIFIED)]
    return f"{lead} for {name}. " + " ".join(notes) + " This is a discovery aid, not an official eligibility decision."


def evaluate_all(schemes: list[dict], profile: dict, keywords: str = "") -> list[dict]:
    canon = to_canonical(profile)
    results = []
    for s in candidates(schemes, canon, keywords):
        ev = evaluate_scheme([_rule(r) for r in s["rules"]], canon)
        results.append({"id": s["id"], "name": s["name"], "level": s["level"], "state": s["state"] or "All India",
                        "category": s["category"], "benefit": s["benefit"], "status": ev.status.value,
                        "missing": ev.missing, "documents": s["documents"], "source_url": s.get("source_url"),
                        "source_status": s.get("source_status"),
                        "criteria": [{"criterion": c.criterion, "outcome": c.outcome.value, "reason": c.reason,
                                      "description": c.description, "indicative": c.indicative} for c in ev.criteria],
                        "explanation": explain(s["name"], ev.status, ev.criteria)})
    order = {"Eligible": 0, "Potentially eligible": 1, "Manual verification required": 2, "Not eligible": 3}
    return sorted(results, key=lambda r: order[r["status"]])
