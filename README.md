# ParcelPilot AI — Trustworthy Agentic Support & Operations Platform

## What This Is

An AI-powered customer support agent for ParcelPilot, a B2B logistics platform. The system answers customer queries about orders, policies, cancellations, service credits, and SLAs using deterministic business rules, not just LLM-generated text.

## Architecture

```
User (Streamlit UI)
    ↓
FastAPI Backend (optional)
    ↓
LangGraph Agent
    ↓
┌───────────┬───────────┬───────────┐
│ Doc Search│ Data Tool │ Action Tool│
│ (BM25 +   │ (SQLite + │ (Prepare → │
│ ChromaDB) │ RBAC)     │ Confirm)   │
└───────────┴───────────┴───────────┘
    ↓
Evidence Collector
    ↓
┌───────────────┬───────────────┐
│ Source Auth   │ Policy Rules  │
│ Engine        │ Engine        │
└───────────────┴───────────────┘
    ↓
Conflict / Evidence Gates
    ↓
Answer OR Escalate
```

## Key Design Decisions

1. **LLM = language only.** Business logic runs in deterministic Python code.
2. **Source authority.** Customer agreements > current policy > product docs > historical context. Deprecated documents excluded.
3. **Two-layer security.** API auth context + DB-level filtering. Customers cannot see other accounts' data.
4. **Evidence gates.** Before answering, the system verifies: customer identified, record found, source found, authority resolved, policy applied.
5. **Hybrid retrieval.** BM25 (exact keyword match) + ChromaDB (semantic search) + BGE reranker.

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Ingest data
python -m app.data.ingest_excel
python -m app.rag.ingest_documents

# Run tests
python scripts/test_agent.py

# Run UI
streamlit run app/frontend/streamlit_app.py
```

## Project Structure

```
parcelpilot-ai/
├── app/
│   ├── agent/graph.py          # LangGraph agent
│   ├── tools/                  # 3 agent tools
│   │   ├── document_search.py  # RAG retrieval
│   │   ├── data_lookup.py      # SQLite queries
│   │   └── actions.py          # Escalation/update
│   ├── engine/
│   │   ├── policy_rules.py     # Deterministic rules
│   │   └── source_authority.py # Conflict resolution
│   ├── rag/
│   │   ├── retriever.py        # Hybrid BM25+ChromaDB
│   │   └── ingest_documents.py # PDF ingestion
│   ├── data/
│   │   ├── database.py         # SQLAlchemy schema
│   │   ├── ingest_excel.py     # Excel ingestion
│   │   └── access_control.py   # RBAC
│   └── frontend/
│       └── streamlit_app.py    # UI
├── data/                       # Ingested data
├── tests/
│   └── smoke_test_set.json     # 15 test cases
└── docs/
    └── PHASE1_DATA_ANALYSIS.md
```

## Test Results

All 10 smoke tests passing:
- Cancellation with agreement override ✅
- Cancellation with standard SOP ✅
- PICKED_UP/DELIVERED cannot cancel ✅
- SLA targets with agreement ✅
- SLA targets without agreement ✅
- Severity classification ✅
- Order listing ✅
- Access control ✅

## Dataset

- Snapshot: 2026-08-16 11:00 IST
- 4 accounts, 6 orders, 7 tickets
- 6 PDFs (policies, SOPs, agreements)
- Historical ticket resolutions may contain errors
