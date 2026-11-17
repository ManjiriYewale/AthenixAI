
"""Build AthenixAI ChromaDB index from government scheme PDFs."""

import sys
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parents[1]

# Add source directory to Python path
sys.path.insert(0, str(ROOT / "src"))

from govscheme.document_processing.ingest import load_documents
from govscheme.infrastructure.vector_store import AthenixVectorStore


def main():

    print("\n===================================")
    print("       ATHENIXAI RAG INDEXER")
    print("===================================\n")

    documents_dir = ROOT / "documents"

    if not documents_dir.exists():
        raise FileNotFoundError("Documents folder not found.")

    print("[1] Reading government scheme PDFs...")

    documents = load_documents([documents_dir])

    if not documents:
        print("No document chunks found.")
        return

    print(f"Total chunks extracted: {len(documents)}")

    print("\n[2] Initializing ChromaDB...")

    vector_store = AthenixVectorStore(
        persist_directory=ROOT / "storage" / "chroma_db"
    )

    print("\n[3] Generating embeddings and indexing documents...")

    total = vector_store.add_documents(documents)

    print("\n[4] Indexing completed!")

    print(f"Total indexed chunks: {total}")

    print("\n[5] Testing semantic search...")

    query = "What are the eligibility conditions for PM Kisan?"

    results = vector_store.search(query, top_k=5)

    print(f"\nQuery: {query}")

    for i, result in enumerate(results, 1):

        print(f"\nResult {i}")
        print("Source:", result["source"])
        print("Page:", result["page"])
        print("Distance:", round(result["distance"], 4))
        print("Text:", result["text"][:300])

    print("\n===================================")
    print("      ATHENIXAI INDEX READY")
    print("===================================")


if __name__ == "__main__":
    main()
