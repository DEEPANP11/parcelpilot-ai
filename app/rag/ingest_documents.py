"""PDF extraction, metadata assignment, and ChromaDB ingestion."""
import json
import hashlib
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

import fitz  # PyMuPDF
import chromadb
from chromadb.config import Settings as ChromaSettings

from config.settings import PDF_DIR, CHROMA_DIR, CURRENT_COLLECTION, HISTORICAL_COLLECTION


@dataclass
class DocumentMetadata:
    chunk_id: str
    source_file: str
    source_type: str       # support_policy | sop | product_guide | customer_agreement | ticket
    status: str            # current | deprecated | historical
    authority: str         # customer_agreement | general_policy | product_docs | historical_context
    account_id: Optional[str]
    effective_date: Optional[str]
    end_date: Optional[str]
    section: Optional[str]
    collection: str        # current | historical


# Document registry with metadata
DOCUMENT_REGISTRY = {
    "01_Support_Policy_v3_CURRENT.pdf": {
        "source_type": "support_policy",
        "status": "current",
        "authority": "general_policy",
        "account_id": None,
        "effective_date": "2026-05-01",
        "end_date": None,
        "collection": "current",
    },
    "02_Support_Policy_v2_DEPRECATED.pdf": {
        "source_type": "support_policy",
        "status": "deprecated",
        "authority": "historical_context",
        "account_id": None,
        "effective_date": "2025-01-01",
        "end_date": "2026-05-01",
        "collection": "historical",
    },
    "03_Cancellation_and_Service_Credit_SOP_v4.pdf": {
        "source_type": "sop",
        "status": "current",
        "authority": "general_policy",
        "account_id": None,
        "effective_date": "2026-06-15",
        "end_date": None,
        "collection": "current",
    },
    "04_Product_Operations_Guide_and_Known_Issues.pdf": {
        "source_type": "product_guide",
        "status": "current",
        "authority": "product_docs",
        "account_id": None,
        "effective_date": "2026-08-14",
        "end_date": None,
        "collection": "current",
    },
    "05_Northstar_Logistics_Enterprise_Agreement.pdf": {
        "source_type": "customer_agreement",
        "status": "current",
        "authority": "customer_agreement",
        "account_id": "ACCT-001",
        "effective_date": "2026-01-01",
        "end_date": "2026-12-31",
        "collection": "current",
    },
    "06_LumenWorks_Service_Agreement.pdf": {
        "source_type": "customer_agreement",
        "status": "current",
        "authority": "customer_agreement",
        "account_id": "ACCT-002",
        "effective_date": "2026-03-01",
        "end_date": "2027-02-28",
        "collection": "current",
    },
}


def extract_pdf_text(pdf_path: Path) -> list[dict]:
    """Extract text from PDF, returning page-level chunks."""
    doc = fitz.open(str(pdf_path))
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text().strip()
        if text:
            pages.append({
                "page_num": i + 1,
                "text": text,
                "char_count": len(text),
            })
    doc.close()
    return pages


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    """Split text into overlapping chunks by character count."""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        # Try to break at a sentence or section boundary
        if end < len(text):
            # Look for last period or newline
            last_break = max(chunk.rfind(". "), chunk.rfind("\n"), chunk.rfind("●"))
            if last_break > chunk_size * 0.5:
                chunk = chunk[:last_break + 1]
                end = start + last_break + 1

        chunks.append(chunk.strip())
        start = end - overlap

    return [c for c in chunks if c]


def make_chunk_id(source_file: str, page_num: int, chunk_idx: int) -> str:
    """Generate deterministic chunk ID."""
    raw = f"{source_file}:p{page_num}:c{chunk_idx}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def validate_document(filename: str, text: str) -> dict:
    """Validate document identity during ingestion."""
    warnings = []

    # Check for identity mismatches
    if "northstar" in filename.lower() and "lumenworks" in text.lower()[:500]:
        warnings.append("DOCUMENT IDENTITY MISMATCH: Filename suggests Northstar but content mentions LumenWorks")
    if "lumenworks" in filename.lower() and "northstar" in text.lower()[:500]:
        warnings.append("DOCUMENT IDENTITY MISMATCH: Filename suggests LumenWorks but content mentions Northstar")

    return {
        "valid": len(warnings) == 0,
        "warnings": warnings,
    }


