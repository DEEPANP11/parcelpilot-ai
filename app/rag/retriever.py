"""Hybrid retrieval: BM25 only (Cloud-compatible)."""
from typing import Optional
from rank_bm25 import BM25Okapi


class HybridRetriever:
    """BM25 keyword search - no ChromaDB dependency."""

    def __init__(self):
        self.all_documents = []
        self.all_metadatas = []
        self.all_ids = []
        
        # Ingest documents
        self._load_documents()
        
        # Build BM25 index
        if self.all_documents:
            self.tokenized_docs = [doc.lower().split() for doc in self.all_documents]
            self.bm25 = BM25Okapi(self.tokenized_docs)
        else:
            self.tokenized_docs = []
            self.bm25 = None

    def _load_documents(self):
        """Load documents from PDFs."""
        try:
            from app.rag.ingest_documents import DOCUMENT_REGISTRY
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
                chunk_size = 1000
                overlap = 200
                start = 0
                idx = 0
                while start < len(full_text):
                    end = start + chunk_size
                    chunk = full_text[start:end]
                    if chunk.strip():
                        self.all_documents.append(chunk.strip())
                        self.all_metadatas.append({
                            "source_file": filename,
                            "source_type": registry_info.get("source_type", ""),
                            "status": registry_info.get("status", ""),
                            "authority": registry_info.get("authority", ""),
                            "account_id": registry_info.get("account_id", ""),
                        })
                        self.all_ids.append(f"{filename}_{idx}")
                        idx += 1
                    start = end - overlap
        except Exception as e:
            print(f"Warning: Document loading error: {e}")

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
        """Fallback to BM25 when vector search not available."""
        return self.bm25_search(query, top_k)

    def hybrid_search(self, query: str, top_k: int = 5,
                      account_id: Optional[str] = None,
                      use_reranker: bool = True) -> list[dict]:
        """Search using BM25."""
        results = self.bm25_search(query, top_k=top_k * 2)

        # Filter by account if needed
        if account_id:
            filtered = []
            for r in results:
                meta = r["metadata"]
                src_type = meta.get("source_type", "")
                doc_account = meta.get("account_id", "")
                if src_type != "customer_agreement" or doc_account == account_id:
                    filtered.append(r)
            results = filtered

        return results[:top_k]

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
