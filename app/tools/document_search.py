"""Document search tool — searches policies, SOPs, agreements, product docs."""
import json
from typing import Optional
from app.rag.retriever import HybridRetriever
from app.engine.source_authority import resolve_authority, detect_conflicts, format_source_citation


class DocumentSearchTool:
    """Tool for searching document corpus with authority resolution."""

    def __init__(self):
        self.retriever = HybridRetriever()

    def run(self, query: str, topic: str = "general",
            account_id: Optional[str] = None,
            top_k: int = 5) -> dict:
        """Search documents and return authoritative answer with sources.

        Args:
            query: User's question
            topic: Topic category (cancellation, sla, service_credit, etc.)
            account_id: Customer account ID for agreement filtering
            top_k: Number of results to retrieve
        """
        # Retrieve relevant chunks
        results = self.retriever.search_by_topic(
            query=query,
            topic=topic,
            account_id=account_id,
            top_k=top_k,
        )

        if not results:
            return {
                "found": False,
                "answer": "No relevant documents found.",
                "sources": [],
                "authority": None,
                "conflicts": [],
            }

        # Resolve authority
        authority = resolve_authority(
            topic=topic,
            retrieved_sources=[r["metadata"] for r in results],
            account_id=account_id,
        )

        # Detect conflicts
        conflicts = detect_conflicts(
            retrieved_sources=[r["metadata"] for r in results],
            topic=topic,
        )

        # Format sources
        sources = []
        for r in results:
            meta = r["metadata"]
            sources.append({
                "text": r["text"][:500],
                "source_file": meta.get("source_file", "unknown"),
                "source_type": meta.get("source_type", "unknown"),
                "status": meta.get("status", "unknown"),
                "authority": meta.get("authority", "unknown"),
                "account_id": meta.get("account_id", ""),
                "score": r.get("rerank_score", r.get("score", 0)),
            })

        return {
            "found": True,
            "answer": authority.content[:1000] if authority.content else "No authoritative content found.",
            "sources": sources,
            "authority": {
                "source_name": authority.source_name,
                "source_type": authority.source_type,
                "confidence": authority.confidence,
                "reasoning": authority.reasoning,
            },
            "conflicts": conflicts,
            "citation": format_source_citation(authority),
        }
