
"""Improved dependency-free BM25 retrieval over document chunks."""

from __future__ import annotations

import math
import re
from collections import Counter

TOKEN = re.compile(r"[a-z0-9]+")

STOP = {
    "the", "a", "an", "of", "to", "is", "am", "i", "my",
    "me", "for", "and", "or", "in", "on", "do", "what",
    "are", "can", "get", "it", "this", "that", "be", "with",
    "how", "which", "who", "when", "where", "under"
}


def tokens(text: str) -> list[str]:
    """Convert text into normalized search tokens."""
    return [
        token
        for token in TOKEN.findall(text.lower())
        if token not in STOP
    ]


class EvidenceIndex:
    """BM25-based evidence retrieval with scheme filtering."""

    def __init__(
        self,
        chunks: list[dict],
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:

        self.chunks = chunks
        self.k1 = k1
        self.b = b

        documents = [tokens(chunk.get("text", "")) for chunk in chunks]

        self.tf = [Counter(document) for document in documents]
        self.doc_lengths = [len(document) for document in documents]

        self.avg_length = (
            sum(self.doc_lengths) / len(self.doc_lengths)
            if self.doc_lengths else 1.0
        )

        document_frequency = Counter(
            token
            for document in documents
            for token in set(document)
        )

        total_documents = len(documents)

        self.idf = {
            token: math.log(
                1 + (
                    total_documents - frequency + 0.5
                ) / (frequency + 0.5)
            )
            for token, frequency in document_frequency.items()
        }

    def _score(self, query_tokens: list[str], index: int) -> float:
        """Calculate BM25 relevance score."""

        score = 0.0
        document_length = self.doc_lengths[index]

        for token in query_tokens:

            frequency = self.tf[index].get(token, 0)

            if frequency == 0:
                continue

            idf = self.idf.get(token, 0.0)

            denominator = frequency + self.k1 * (
                1 - self.b
                + self.b * document_length / self.avg_length
            )

            score += (
                idf
                * frequency
                * (self.k1 + 1)
                / denominator
            )

        return score

    def search(
        self,
        query: str,
        scheme_id: str | None = None,
        k: int = 3,
    ) -> list[dict]:
        """
        Retrieve the most relevant evidence passages.

        Args:
            query: User query or expanded search query.
            scheme_id: Optional scheme-specific filter.
            k: Maximum number of passages to return.

        Returns:
            Ranked passages containing source, page, scheme_id and score.
        """

        if not query.strip() or k <= 0:
            return []

        # Remove duplicate query terms.
        query_tokens = list(dict.fromkeys(tokens(query)))

        if not query_tokens:
            return []

        hits = []

        for index, chunk in enumerate(self.chunks):

            if (
                scheme_id is not None
                and chunk.get("scheme_id") != scheme_id
            ):
                continue

            score = self._score(query_tokens, index)

            if score > 0:
                hits.append((score, chunk))

        # Highest relevance first.
        hits.sort(key=lambda item: item[0], reverse=True)

        results = []
        seen = set()

        for score, chunk in hits:

            text = chunk.get("text", "").strip()

            # Avoid returning duplicate passages.
            normalized_text = " ".join(text.lower().split())

            if not normalized_text or normalized_text in seen:
                continue

            seen.add(normalized_text)

            results.append({
                **chunk,
                "score": round(score, 3),
            })

            if len(results) >= k:
                break

        return results