def ingest_documents():
    """Main document ingestion pipeline."""
    print("=" * 60)
    print("PDF -> ChromaDB INGESTION")
    print("=" * 60)

    # Initialize ChromaDB
    chroma_client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=ChromaSettings(anonymized_telemetry=False),
    )

    # Create/recreate collections
    try:
        chroma_client.delete_collection(CURRENT_COLLECTION)
    except Exception:
        pass
    try:
        chroma_client.delete_collection(HISTORICAL_COLLECTION)
    except Exception:
        pass

    current_col = chroma_client.create_collection(
        name=CURRENT_COLLECTION,
        metadata={"description": "Current authoritative documents"}
    )
    historical_col = chroma_client.create_collection(
        name=HISTORICAL_COLLECTION,
        metadata={"description": "Historical/context-only documents"}
    )

    all_chunks = []
    all_metadatas = []
    all_ids = []

    for filename, registry_info in DOCUMENT_REGISTRY.items():
        pdf_path = PDF_DIR / filename
        if not pdf_path.exists():
            print(f"  WARNING: {filename} not found, skipping")
            continue

        print(f"\nProcessing: {filename}")

        # Extract text
        pages = extract_pdf_text(pdf_path)
        full_text = "\n".join(p["text"] for p in pages)

        # Validate document identity
        validation = validate_document(filename, full_text)
        if not validation["valid"]:
            for w in validation["warnings"]:
                print(f"  ⚠ {w}")

        # Chunk text
        chunks = chunk_text(full_text)
        print(f"  Extracted {len(pages)} pages, {len(chunks)} chunks")

        # Create metadata for each chunk
        for idx, chunk in enumerate(chunks):
            chunk_id = make_chunk_id(filename, 1, idx)  # simplified page num
            metadata = DocumentMetadata(
                chunk_id=chunk_id,
                source_file=filename,
                source_type=registry_info["source_type"],
                status=registry_info["status"],
                authority=registry_info["authority"],
                account_id=registry_info["account_id"],
                effective_date=registry_info["effective_date"],
                end_date=registry_info["end_date"],
                section=None,
                collection=registry_info["collection"],
            )

            all_chunks.append(chunk)
            all_metadatas.append(asdict(metadata))
            all_ids.append(chunk_id)

    # Add to ChromaDB
    if all_chunks:
        # Split into current and historical
        current_ids = [all_ids[i] for i in range(len(all_ids)) if all_metadatas[i]["collection"] == "current"]
        current_chunks = [all_chunks[i] for i in range(len(all_chunks)) if all_metadatas[i]["collection"] == "current"]
        current_metas = [all_metadatas[i] for i in range(len(all_metadatas)) if all_metadatas[i]["collection"] == "current"]

        historical_ids = [all_ids[i] for i in range(len(all_ids)) if all_metadatas[i]["collection"] == "historical"]
        historical_chunks = [all_chunks[i] for i in range(len(all_chunks)) if all_metadatas[i]["collection"] == "historical"]
        historical_metas = [all_metadatas[i] for i in range(len(all_metadatas)) if all_metadatas[i]["collection"] == "historical"]

        # Clean metadata — ChromaDB doesn't accept None values
        def clean_meta(meta):
            return {k: (v if v is not None else "") for k, v in meta.items()}

        current_metas_clean = [clean_meta(m) for m in current_metas]
        historical_metas_clean = [clean_meta(m) for m in historical_metas]

        if current_chunks:
            current_col.add(
                documents=current_chunks,
                metadatas=current_metas_clean,
                ids=current_ids,
            )
            print(f"\n  Added {len(current_chunks)} chunks to CURRENT collection")

        if historical_chunks:
            historical_col.add(
                documents=historical_chunks,
                metadatas=historical_metas_clean,
                ids=historical_ids,
            )
            print(f"  Added {len(historical_chunks)} chunks to HISTORICAL collection")

    # Save metadata index
    metadata_path = CHROMA_DIR / "document_metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(all_metadatas, f, indent=2)

    print(f"\nTotal chunks indexed: {len(all_chunks)}")
    print(f"Metadata saved to: {metadata_path}")
    print("Document ingestion complete!")


if __name__ == "__main__":
    ingest_documents()
