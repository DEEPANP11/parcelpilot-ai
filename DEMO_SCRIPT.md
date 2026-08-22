# Demo Script — ParcelPilot AI Support Agent (5 Minutes)

## Video Structure

### Part 1: Architecture Overview (1 minute)

**[0:00 - 0:15] Introduction**
"Hi, I'm [Your Name]. This is my submission for the ParcelPilot AI Agent Assessment. I built a customer support chatbot for ParcelPilot, a B2B logistics platform."

**[0:15 - 0:45] Architecture Diagram**
Show the architecture diagram (draw on whiteboard or use slides):

```
User Query
    ↓
Intent Classification (keyword matching)
    ↓
Entity Extraction (regex patterns)
    ↓
Evidence Gathering (database + documents)
    ↓
Policy Rules Engine (deterministic logic)
    ↓
Confidence Gates (validation)
    ↓
Answer Generation
```

"Key decisions:
1. I chose a rules-based approach over LLM for determinism and auditability
2. Hybrid RAG: BM25 keyword search + ChromaDB vector search
3. Three tools: document search, data lookup, state-changing actions
4. Access control enforced at the data layer"

**[0:45 - 1:00] Tech Stack**
"This is built with:
- Python + FastAPI backend
- Streamlit frontend
- SQLite database
- ChromaDB for vector search
- BM25 for keyword search
- No external LLM APIs"

---

### Part 2: Demo — Customer-Facing Chatbot (2 minutes)

**[1:00 - 1:30] Setup**
Switch to browser showing the app. Select "Customer" role, account "Northstar Logistics".

**[1:30 - 2:00] Query 1: Simple Lookup**
Type: `show order ORD-1001`

"Watch what happens:
1. System identifies intent as 'lookup'
2. Extracts order ID 'ORD-1001'
3. Checks access control (customer owns this order)
4. Looks up order from database
5. Returns order details with source citation"

Show the expandable sections: Tool Activity, Sources, Confidence Gates.

**[2:00 - 2:30] Query 2: Multi-Step Request**
Type: `Can Northstar cancel ORD-1001 without a cancellation fee?`

"This is a multi-step request:
1. System looks up order (status: BOOKED)
2. Finds Northstar's customer agreement
3. Applies policy rule: agreement waives cancellation fee for BOOKED orders
4. Answers: 'Yes. Customer agreement waives cancellation fee.'"

Show how the system combines database lookup + document search + policy rules.

**[2:30 - 3:00] Query 3: Confirmation Flow**
Type: `cancel order ORD-1001`

"Notice the confirmation flow:
1. System shows order details
2. Shows cancellation eligibility
3. Asks 'Do you want me to cancel?'
4. Shows confirmation buttons in sidebar
5. Only executes after user confirms"

Click "Yes, Confirm" to show the action being executed.

---

### Part 3: Demo — Access Control & Edge Cases (1 minute)

**[3:00 - 3:30] Access Control**
Keep Customer role. Type: `show order ORD-2001`

"Watch the access control:
1. Customer tries to access order ORD-2001 (belongs to LumenWorks)
2. System blocks access: 'Access denied'
3. This is enforced at the data layer, not just UI"

Switch to Manager role. Type: `show order ORD-2001`

"As a manager, I can access any order. Same query, different result."

**[3:30 - 4:00] Edge Cases**
Type: `cancel order` (no ID)

"System asks for clarification: 'Please provide the Order ID.'
It doesn't guess or make up an answer."

Type: `how many orders`

"System counts and lists all open orders for the account."

---

### Part 4: Demo — Operations Dashboard (30 seconds)

**[4:00 - 4:30] Operations Dashboard**
Click "Operations Dashboard" tab.

"For internal operations, I built a dashboard that shows:
1. Open tickets with severity classification (P1/P2/P3)
2. Pattern detection (tickets related to same issue)
3. SLA breach detection
4. Order overview with status"

Show the severity classification for a ticket.

---

### Part 5: Key Decisions & Conclusion (30 seconds)

**[4:30 - 5:00] Key Decisions**
"Why I made these choices:

1. **Rules over LLM**: Deterministic, no hallucinations, auditable for compliance
2. **Hybrid RAG**: Best of both worlds — keywords + semantics
3. **Access control in data layer**: Not just UI-level, actually enforced
4. **Confidence gates**: Validates every response before returning
5. **Source citations**: Every answer shows where it came from"

**[5:00] Conclusion**
"This covers the minimum requirements plus the additional client problems. The system handles natural language queries, enforces access control, uses three tools, requires confirmation before actions, and provides source citations. Thank you."

---

## Recording Tips

1. **Screen recording**: Use OBS Studio or Loom (free)
2. **Resolution**: 1080p minimum
3. **Audio**: Use a good microphone, speak clearly
4. **Pacing**: Practice beforehand, keep under 5 minutes
5. **Demo data**: Reset database before recording (run `python -m app.data.ingest_excel`)

## Pre-Recording Checklist

- [ ] Reset database: `python -m app.data.ingest_excel`
- [ ] Ingest documents: `python -m app.rag.ingest_documents`
- [ ] Clear browser history/cache
- [ ] Close unnecessary tabs/apps
- [ ] Test audio levels
- [ ] Have demo queries written down
- [ ] Restart the app: `python -m streamlit run app/frontend/streamlit_app.py`
