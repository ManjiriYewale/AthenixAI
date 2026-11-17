# Agentic RAG design (follows the engineering blueprint's five-agent contract)

Flow per chat turn: Orchestrator -> Retrieval -> Eligibility -> Clarification -> Guidance. The workflow controller
(`agents/workflow.py`) only sequences nodes, retries a failed node once, and enforces the clarification limit (3).
It is not a sixth agent. LangGraph is deliberately not used in v1; the node functions can be ported later.

| Agent | Does | Must not |
|---|---|---|
| Orchestrator | intent, input normalising, fact extraction (regex, no LLM), state merge | decide eligibility |
| Retrieval | SQL candidate filter + BM25 evidence with source and page | judge eligibility from similarity |
| Eligibility | deterministic rule engine, 5 outcomes | use the LLM |
| Clarification | one targeted question per turn, max 3, skip support | ask irrelevant data, loop |
| Guidance | grounded answer, citations, abstains without evidence, flags unverified sources | invent steps, documents, links |

RAG: `document_processing/ingest.py` (txt/pdf/docx -> pages -> clean -> chunks with scheme_id, source, page, deterministic id)
-> `infrastructure/bm25.py` (retrieval). Retrieved text is data: chunks matching injection patterns are flagged and never
shown or used. LLM: `infrastructure/llm.py` rewords a finished draft only and falls back to the draft if a status or
scheme name is dropped. Add real documents (PDF/DOCX/TXT named `<scheme_id>.pdf`) to `documents/`.

State: the chat is stateless on the server (profile and pending question travel with each request). `/api/v1/workflows`
keeps up to 200 runs in memory only.
