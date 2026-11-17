"""
Application services for AthenixAI.

Responsibilities:
1. Find relevant government schemes.
2. Filter schemes using specific names and categories.
3. Evaluate eligibility using deterministic rules.
4. Generate explanations without inventing eligibility conditions.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from govscheme.domain.engine import (
    Outcome,
    Rule,
    Status,
    evaluate_scheme,
    to_canonical,
)


# ============================================================
# SPECIFIC SCHEME ALIASES
# ============================================================

SPECIFIC_SCHEME_ALIASES = {
    "pm-kisan": [
        "pm-kisan",
        "pm kisan",
    ],
    "pmfby": [
        "pmfby",
        "fasal bima",
    ],
    "kcc": [
        "kisan credit card",
    ],
    "pm-kusum": [
        "pm-kusum",
        "pm kusum",
    ],
    "pmay-g": [
        "pmay-g",
        "pmay g",
    ],
    "pmay-u": [
        "pmay-u",
        "pmay u",
    ],
    "nmmss": [
        "nmmss",
    ],
    "pm-yasasvi": [
        "pm yasasvi",
        "pm-yasasvi",
    ],
    "pmjay": [
        "pm-jay",
        "pmjay",
    ],
    "ujjwala": [
        "ujjwala",
    ],
    "mgnrega": [
        "mgnrega",
        "nrega",
    ],
    "pm-svanidhi": [
        "pm svanidhi",
        "pm-svanidhi",
    ],
    "pmjdy": [
        "pmjdy",
        "jan dhan",
    ],
    "pmmvy": [
        "pmmvy",
        "matru vandana",
    ],
    "pm-kmy": [
        "pm-kmy",
        "pm kmy",
    ],
}


# ============================================================
# RULE CONVERSION
# ============================================================

def _rule(r: dict[str, Any]) -> Rule:
    """Convert a database eligibility rule into a domain Rule."""

    f = lambda v: date.fromisoformat(v) if v else None

    return Rule(
        r["criterion"],
        r["operator"],
        r["expected"],
        r.get("description") or "",
        r.get("source_reference") or "",
        r.get("verification_status") or "verification_required",
        r.get("last_verified_at"),
        f(r.get("effective_from")),
        f(r.get("effective_to")),
    )


# ============================================================
# SCHEME CANDIDATE SEARCH
# ============================================================

def candidates(
    schemes: list[dict],
    profile: dict,
    keywords: str = "",
) -> list[dict]:
    """
    Find relevant government schemes using keywords,
    location and education-level relevance.

    This function ranks recommendations; it does not
    make eligibility decisions.
    """

    words = [
        word.lower()
        for word in keywords.split()
        if word.strip()
    ]

    state = str(profile.get("state") or "").strip().lower()
    education = str(profile.get("education") or "").strip().lower()
    age = profile.get("age")

    # Identify higher-education applicants.
    higher_education = any(
        term in education
        for term in (
            "b.tech", "btech", "b.e.", "engineering",
            "bachelor", "undergraduate", "college",
            "university", "postgraduate", "master",
            "m.tech", "mtech", "mba", "degree",
        )
    )

    # Identify school-level applicants.
    school_education = any(
        term in education
        for term in (
            "school", "class 8", "class 9", "class 10",
            "class 11", "class 12", "secondary",
        )
    )

    def matches_state(scheme: dict) -> bool:
        scheme_level = str(scheme.get("level") or "").lower()
        scheme_state = str(scheme.get("state") or "").strip().lower()

        if scheme_level == "state" and state:
            return scheme_state == state

        return True

    requested_schemes = [
        word for word in words
        if word in SPECIFIC_SCHEME_ALIASES
    ]

    # Specific scheme searches retain their existing behaviour.
    if requested_schemes:
        aliases = [
            alias
            for keyword in requested_schemes
            for alias in SPECIFIC_SCHEME_ALIASES[keyword]
        ]

        return [
            scheme for scheme in schemes
            if matches_state(scheme)
            and any(
                alias in str(scheme.get("name") or "").lower()
                for alias in aliases
            )
        ]

    results = []

    for scheme in schemes:
        if not matches_state(scheme):
            continue

        name = str(scheme.get("name") or "").lower()

        searchable_text = " ".join(
            str(scheme.get(field) or "")
            for field in (
                "name", "description", "benefit", "category"
            )
        ).lower()

        # Avoid recommending school-only scholarships
        # to applicants already pursuing higher education.
        school_scheme = (
            "national means-cum-merit" in name
            or "nmms" in name
        )

        if higher_education and school_scheme:
            continue

        # Avoid recommending college scholarships to
        # applicants whose profile explicitly says school.
        college_scheme = any(
            term in name
            for term in ("college", "university", "higher education")
        )

        if school_education and college_scheme:
            continue

        hits = sum(
            word in searchable_text
            for word in words
        )

        if words and hits == 0:
            continue

        score = hits

        # Prefer college/university scholarships for
        # applicants pursuing higher education.
        if higher_education and college_scheme:
            score += 10

        if higher_education and "education" in searchable_text:
            score += 2

        results.append((score, scheme))

    results.sort(key=lambda item: -item[0])

    return [
        scheme for _, scheme in results
    ]
# ============================================================
# ELIGIBILITY EXPLANATION
# ============================================================

def explain(
    name: str,
    status: Status,
    criteria: list,
) -> str:
    """
    Generate a deterministic eligibility explanation.

    The explanation uses evaluated rule results.
    It does not invent eligibility conditions.
    """

    lead = {
        Status.ELIGIBLE:
            "You appear to meet the verified conditions",

        Status.NOT_ELIGIBLE:
            "You do not meet a verified condition",

        Status.POTENTIAL:
            "You are potentially eligible, but some information is missing",

        Status.MANUAL:
            "Manual verification is required, because the available sources do not establish these conditions",
    }[status]

    notes = [
        f"{criterion.criterion.replace('_', ' ')}: {criterion.reason}"
        for criterion in criteria
        if criterion.outcome in (
            Outcome.FAILED,
            Outcome.MISSING,
            Outcome.UNVERIFIED,
        )
    ]

    explanation = (
        f"{lead} for {name}. "
        + " ".join(notes)
        + " This is a discovery aid, not an official eligibility decision."
    )

    return explanation


# ============================================================
# EVALUATE ALL CANDIDATE SCHEMES
# ============================================================

def evaluate_all(
    schemes: list[dict],
    profile: dict,
    keywords: str = "",
) -> list[dict]:
    """
    Evaluate eligibility for the supplied candidate schemes.

    Eligibility is determined only by the deterministic
    domain rule engine.
    """

    canonical_profile = to_canonical(profile)

    results = []

    selected_schemes = candidates(
        schemes,
        canonical_profile,
        keywords,
    )

    for scheme in selected_schemes:

        rules = [
            _rule(rule)
            for rule in scheme.get("rules", [])
        ]

        evaluation = evaluate_scheme(
            rules,
            canonical_profile,
        )

        results.append({

            "id": scheme["id"],

            "name": scheme["name"],

            "level": scheme["level"],

            "state": scheme.get("state") or "All India",

            "category": scheme.get("category"),

            "benefit": scheme.get("benefit"),

            "status": evaluation.status.value,

            "missing": evaluation.missing,

            "documents": scheme.get("documents", []),

            "source_url": scheme.get("source_url"),

            "source_status": scheme.get("source_status"),

            "criteria": [

                {
                    "criterion": criterion.criterion,

                    "outcome": criterion.outcome.value,

                    "reason": criterion.reason,

                    "description": criterion.description,

                    "indicative": criterion.indicative,
                }

                for criterion in evaluation.criteria
            ],

            "explanation": explain(
                scheme["name"],
                evaluation.status,
                evaluation.criteria,
            ),
        })

    # --------------------------------------------------------
    # ELIGIBILITY RESULT PRIORITY
    # --------------------------------------------------------

    status_order = {
        "Eligible": 0,
        "Potentially eligible": 1,
        "Manual verification required": 2,
        "Not eligible": 3,
    }

    results.sort(
        key=lambda result: status_order.get(
            result["status"],
            99,
        )
    )

    return results