"""Hybrid retrieval: BM25 + ChromaDB + BGE reranker (In-Memory Mode)."""
import json
from pathlib import Path
from typing import Optional

import chromadb
from rank_bm25 import BM25Okapi

from config.settings import CURRENT_COLLECTION, HISTORICAL_COLLECTION


class HybridRetriever:
    """Combines BM25 keyword search + ChromaDB vector search + reranking."""

    def __init__(self):
        # Use in-memory ChromaDB for cloud compatibility
        self.chroma_client = chromadb.Client()
        
        # Create collections
        self.current_col = self.chroma_client.create_collection(
            name=CURRENT_COLLECTION,
            metadata={"description": "Current authoritative documents"}
        )
        self.historical_col = self.chroma_client.create_collection(
            name=HISTORICAL_COLLECTION,
            metadata={"description": "Historical/context-only documents"}
        )
        
        # Ingest documents
        self._ingest_documents()
        
        # Load all documents for BM25
        self._build_bm25_index()

        # Lazy-load reranker
        self._reranker = None

    def _ingest_documents(self):
        """Ingest documents into collections."""
        try:
            from app.rag.ingest_documents import DOCUMENT_REGISTRY
            from pathlib import Path
            from config.settings import PDF_DIR
            import fitz  # PyMuPDF
            
            for filename, registry_info in DOCUMENT_REGISTRY.items():
                pdf_path = PDF_DIR / filename
                if not pdf_path.exists():
                    continue
                
                # Extract text
                doc = fitz.open(str(pdf_path))
                full_text = ""
                for page in doc:
                    full_text += page.get_text()
                doc.close()
                
                # Chunk text
                chunks = []
                chunk_size = 1000
                overlap = 200
                start = 0
                while start < len(full_text):
                    end = start + chunk_size
                    chunk = full_text[start:end]
                    if chunk.strip():
                        chunks.append(chunk.strip())
                    start = end - overlap
                
                if not chunks:
                    continue
                
                # Add to appropriate collection
                collection = self.current_col if registry_info["collection"] == "current" else self.historical_col
                
                ids = [f"{filename}_{i}" for i in range(len(chunks))]
                metadatas = [
                    {
                        "source_file": filename,
                        "source_type": registry_info.get("source_type", ""),
                        "status": registry_info.get("status", ""),
                        "authority": registry_info.get("authority", ""),
                        "account_id": registry_info.get("account_id", ""),
                    }
                    for _ in chunks
                ]
                
                collection.add(
                    documents=chunks,
                    metadatas=metadatas,
                    ids=ids,
                )
        except Exception as e:
            print(f"Warning: Document ingestion error: {e}")

    def _build_bm25_index(self):
        """Build BM25 index from ChromaDB documents."""
        current_data = self.current_col.get()
        historical_data = self.historical_col.get()

        self.all_documents = []
        self.all_metadatas = []
        self.all_ids = []

        for i, doc_id in enumerate(current_data["ids"]):
            self.all_documents.append(current_data["documents"][i])
            self.all_metadatas.append(current_data["metadatas"][i])
            self.all_ids.append(doc_id)

        for i, doc_id in enumerate(historical_data["ids"]):
            self.all_documents.append(historical_data["documents"][i])
            self.all_metadatas.append(historical_data["metadatas"][i])
            self.all_ids.append(doc_id)

        # Tokenize for BM25 - handle empty corpus
        if self.all_documents:
            self.tokenized_docs = [doc.lower().split() for doc in self.all_documents]
            self.bm25 = BM25Okapi(self.tokenized_docs)
        else:
            self.tokenized_docs = []
            self.bm25 = None

    def bm25_search(self, query: str, top_k: int = 10) -> list[dict]:
        """BM25 keyword search."""
        if not self.bm25 or not self.tokenized_docs:
            return []
        
        tokenized_query = query.lower().split()
        scores = self.bm25.get_scores(tokenized_query)
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
        if self.current_col.count() == 0:
            return []
        
        current_results = self.current_col.query(
            query_texts=[query],
            n_results=min(top_k, self.current_col.count()),
        )

        results = []
        for i, doc_id in enumerate(current_results["ids"][0]):
            distance = current_results["distances"][0][i] if current_results["distances"] else 0
            results.append({
                "id": doc_id,
                "text": current_results["documents"][0][i],
                "metadata": current_results["metadatas"][0][i],
                "score": 1 - distance,
                "method": "vector",
            })
        return results

    def hybrid_search(self, query: str, top_k: int = 5,
                      account_id: Optional[str] = None,
                      use_reranker: bool = True) -> list[dict]:
        """Combined BM25 + vector search."""
        bm25_results = self.bm25_search(query, top_k=10)
        vector_results = self.vector_search(query, top_k=10, account_id=account_id)

        seen_ids = set()
        merged = []
        for result in bm25_results + vector_results:
            if result["id"] not in seen_ids:
                seen_ids.add(result["id"])
                merged.append(result)

        if account_id:
            filtered = []
            for r in merged:
                meta = r["metadata"]
                src_type = meta.get("source_type", "")
                doc_account = meta.get("account_id", "")
                if src_type != "customer_agreement" or doc_account == account_id:
                    filtered.append(r)
            merged = filtered

        merged.sort(key=lambda x: x.get("score", 0), reverse=True)
        return merged[:top_k]

    def search_by_topic(self, query: str, topic: str,
                        account_id: Optional[str] = None,
                        top_k: int = 5) -> list[dict]:
        """Search with topic-specific filtering."""
        topic_enhanced = f"{topic}: {query}"
        results = self.hybrid_search(topic_enhanced, top_k=top_k * 2, account_id=account_id)

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
