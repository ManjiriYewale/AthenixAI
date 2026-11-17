"""The five agents. State is a plain dict (see workflow.new_state). Only the Eligibility agent judges eligibility."""
from __future__ import annotations
from collections import Counter
from govscheme.agents import nlu
from govscheme.application.service import candidates, evaluate_all
from govscheme.domain.engine import to_canonical

MAX_CLARIFY = 3
ICON = {"Eligible": "✔", "Potentially eligible": "◐", "Not eligible": "✖", "Manual verification required": "⚑"}

INTENT_TERMS = {
    "documents": (
        "required documents identity proof Aadhaar certificate "
        "bank passbook land records income certificate"
    ),

    "apply": (
        "application procedure registration enrollment "
        "online application official portal application steps"
    ),

    "eligibility": (
        "eligibility criteria qualifying conditions "
        "eligible beneficiaries exclusions disqualifications "
        "income age occupation landholding requirements"
    ),

    "discover": (
        "scheme overview objectives purpose benefits "
        "financial assistance coverage features"
    ),
}



def log(s: dict, agent: str, note: str) -> None:
    s["trace"].append({"agent": agent, "action": note})



class Orchestrator:
    """Understands intent, query type, normalises input and merges facts."""

    def run(self, s: dict) -> None:
        text = s["message"][:500]

        # Identify general intent
        s["intent"] = nlu.classify(text)

        # Identify specific information requested
        s["query_type"] = nlu.classify_query_type(text)

        # Extract user profile information
        facts = nlu.extract_facts(text)

        pf = s.get("pending_field")

        if pf in nlu.ORDER:
            if pf not in facts:
                v = nlu.parse_answer(pf, text)

                if v is not None:
                    facts[pf] = v

                elif nlu.SKIP.search(text):
                    s["skipped_fields"].append(pf)

        s["pending_field"] = None
        s["profile"].update(facts)

        # Identify government scheme keywords
        s["keywords"] = nlu.topic_keywords(text)

        log(
            s,
            "Orchestrator",
            f"intent={s['intent']}; "
            f"query_type={s['query_type']}; "
            f"learned {sorted(facts) or 'nothing new'}",
        )


class Retrieval:
    """Hybrid BM25 + ChromaDB retrieval with query-type awareness."""

    QUERY_TYPE_TERMS = {
        "benefits": (
            "benefits financial assistance amount subsidy "
            "payment installments annual income support "
            "monetary assistance"
        ),

        "eligibility": (
            "eligibility criteria qualifying conditions "
            "eligible beneficiaries exclusions disqualifications "
            "income age occupation landholding requirements"
        ),

        "application": (
            "application procedure registration enrollment "
            "online application official portal application steps"
        ),

        "documents": (
            "required documents identity proof Aadhaar "
            "certificates bank passbook land records"
        ),

        "overview": (
            "scheme overview objectives purpose features "
            "main provisions and benefits"
        ),

        "general": "scheme information government assistance",
    }

    def __init__(self, schemes, index, vector_index=None) -> None:
        self.schemes = schemes
        self.index = index
        self.vector_index = vector_index

    @staticmethod
    def _passage_key(item):
        return (
            item.get("source", ""),
            item.get("page", 0),
            " ".join(item.get("text", "").lower().split()),
        )

    def _hybrid_search(self, query, scheme_id, k=3):
        """Combine BM25 and ChromaDB rankings using RRF."""

        bm25_results = self.index.search(
            query,
            scheme_id,
            k=8,
        )

        vector_results = []

        if self.vector_index is not None:
            vector_results = self.vector_index.search(
                query,
                top_k=8,
                scheme_id=scheme_id,
            )

        fused = {}

        # BM25 ranking
        for rank, item in enumerate(bm25_results, start=1):

            if item.get("suspicious", False):
                continue

            key = self._passage_key(item)

            fused.setdefault(key, {
                **item,
                "hybrid_score": 0.0,
                "retrieval_methods": [],
            })

            fused[key]["hybrid_score"] += 1 / (60 + rank)

            if "BM25" not in fused[key]["retrieval_methods"]:
                fused[key]["retrieval_methods"].append("BM25")

        # ChromaDB ranking
        for rank, item in enumerate(vector_results, start=1):

            if item.get("suspicious", False):
                continue

            key = self._passage_key(item)

            fused.setdefault(key, {
                **item,
                "hybrid_score": 0.0,
                "retrieval_methods": [],
            })

            fused[key]["hybrid_score"] += 1 / (60 + rank)

            if "ChromaDB" not in fused[key]["retrieval_methods"]:
                fused[key]["retrieval_methods"].append("ChromaDB")

        ranked = sorted(
            fused.values(),
            key=lambda item: item["hybrid_score"],
            reverse=True,
        )

        return ranked[:k]

    def run(self, s: dict) -> None:

        # Find relevant candidate schemes
        cands = candidates(
            self.schemes(),
            to_canonical(s["profile"]),
            s["keywords"],
        )[:5]

        s["candidates"] = cands
        s["evidence"] = {}

        # Identify the specific information requested
        query_type = s.get("query_type", "general")

        query_terms = self.QUERY_TYPE_TERMS.get(
            query_type,
            self.QUERY_TYPE_TERMS["general"],
        )

        # Combine question-specific terms with original question
        query = f"{query_terms} {s['message']}"

        # Retrieve evidence separately for each scheme
        for scheme in cands:

            scheme_id = scheme["id"]

            passages = self._hybrid_search(
                query,
                scheme_id,
                k=3,
            )

            s["evidence"][scheme_id] = passages

        total_evidence = sum(
            len(passages)
            for passages in s["evidence"].values()
        )

        log(
            s,
            "Retrieval",
            f"{len(cands)} candidate schemes; "
            f"{total_evidence} hybrid evidence passages; "
            f"query_type={query_type}",
        )

