
"""RAG retrieval service for AthenixAI."""

from govscheme.infrastructure.vector_store import AthenixVectorStore


class RAGService:

    def __init__(self, vector_store):
        self.vector_store = vector_store

    def retrieve(self, question: str, top_k: int = 5):

        results = self.vector_store.search(
            query=question,
            top_k=top_k
        )

        # Exclude suspicious instruction-like content
        safe_results = [
            result for result in results
            if not result.get("suspicious", False)
        ]

        context = []

        for result in safe_results:
            context.append({
                "source": result["source"],
                "page": result["page"],
                "text": result["text"],
                "distance": result["distance"]
            })

        return {
            "question": question,
            "total_results": len(context),
            "context": context
        }
