"""ChromaDB vector store for AthenixAI."""

from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction


class AthenixVectorStore:
    """Persistent semantic retrieval for government scheme documents."""

    def __init__(
        self,
        persist_directory="storage/chroma_db",
        collection_name="government_schemes",
        model_name="sentence-transformers/all-MiniLM-L6-v2",
    ):
        self.persist_directory = str(Path(persist_directory))

        Path(self.persist_directory).mkdir(
            parents=True,
            exist_ok=True,
        )

        # Use ChromaDB's ONNX-based embedding function instead of PyTorch.
        self.embedding_function = DefaultEmbeddingFunction()

        self.client = chromadb.PersistentClient(
            path=self.persist_directory
        )

        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_documents(self, documents, batch_size=100):
        """Generate embeddings and store document chunks."""

        if not documents:
            return self.collection.count()

        total = len(documents)

        for start in range(0, total, batch_size):
            batch = documents[start:start + batch_size]

            texts = [doc["text"] for doc in batch]

            embeddings = self.embedding_function(texts)

            ids = [doc["chunk_id"] for doc in batch]

            metadatas = [
                {
                    "scheme_id": str(doc["scheme_id"]),
                    "source": str(doc["source"]),
                    "page": int(doc["page"]),
                    "suspicious": bool(doc.get("suspicious", False)),
                }
                for doc in batch
            ]

            self.collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
            )

            print(
                f"Indexed {min(start + batch_size, total)}/{total}"
            )

        return self.collection.count()

    def search(
        self,
        query,
        top_k=5,
        scheme_id=None,
        include_suspicious=False,
    ):
        """Search semantically relevant document chunks."""

        total = self.collection.count()

        if not query.strip() or top_k <= 0 or total == 0:
            return []

        query_embedding = self.embedding_function([query])

        filters = []

        if scheme_id is not None:
            filters.append({"scheme_id": str(scheme_id)})

        if not include_suspicious:
            filters.append({"suspicious": False})

        where = None

        if len(filters) == 1:
            where = filters[0]
        elif len(filters) > 1:
            where = {"$and": filters}

        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=min(top_k, total),
            where=where,
            include=[
                "documents",
                "metadatas",
                "distances",
            ],
        )

        output = []

        if not results["documents"] or not results["documents"][0]:
            return output

        for text, metadata, distance in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            output.append({
                "text": text,
                "source": metadata["source"],
                "page": metadata["page"],
                "scheme_id": metadata["scheme_id"],
                "distance": round(float(distance), 4),
                "suspicious": metadata.get("suspicious", False),
            })

        return output

    def count(self):
        """Return the total number of indexed chunks."""

        return self.collection.count()