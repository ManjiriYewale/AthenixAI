"""Bounded workflow controller (orchestration, not a sixth agent): ordered nodes, one retry, clarification limit."""
from __future__ import annotations
from govscheme.agents.agents import MAX_CLARIFY, Clarification, Eligibility, Guidance, Orchestrator, Retrieval


def new_state(message: str, profile: dict | None = None, pending_field: str | None = None,
              clarification_count: int = 0, skipped_fields: list[str] | None = None) -> dict:
    return {"message": message, "profile": dict(profile or {}), "pending_field": pending_field,
            "clarification_count": min(clarification_count, MAX_CLARIFY), "skipped_fields": list(skipped_fields or []),
            "intent": "discover", "keywords": "", "candidates": [], "evidence": {}, "results": [], "question": None,
            "warnings": [], "trace": [], "status": "completed", "reply": "", "citations": []}


class Workflow:
    def __init__(
        self,
        schemes,
        index,
        llm,
        vector_index=None,
    ) -> None:

        self.orch = Orchestrator()

        self.ret = Retrieval(
            schemes,
            index,
            vector_index,
        )

        self.elig = Eligibility()
        self.clar = Clarification()
        self.guide = Guidance(llm)

    def run(self, s: dict) -> dict:
        s.update(
            warnings=[],
            trace=[],
            citations=[],
            status="completed",
        )

        self._step(self.orch, s)

        nodes = (
            [self.guide]
            if s["intent"] == "greeting"
            else [
                self.ret,
                self.elig,
                self.clar,
                self.guide,
            ]
        )

        for node in nodes:
            if s["status"] == "error":
                break

            self._step(node, s)

        if s["status"] == "completed" and s["question"]:
            s["status"] = "needs_clarification"

        return s

    @staticmethod
    def _step(node, s: dict) -> None:
        for attempt in (1, 2):
            try:
                node.run(s)
                return

            except Exception:
                if attempt == 2:
                    s["status"] = "error"
                    s["reply"] = (
                        "Sorry, something went wrong while checking "
                        "schemes. Please try again or verify on official portals."
                    )

                    s["warnings"].append(
                        f"{type(node).__name__} failed twice."
                    )


                  
def to_response(s: dict) -> dict:
    return {
        "reply": s["reply"],
        "status": s["status"],
        "intent": s["intent"],
        "profile": s["profile"],
        "question": s["question"],
        "clarification_count": s["clarification_count"],
        "skipped_fields": s["skipped_fields"],
        "pending_field": s["pending_field"],
        "schemes": [
            {
                "id": r["id"],
                "name": r["name"],
                "status": r["status"],
            }
            for r in s["results"]
        ],
        "citations": s["citations"],
        "warnings": sorted(set(s["warnings"])),
        "trace": s["trace"],
    }
