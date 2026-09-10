"""Persistent semantic memory for BerryLensAI fact-check results."""

import json
from datetime import datetime, timezone
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions
from config import settings


class BerryLensMemory:
    """Store and retrieve fact-checks using a local Chroma collection."""

    def __init__(self, persist_path=None):
        persist_path = persist_path or settings.chroma_path
        Path(persist_path).mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=persist_path)
        self.embedder = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        self.collection = self.client.get_or_create_collection(
            name="fact_checks",
            embedding_function=self.embedder,
            metadata={"hnsw:space": "cosine"},
        )

    def store(self, claim: str, result: dict) -> str:
        """Store one completed fact-check and return its document ID."""
        if result.get("research_status") in {"FAILED", "CACHED"}:
            return ""
        timestamp = datetime.now(timezone.utc).isoformat()
        doc_id = f"claim_{datetime.now(timezone.utc).timestamp()}"
        self.collection.add(
            ids=[doc_id],
            documents=[claim],
            metadatas=[
                {
                    "verdict": str(result.get("verdict", "UNKNOWN")),
                    "confidence": str(result.get("confidence", 0)),
                    "summary": str(result.get("summary", ""))[:500],
                    "sources": json.dumps(result.get("sources", [])[:3]),
                    "timestamp": timestamp,
                    "schema_version": str(result.get("schema_version", "1.1")),
                    "research_status": str(result.get("research_status", "COMPLETE")),
                }
            ],
        )
        return doc_id

    def search(self, claim: str, threshold: float = 0.85, n_results: int = 3) -> list:
        """Return cached results whose cosine similarity meets ``threshold``."""
        count = self.collection.count()
        if not count:
            return []

        results = self.collection.query(
            query_texts=[claim], n_results=min(n_results, count)
        )
        matches = []
        for index, distance in enumerate(results.get("distances", [[]])[0]):
            similarity = 1 - distance
            if similarity < threshold:
                continue
            metadata = results["metadatas"][0][index]
            timestamp = metadata.get("timestamp", "")
            try:
                age_days = (datetime.now(timezone.utc) - datetime.fromisoformat(timestamp)).days
            except (TypeError, ValueError):
                age_days = settings.max_cache_age_days + 1
            if age_days > settings.max_cache_age_days:
                continue
            matches.append(
                {
                    "claim": results["documents"][0][index],
                    "similarity": round(similarity * 100, 1),
                    "verdict": metadata.get("verdict", "UNKNOWN"),
                    "confidence": metadata.get("confidence", "0"),
                    "summary": metadata.get("summary", ""),
                    "sources": json.loads(metadata.get("sources", "[]")),
                    "timestamp": timestamp,
                    "from_cache": True,
                }
            )
        return matches

    def count(self) -> int:
        return self.collection.count()

    def clear(self) -> None:
        self.client.delete_collection("fact_checks")
        self.collection = self.client.get_or_create_collection(
            name="fact_checks",
            embedding_function=self.embedder,
            metadata={"hnsw:space": "cosine"},
        )
