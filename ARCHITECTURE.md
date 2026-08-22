# Architecture Note — ParcelPilot AI Support Agent

## 1. Agent Design

### Approach: Deterministic Rules-Based Agent
I chose a **deterministic rules-based architecture** over an LLM-based agent for this assessment. The key reasoning:

- **Predictability**: Every response follows deterministic logic — no hallucinations, no inconsistent answers
- **Auditability**: Each decision path is traceable through intent classification → entity extraction → policy rules
- **Cost**: No API calls to external LLMs, runs entirely locally
- **Speed**: Sub-second responses, no waiting for LLM inference

### State Machine Flow
```
User Query
    ↓
┌─────────────────────────────────────────┐
│ Step 1: Intent Classification           │
│ - Keyword matching (regex/rule-based)   │
│ - Returns: lookup | cancellation |      │
│   service_credit | sla | escalation |   │
│   known_issue | how_to | general        │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ Step 2: Entity Extraction               │
│ - Regex for order IDs (ORD-XXXX)        │
│ - Regex for ticket IDs (TKT-XXX)        │
│ - Auto-inject account_id from user ctx  │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ Step 3: Evidence Gathering              │
│ - Access control check                  │
│ - Database lookups (order, ticket, acct)│
│ - Document retrieval (BM25 + Vector)    │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ Step 4: Policy Rules Engine             │
│ - Cancellation fee calculation          │
│ - Service credit eligibility            │
│ - SLA target lookup                     │
│ - Severity classification               │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ Step 5: Confidence Gates                │
│ - customer_identified                   │
│ - order/ticket_found                    │
│ - source_found                          │
│ - authority_resolved                    │
│ - policy_applied                        │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ Step 6: Answer Generation               │
│ - Assemble response from all evidence   │
│ - Add source citations                  │
│ - Propose actions if needed             │
└─────────────────────────────────────────┘
```

### User Contexts
The system supports three roles with different permissions:

| Role | Access | Capabilities |
|------|--------|--------------|
| Customer | Own account only | View orders/tickets, request cancellation, request credit |
| Support Agent | All accounts (scoped) | View any order/ticket, escalate, classify severity |
| Manager | Full access | Approve credits, view all data, manage escalations |

---

## 2. Tool Design

### Tool 1: Document Search (RAG)
```
HybridRetriever
├── BM25 Search (keyword matching)
│   - Fast, exact keyword matches
│   - Good for: "cancellation policy", "SLA P1"
│
├── ChromaDB Vector Search (semantic)
│   - Handles synonyms and meaning
│   - Good for: "what if pickup is late"
│
├── Merge & Deduplicate
│   - Combine results from both methods
│   - Remove duplicate chunks
│
└── BGE Reranker (cross-encoder)
    - Re-rank for relevance
    - Falls back to score-based if unavailable
```

### Tool 2: Structured Data Lookup
```
DataLookupTool
├── order(order_id)          → Single order details
├── orders_by_account(account_id)  → All orders for account
├── ticket(ticket_id)        → Single ticket details
├── tickets_by_account(account_id) → All tickets for account
└── account(account_id)      → Account details
```

**Access Control**: Each lookup checks user context:
- Customer: Can only access own account data
- Support/Manager: Can access any data

### Tool 3: State-Changing Actions
```
ActionTool
├── cancel_order    → Cancel shipment (with confirmation)
├── escalation      → Create escalation record (with confirmation)
├── ticket_update   → Update ticket status (with confirmation)
└── followup_task   → Create follow-up task (with confirmation)
```

**Confirmation Flow**:
1. User requests action
2. Agent prepares action details
3. System asks "Do you want to proceed?"
4. User confirms (Yes/No)
5. Action executed only after confirmation

---

## 3. Document and Structured-Data Handling

### Document Ingestion
```
PDF Files (6 documents)
    ↓
PyMuPDF (fitz) → Extract text per page
    ↓
Chunking (1000 chars, 200 overlap)
    ↓
Metadata Assignment
├── source_type: support_policy | sop | product_guide | customer_agreement
├── status: current | deprecated | historical
├── authority: customer_agreement | general_policy | product_docs | historical_context
├── account_id: ACCT-001 | ACCT-002 | "" (general)
└── effective_date / end_date
    ↓
ChromaDB Storage
├── Current Collection (active documents)
└── Historical Collection (deprecated documents)
```

### Structured Data (SQLite)
```
Excel → Pandas → SQLite
├── accounts (4 accounts)
├── orders (8 orders with status, carrier, fees)
├── tickets (6 tickets with status, severity)
├── escalations (created by actions)
└── audit_log (all actions logged)
```

### Multi-Step Request Example
**Query**: "Can Northstar cancel ORD-1001 without a cancellation fee?"

**Execution Path**:
1. **Intent**: classification → "cancellation"
2. **Entity extraction**: order_id = "ORD-1001", account_id = "ACCT-001"
3. **Data lookup**: Get order details (status=BOOKED, fee=4200)
4. **Document search**: Find Northstar agreement + cancellation policy
5. **Policy rules**: 
   - Check order status (BOOKED)
   - Check agreement (Northstar waives all BOOKED cancellations)
   - Calculate fee (INR 0)
6. **Answer**: "Yes. Customer agreement waives cancellation fee for all BOOKED shipments before pickup."

---

## 4. Source Reliability and Conflict Handling

### Document Authority Hierarchy
```
Priority 1: Customer Agreement (account-specific)
    - Overrides general policies
    - E.g., Northstar Enterprise Agreement

Priority 2: Current Support Policy
    - General rules applicable to all
    - E.g., Support Policy v3

Priority 3: Product Operations Guide
    - Known issues, product capabilities
    - E.g., Known Issues Catalog

Priority 4: Historical Context (deprecated)
    - Used only as reference
    - E.g., Support Policy v2 (deprecated)
```

### Conflict Resolution
1. **Customer agreement always wins**: If Northstar's agreement says "waives cancellation fee" but general policy says "INR 250 fee", we use the agreement
2. **Current over deprecated**: Support Policy v3 takes precedence over v2
3. **Explicit > implicit**: If a document explicitly states a rule, it overrides general defaults
4. **Cite sources**: Every answer includes "Based on: [source document]"

### Confidence Gates
Each response goes through 5 gates:
- `customer_identified`: Do we know who's asking?
- `order/ticket_found`: Did we find the requested data?
- `source_found`: Do we have relevant documents?
- `authority_resolved`: Can we determine which source is authoritative?
- `policy_applied`: Did we apply the correct policy rule?

---

## 5. Major Technical Trade-offs

| Decision | Choice | Reasoning |
|----------|--------|-----------|
| **Rules vs LLM** | Rules-based | Deterministic, no hallucinations, auditable, free |
| **Single vs Multi-agent** | Single agent with tools | Simpler architecture, all tools available to one agent |
| **SQLite vs PostgreSQL** | SQLite | Lightweight, no setup, sufficient for assessment |
| **ChromaDB vs Pinecone** | ChromaDB | Local, no API keys needed, free |
| **BM25 + Vector** | Hybrid search | Best of both: keywords + semantics |
| **Confirmation flow** | Before every action | Prevents accidental state changes |
| **Access control** | Data layer enforcement | Not just UI-level, actually enforced in tool calls |

### What I'd Do Differently with More Time
1. **Add LLM fallback**: For complex queries not matching rules, fallback to LLM
2. **Conversation memory**: Currently stateless, each query independent
3. **Streaming responses**: For better UX with long answers
4. **More sophisticated RAG**: Query expansion, hypothetical document embeddings
5. **Real authentication**: Currently mocked, would add OAuth/JWT
