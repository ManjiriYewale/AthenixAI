"""Deterministic eligibility engine. No web or DB imports. The LLM never decides eligibility."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any


class Outcome(str, Enum):
    SATISFIED = "SATISFIED"
    FAILED = "FAILED"
    MISSING = "MISSING"
    UNVERIFIED = "UNVERIFIED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class Status(str, Enum):
    ELIGIBLE = "Eligible"
    POTENTIAL = "Potentially eligible"
    NOT_ELIGIBLE = "Not eligible"
    MANUAL = "Manual verification required"


# Explicit API field -> canonical rule key mapping (units: INR per year, age in years).
FIELD_MAP = {"age": "age", "state": "state", "annual_family_income": "annual_family_income",
             "occupation": "occupation", "category": "category", "gender": "gender",
             "education": "education"}

OPS = {
    "less_than_or_equal": lambda a, e: a <= e,
    "greater_than_or_equal": lambda a, e: a >= e,
    "equals": lambda a, e: a == e,
    "in": lambda a, e: a in e,
}


@dataclass(frozen=True)
class Rule:
    criterion: str
    operator: str
    expected: Any
    description: str = ""
    source_reference: str = ""
    verification_status: str = "verification_required"
    last_verified_at: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None


@dataclass(frozen=True)
class CriterionResult:
    criterion: str
    outcome: Outcome
    reason: str
    description: str = ""
    indicative: bool | None = None  # what the check WOULD give if the rule were confirmed
    source_reference: str = ""


@dataclass
class Evaluation:
    status: Status
    criteria: list[CriterionResult] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


def to_canonical(profile: dict[str, Any]) -> dict[str, Any]:
    """Map API profile fields to canonical rule keys, dropping unknown/empty values."""
    return {FIELD_MAP[k]: v for k, v in profile.items() if k in FIELD_MAP and v not in (None, "")}


def evaluate_rule(rule: Rule, profile: dict[str, Any], today: date | None = None) -> CriterionResult:
    today = today or date.today()
    base = dict(criterion=rule.criterion, description=rule.description, source_reference=rule.source_reference)
    if (rule.effective_from and today < rule.effective_from) or (rule.effective_to and today > rule.effective_to):
        return CriterionResult(outcome=Outcome.NOT_APPLICABLE, reason="Rule is outside its effective dates.", **base)
    value = profile.get(rule.criterion)
    if value is None:
        return CriterionResult(outcome=Outcome.MISSING, reason="This profile value was not provided.", **base)
    try:
        met = OPS[rule.operator](value, rule.expected)
    except (KeyError, TypeError):
        return CriterionResult(outcome=Outcome.UNVERIFIED, reason="Value could not be compared with the rule.", **base)
    if rule.verification_status != "verified":  # never upgrade an unverified rule
        note = "meets" if met else "does not meet"
        return CriterionResult(outcome=Outcome.UNVERIFIED, indicative=met,
                               reason=f"Rule not yet verified against an official source; your value {note} it as written.", **base)
    return CriterionResult(outcome=Outcome.SATISFIED if met else Outcome.FAILED, indicative=met,
                           reason="Your value meets the verified rule." if met else "Your value violates the verified rule.", **base)


def evaluate_scheme(rules: list[Rule], profile: dict[str, Any], today: date | None = None) -> Evaluation:
    results = [evaluate_rule(r, profile, today) for r in rules]
    missing = [r.criterion for r in results if r.outcome is Outcome.MISSING]
    outcomes = {r.outcome for r in results}
    if not results:
        status = Status.MANUAL
    elif Outcome.FAILED in outcomes:
        status = Status.NOT_ELIGIBLE
    elif Outcome.UNVERIFIED in outcomes:
        status = Status.MANUAL
    elif Outcome.MISSING in outcomes:
        status = Status.POTENTIAL
    else:
        status = Status.ELIGIBLE
    return Evaluation(status, results, missing)
