# AthenixAI – AI-Powered Government Scheme Discovery

**AthenixAI** is an AI-powered Government Scheme Discovery and Assistance System that helps users find relevant Central and Maharashtra government schemes based on their personal profiles. It uses Agentic AI and Retrieval-Augmented Generation (RAG) to provide scheme information, supporting evidence, and application guidance.

---

## Overview

Finding suitable government schemes can be difficult because information is spread across multiple government portals, documents, and guidelines.

AthenixAI simplifies this process by allowing users to create a profile, discover potentially relevant schemes, explore scheme details, and interact with an AI-powered chatbot.

## Key Features

- **Profile-Based Recommendations:** Suggests potentially relevant schemes based on age, state, income, occupation, gender, category, and education.
- **84 Government Schemes:** Includes Central Government and Maharashtra Government schemes.
- **Five-Agent Architecture:** Uses Orchestrator, Retrieval, Eligibility, Clarification, and Guidance agents.
- **Retrieval-Augmented Generation (RAG):** Retrieves relevant information from government scheme documents.
- **Hybrid Search:** Combines BM25 keyword retrieval and ChromaDB semantic search.
- **AI Chatbot:** Answers questions about scheme benefits, eligibility conditions, required documents, and application procedures.
- **Source Citations:** Provides supporting PDF document references and page numbers.
- **Explainable Recommendations:** Displays scheme information and manual-verification notices.
- **Responsive Frontend:** Interactive interface with light and dark themes.

## Technology Stack

| Component | Technologies |
|---|---|
| Programming Language | Python |
| Backend | FastAPI |
| Frontend | HTML, CSS, JavaScript |
| Database | SQLite |
| Vector Database | ChromaDB |
| Retrieval | BM25, Semantic Search, Hybrid Retrieval |
| AI Integration | Groq API |
| Document Processing | PyPDF |
| Embeddings | Sentence Transformers |
| Server | Uvicorn |
| Testing | Pytest |

## Agent Architecture

AthenixAI uses five specialized agents:

1. **Orchestrator Agent:** Understands user queries and coordinates the workflow.
2. **Retrieval Agent:** Retrieves relevant scheme information using hybrid search.
3. **Eligibility Agent:** Evaluates available profile information against configured eligibility rules.
4. **Clarification Agent:** Identifies missing information and asks relevant questions.
5. **Guidance Agent:** Generates explanations and provides scheme-related guidance with supporting evidence.

## RAG Workflow

1. Collect government scheme documents.
2. Extract text from PDF documents.
3. Split documents into smaller chunks.
4. Generate semantic embeddings.
5. Store document vectors in ChromaDB.
6. Retrieve relevant passages using BM25 and semantic search.
7. Combine retrieval results using hybrid ranking.
8. Generate grounded responses with supporting citations.

## Project Dataset

- **84** Central and Maharashtra government scheme records.
- **18** government scheme PDF documents.
- Scheme categories include agriculture, education, healthcare, housing, women empowerment, employment, and social welfare.

## Project Structure

```text
gsa/
│
├── apps/
│   ├── api/
│   │   └── app/
│   │       └── main.py
│   └── frontend/
│       ├── css/
│       ├── js/
│       └── index.html
│
├── data/
│   └── samples/
│       └── india-central-maharashtra-schemes.json
│
├── documents/
│   └── Government Scheme PDFs
│
├── scripts/
│   ├── build_vector_index.py
│   ├── import_real_schemes.py
│   └── import_seed.py
│
├── src/
│   └── govscheme/
│       ├── agents/
│       ├── application/
│       ├── config/
│       ├── document_processing/
│       ├── domain/
│       └── infrastructure/
│
├── storage/
├── tests/
├── requirements.txt
└── README.md
```

## Installation and Setup