class Eligibility:
    """Calls the deterministic rule engine. Statuses here are final for the turn."""
    def run(self, s: dict) -> None:
        s["results"] = evaluate_all(s["candidates"], s["profile"])
        log(s, "Eligibility", ", ".join(f"{r['id']}={r['status']}" for r in s["results"]) or "no schemes")


class Clarification:
    """
    Asks one targeted question per turn.

    Uses eligibility-rule gaps first. If rules are unavailable,
    asks relevant profile questions for better discovery.
    """

    def run(self, s: dict) -> None:
        s["question"] = None

        if s["intent"] not in ("discover", "eligibility"):
            return

        profile = s["profile"]
        skipped = s["skipped_fields"]

        # ------------------------------------------------
        # 1. COLLECT MISSING FIELDS FROM ELIGIBILITY RULES
        # ------------------------------------------------

        freq = Counter(
            missing
            for result in s["results"]
            if result["status"] != "Not eligible"
            for missing in result.get("missing", [])
            if missing not in skipped
            and not profile.get(missing)
        )

        # ------------------------------------------------
        # 2. FALLBACK FOR SCHEMES WITHOUT STRUCTURED RULES
        # ------------------------------------------------

        message = s["message"].lower()

        education_request = (
            "scholarship" in message
            or "education" in message
            or any(
                str(result.get("category", "")).lower() == "education"
                for result in s["results"]
            )
        )

        fallback_fields = []

        if education_request:
            fallback_fields = [
                "education",
                "state",
                "annual_family_income",
                "category",
            ]

        # Use only fields supported by the existing NLU configuration.
        for field in fallback_fields:
            if (
                field in nlu.ORDER
                and field not in profile
                and field not in skipped
                and field in nlu.QUESTIONS
            ):
                freq[field] += 1

        # ------------------------------------------------
        # 3. STOP IF NO QUESTION IS REQUIRED
        # ------------------------------------------------

        if not freq:
            return

        # ------------------------------------------------
        # 4. LIMIT TOTAL CLARIFICATION QUESTIONS
        # ------------------------------------------------

        if s["clarification_count"] >= MAX_CLARIFY:
            s["warnings"].append(
                "I have asked enough questions; remaining gaps "
                "need manual verification."
            )
            s["status"] = "manual_review"
            return

        # ------------------------------------------------
        # 5. SELECT ONE QUESTION
        # ------------------------------------------------

        f = min(
            freq,
            key=lambda field: (
                -freq[field],
                nlu.ORDER.index(field),
            ),
        )

        s["question"] = {
            "field": f,
            "text": nlu.QUESTIONS[f],
            "choices": nlu.CHOICES.get(f, []),
        }

        s["pending_field"] = f
        s["clarification_count"] += 1

        log(
            s,
            "Clarification",
            f"asking for {f} "
            f"({s['clarification_count']}/{MAX_CLARIFY})",
        )

