from datetime import date
from govscheme.domain.engine import Outcome, Rule, Status, evaluate_scheme

V = dict(verification_status="verified")


def test_boundary_income_unverified_is_never_eligible():
    ev = evaluate_scheme([Rule("annual_family_income", "less_than_or_equal", 800000)], {"annual_family_income": 800000})
    assert ev.status is Status.MANUAL and ev.criteria[0].indicative is True


def test_verified_all_satisfied_is_eligible():
    assert evaluate_scheme([Rule("age", "greater_than_or_equal", 60, **V)], {"age": 60}).status is Status.ELIGIBLE


def test_verified_failure_is_not_eligible():
    assert evaluate_scheme([Rule("age", "greater_than_or_equal", 60, **V)], {"age": 59}).status is Status.NOT_ELIGIBLE


def test_missing_value_is_potential_and_listed():
    ev = evaluate_scheme([Rule("age", "less_than_or_equal", 25, **V)], {})
    assert ev.status is Status.POTENTIAL and ev.missing == ["age"]


def test_expired_rule_not_applicable_and_no_rules_manual():
    r = Rule("age", "less_than_or_equal", 25, effective_to=date(2020, 1, 1), **V)
    ev = evaluate_scheme([r], {"age": 90})
    assert ev.criteria[0].outcome is Outcome.NOT_APPLICABLE and ev.status is Status.ELIGIBLE
    assert evaluate_scheme([], {}).status is Status.MANUAL


def test_type_mismatch_is_unverified_not_crash():
    ev = evaluate_scheme([Rule("age", "less_than_or_equal", 25, **V)], {"age": "abc"})
    assert ev.criteria[0].outcome is Outcome.UNVERIFIED
