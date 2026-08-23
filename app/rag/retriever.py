"""Hybrid retrieval: BM25 + ChromaDB + BGE reranker."""
import json
from pathlib import Path
from typing import Optional

import chromadb
from rank_bm25 import BM25Okapi

from config.settings import CHROMA_DIR, CURRENT_COLLECTION, HISTORICAL_COLLECTION


class HybridRetriever:
    """Combines BM25 keyword search + ChromaDB vector search + reranking."""

    def __init__(self):
        # Ensure directory exists
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        
        self.chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        
        # Try to get collections, create if they don't exist
        try:
            self.current_col = self.chroma_client.get_collection(CURRENT_COLLECTION)
        except Exception:
            self.current_col = self.chroma_client.create_collection(
                name=CURRENT_COLLECTION,
                metadata={"description": "Current authoritative documents"}
            )
        
        try:
            self.historical_col = self.chroma_client.get_collection(HISTORICAL_COLLECTION)
        except Exception:
            self.historical_col = self.chroma_client.create_collection(
                name=HISTORICAL_COLLECTION,
                metadata={"description": "Historical/context-only documents"}
            )
        
        # Ingest documents if collections are empty
        if self.current_col.count() == 0 and self.historical_col.count() == 0:
            self._ingest_documents()
        
        # Load all documents for BM25
        self._build_bm25_index()

        # Lazy-load reranker
        self._reranker = None

    def _ingest_documents(self):
        """Ingest documents if collections are empty."""
        try:
            from app.rag.ingest_documents import ingest_documents
            ingest_documents()
        except Exception as e:
            print(f"Warning: Could not ingest documents: {e}")

    def _build_bm25_index(self):
        """Build BM25 index from ChromaDB documents."""
        # Get all documents from both collections
        current_data = self.current_col.get()
        historical_data = self.historical_col.get()

        self.all_documents = []
        self.all_metadatas = []
        self.all_ids = []
        self.collection_map = {}  # id -> collection name

        for i, doc_id in enumerate(current_data["ids"]):
            self.all_documents.append(current_data["documents"][i])
            self.all_metadatas.append(current_data["metadatas"][i])
            self.all_ids.append(doc_id)
            self.collection_map[doc_id] = "current"

        for i, doc_id in enumerate(historical_data["ids"]):
            self.all_documents.append(historical_data["documents"][i])
            self.all_metadatas.append(historical_data["metadatas"][i])
            self.all_ids.append(doc_id)
            self.collection_map[doc_id] = "historical"

        # Tokenize for BM25 - handle empty corpus
        if self.all_documents:
            self.tokenized_docs = [
                doc.lower().split() for doc in self.all_documents
            ]
            self.bm25 = BM25Okapi(self.tokenized_docs)
        else:
            self.tokenized_docs = []
            self.bm25 = None

    def _get_reranker(self):
        """Lazy-load cross-encoder reranker."""
        if self._reranker is None:
            try:
                from sentence_transformers import CrossEncoder
                self._reranker = CrossEncoder("BAAI/bge-reranker-base")
            except Exception:
                # Fallback: skip reranking if model not available
                self._reranker = False
        return self._reranker

    def bm25_search(self, query: str, top_k: int = 10) -> list[dict]:
        """BM25 keyword search."""
        # Handle empty corpus
        if not self.bm25 or not self.tokenized_docs:
            return []
        
        tokenized_query = query.lower().split()
        scores = self.bm25.get_scores(tokenized_query)

        # Get top-k indices
        ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        results = []
        for idx in ranked_indices:
            if scores[idx] > 0:
                results.append({
                    "id": self.all_ids[idx],
                    "text": self.all_documents[idx],
                    "metadata": self.all_metadatas[idx],
                    "score": float(scores[idx]),
                    "method": "bm25",
                })
        return results

    def vector_search(self, query: str, top_k: int = 10,
                      account_id: Optional[str] = None) -> list[dict]:
        """ChromaDB vector search with metadata filtering."""
        # Build where filter
        where_filter = None
        if account_id:
            where_filter = {
                "$or": [
                    {"account_id": ""},
                    {"account_id": account_id},
                ]
            }

        # Search current collection
        current_results = self.current_col.query(
            query_texts=[query],
            n_results=min(top_k, self.current_col.count()),
            where=where_filter,
        )

        results = []
        for i, doc_id in enumerate(current_results["ids"][0]):
            distance = current_results["distances"][0][i] if current_results["distances"] else 0
            results.append({
                "id": doc_id,
                "text": current_results["documents"][0][i],
                "metadata": current_results["metadatas"][0][i],
                "score": 1 - distance,  # Convert distance to similarity
                "method": "vector",
            })

        return results

    def hybrid_search(self, query: str, top_k: int = 5,
                      account_id: Optional[str] = None,
                      use_reranker: bool = True) -> list[dict]:
        """Combined BM25 + vector search with optional reranking."""
        # Get candidates from both methods
        bm25_results = self.bm25_search(query, top_k=10)
        vector_results = self.vector_search(query, top_k=10, account_id=account_id)

        # Merge and deduplicate
        seen_ids = set()
        merged = []

        for result in bm25_results + vector_results:
            if result["id"] not in seen_ids:
                seen_ids.add(result["id"])
                merged.append(result)

        # Filter by account for customer-specific docs
        if account_id:
            filtered = []
            for r in merged:
                meta = r["metadata"]
                src_type = meta.get("source_type", "")
                doc_account = meta.get("account_id", "")

                # Include if: general doc, or same account's agreement
                if src_type != "customer_agreement" or doc_account == account_id:
                    filtered.append(r)
            merged = filtered

        # Rerank with cross-encoder
        reranker = self._get_reranker()
        if use_reranker and reranker and len(merged) > 0:
            pairs = [(query, r["text"][:512]) for r in merged]
            rerank_scores = reranker.predict(pairs)
            for i, score in enumerate(rerank_scores):
                merged[i]["rerank_score"] = float(score)
            merged.sort(key=lambda x: x.get("rerank_score", x["score"]), reverse=True)
        else:
            # Sort by combined score
            merged.sort(key=lambda x: x["score"], reverse=True)

        return merged[:top_k]

    def search_by_topic(self, query: str, topic: str,
                        account_id: Optional[str] = None,
                        top_k: int = 5) -> list[dict]:
        """Search with topic-specific filtering."""
        # Add topic context to query
        topic_enhanced = f"{topic}: {query}"

        results = self.hybrid_search(topic_enhanced, top_k=top_k * 2, account_id=account_id)

        # Filter by relevant source types based on topic
        topic_source_map = {
            "cancellation": ["customer_agreement", "sop", "support_policy"],
            "sla": ["customer_agreement", "support_policy"],
            "service_credit": ["customer_agreement", "sop"],
            "product_capability": ["customer_agreement", "product_guide"],
            "known_issue": ["product_guide"],
        }

        relevant_types = topic_source_map.get(topic, None)
        if relevant_types:
            filtered = [r for r in results if r["metadata"].get("source_type") in relevant_types]
            if filtered:
                return filtered[:top_k]

        return results[:top_k]