class Guidance:
    """
    Generates evidence-based scheme explanations.

    Uses:
    - Scheme catalogue information
    - Deterministic eligibility results
    - Retrieved government PDF passages

    Never invents eligibility conditions or application steps.
    """

    def __init__(self, llm) -> None:
        self.llm = llm

    def run(self, s: dict) -> None:

        intent = s["intent"]
        results = s["results"]

        if intent == "greeting":
            s["reply"] = (
                "Hello! I'm AthenixAI. "
                "I can help you discover government schemes, "
                "understand eligibility, find required documents "
                "and learn how to apply."
            )
            return

        lines = []
        citations = []

        # --------------------------------------------------
        # NO MATCHING SCHEMES
        # --------------------------------------------------

        if not results:
            lines.append(
                "No matching government scheme was found "
                "in the current catalogue."
            )

            lines.append(
                "Please provide more details or check "
                "the relevant official government portal."
            )

        # --------------------------------------------------
        # PROCESS EACH MATCHING SCHEME
        # --------------------------------------------------

        for result in results[:5]:

            scheme_id = result["id"]
            scheme_name = result["name"]
            status = result["status"]

            lines.append("")
            lines.append("=" * 45)

            lines.append(
                f"{ICON[status]} {scheme_name}"
            )

            lines.append(
                f"Eligibility status: {status}"
            )

            # --------------------------------------------------
            # SCHEME INFORMATION
            # --------------------------------------------------

            if result.get("category"):
                lines.append(
                    f"Category: {result['category']}"
                )

            if result.get("benefit"):
                lines.append(
                    f"Available benefit: {result['benefit']}"
                )

            # --------------------------------------------------
            # RETRIEVED PDF EVIDENCE
            # --------------------------------------------------

            raw_evidence = s.get("evidence", {}).get(
                scheme_id, []
            )

            evidence = [
                item
                for item in raw_evidence
                if not item.get("suspicious", False)
            ]

            if len(evidence) < len(raw_evidence):
                s["warnings"].append(
                    "A source passage containing instruction-like "
                    "text was ignored."
                )

            lines.append("")
            lines.append("OFFICIAL DOCUMENT EVIDENCE:")

            if evidence:

                for item in evidence[:2]:

                    source = item["source"]
                    page = item["page"]
                    snippet = item["text"].strip()

                    lines.append(
                        f"\nSource: {source}"
                    )

                    lines.append(
                        f"Page: {page}"
                    )

                    lines.append(
                        f"Extracted information: {snippet}"
                    )

                    citations.append({
                        "scheme_id": scheme_id,
                        "source": source,
                        "page": page,
                        "snippet": snippet[:500],
                    })

            else:

                lines.append(
                    "No relevant PDF evidence was retrieved "
                    "for this scheme."
                )

                s["warnings"].append(
                    f"No PDF evidence retrieved for {scheme_name}."
                )

            # --------------------------------------------------
            # REQUIRED DOCUMENTS
            # --------------------------------------------------

            if intent == "documents":

                documents = result.get("documents", [])

                lines.append("")
                lines.append("REQUIRED DOCUMENTS:")

                if documents:

                    for document in documents:
                        lines.append(f"- {document}")

                    lines.append(
                        "Confirm the latest document requirements "
                        "with the official scheme authority."
                    )

                else:

                    lines.append(
                        "The available catalogue does not establish "
                        "the required documents."
                    )

            # --------------------------------------------------
            # APPLICATION GUIDANCE
            # --------------------------------------------------

            elif intent == "apply":

                lines.append("")
                lines.append("APPLICATION GUIDANCE:")

                steps = []

                for item in evidence:

                    text = item["text"].replace(
                        " Step", "\nStep"
                    )

                    for line in text.splitlines():

                        line = line.strip()

                        if line.startswith("Step"):
                            steps.append(line)

                if steps:

                    for step in steps[:4]:
                        lines.append(f"- {step}")

                else:

                    lines.append(
                        "The retrieved passages do not establish "
                        "a complete application procedure. "
                        "Please verify the latest process "
                        "on the official portal."
                    )

            # --------------------------------------------------
            # ELIGIBILITY EXPLANATION
            # --------------------------------------------------

            if intent == "eligibility":

                lines.append("")
                lines.append("ELIGIBILITY ASSESSMENT:")

                criteria = result.get("criteria", [])

                if criteria:

                    for criterion in criteria:

                        description = (
                            criterion.get("description")
                            or criterion.get("criterion")
                        )

                        lines.append(
                            f"- {description}: "
                            f"{criterion['outcome']} — "
                            f"{criterion['reason']}"
                        )

                else:

                    lines.append(
                        "No structured eligibility rules are "
                        "available for a reliable assessment."
                    )

                lines.append(
                    f"Current assessment: {status}."
                )

            # --------------------------------------------------
            # MISSING PROFILE INFORMATION
            # --------------------------------------------------

            missing = result.get("missing", [])

            if missing:

                lines.append("")
                lines.append("ADDITIONAL INFORMATION NEEDED:")

                for field in missing:
                    lines.append(
                        f"- {field.replace('_', ' ').title()}"
                    )

        # --------------------------------------------------
        # SOURCE VERIFICATION WARNING
        # --------------------------------------------------

        if any(
            (result.get("source_status") or "")
            != "verified"
            for result in results
        ):

            warning = (
                "Some source records have not yet been verified. "
                "Please manually confirm the information "
                "against current official government guidelines."
            )

            if warning not in s["warnings"]:
                s["warnings"].append(warning)

        # --------------------------------------------------
        # CLARIFICATION QUESTION
        # --------------------------------------------------

        if s.get("question"):

            lines.append("")
            lines.append(
                s["question"]["text"]
            )

        # --------------------------------------------------
        # FINAL DISCLAIMER
        # --------------------------------------------------

        lines.append("")
        lines.append(
            "IMPORTANT: AthenixAI is a government scheme "
            "discovery and assistance system."
        )

        lines.append(
            "This is not an official eligibility decision. "
            "No application has been submitted."
        )

               # --------------------------------------------------
        # BUILD GROUNDED LLM CONTEXT
        # --------------------------------------------------

        s["citations"] = citations

        context_parts = []

        for result in results[:5]:

            scheme_id = result["id"]

            context_parts.append(
                f"SCHEME: {result['name']}"
            )

            context_parts.append(
                f"ELIGIBILITY STATUS: {result['status']}"
            )

            context_parts.append(
                f"BENEFIT: {result.get('benefit', 'Not specified')}"
            )

            evidence = s.get("evidence", {}).get(
                scheme_id, []
            )

            for item in evidence[:2]:

                if item.get("suspicious", False):
                    continue

                context_parts.append(
                    f"""
SOURCE: {item['source']}
PAGE: {item['page']}
EVIDENCE:
{item['text'][:1200]}
"""
                )

        context = "\n".join(context_parts)

        # --------------------------------------------------
        # GENERATE EVIDENCE-GROUNDED ANSWER
        # --------------------------------------------------

        fallback = "\n".join(lines)
        s["reply"] = fallback

        if context.strip():

            generated_answer = self.llm.answer(
                question=s["message"],
                context=context,
                fallback=fallback,
            )

            if generated_answer:
                s["reply"] = generated_answer

        # --------------------------------------------------
        # LOGGING
        # --------------------------------------------------

        log(
            s,
            "Guidance",
            f"{len(citations)} citations; "
            f"query_type={s.get('query_type', 'general')}; "
            f"LLM answer generation attempted; "
            f"warnings={len(s['warnings'])}"
        )