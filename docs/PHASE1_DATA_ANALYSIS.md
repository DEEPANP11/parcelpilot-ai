# Phase 1: Data Pack Analysis Report

## 1. Dataset Snapshot

| Field | Value |
|-------|-------|
| Snapshot Time | 2026-08-16 11:00 Asia/Kolkata |
| Currency | INR |
| Note | Synthetic dataset. Historical ticket resolutions may be incorrect. |

**CRITICAL**: All time-based calculations (SLA, cancellation windows, pickup delays) must use this snapshot time, NOT current system time.

---

## 2. Excel Workbook Structure

### 2.1 Accounts Sheet (4 records)

| Column | Type | Description |
|--------|------|-------------|
| account_id | str | Primary key (ACCT-001 to ACCT-004) |
| account_name | str | Company name |
| plan | str | Enterprise / Growth / Standard |
| status | str | All currently "active" |
| csm | str | Customer Success Manager name |
| contract_file | str | Filename of signed agreement (NaN if none) |
| premium_support | bool | Whether premium support is enabled |
| notes | str | Free-text notes |

**Records:**

| account_id | account_name | plan | csm | contract_file | premium_support |
|------------|-------------|------|-----|---------------|-----------------|
| ACCT-001 | Northstar Logistics | Enterprise | Priya Mehta | 05_Northstar...pdf | True |
| ACCT-002 | LumenWorks | Growth | Arjun Rao | 06_LumenWorks...pdf | False |
| ACCT-003 | Beacon Retail | Standard | Neha Kapoor | NaN (no contract) | False |
| ACCT-004 | Axis Labs | Enterprise | Priya Mehta | NaN (no contract) | False |

**Key observations:**
- ACCT-001 (Northstar): Enterprise + has custom agreement + premium support
- ACCT-002 (LumenWorks): Growth + has custom agreement + no premium
- ACCT-003 (Beacon): Standard + no agreement → standard policies apply
- ACCT-004 (Axis Labs): Enterprise + no agreement → standard Enterprise policy applies

### 2.2 Orders Sheet (6 records)

| Column | Type | Description |
|--------|------|-------------|
| order_id | str | Primary key (ORD-XXXX) |
| account_id | str | Foreign key to accounts |
| carrier | str | SwiftShip / BlueDart Pro / RoadRunner |
| status | str | BOOKED / PICKED_UP / DELIVERED |
| booked_at | datetime | When order was booked |
| pickup_window_start | datetime | Scheduled pickup window start |
| pickup_window_end | datetime | Scheduled pickup window end |
| pickup_actual_at | datetime | Actual pickup time (NaN if not picked up) |
| shipment_fee_inr | int | Shipment fee in INR |
| carrier_fault | bool | Whether carrier is at fault |
| customer_fault | bool | Whether customer is at fault |
| cancellation_requested_at | datetime | When cancellation was requested (NaN if none) |
| notes | str | Context notes |

**Records:**

| order_id | account | carrier | status | fee | carrier_fault | cancellation_requested | key_note |
|----------|---------|---------|--------|-----|---------------|----------------------|----------|
| ORD-1001 | ACCT-001 | SwiftShip | BOOKED | 4200 | False | 2026-08-16 11:00 | Not picked up, cancel requested |
| ORD-1002 | ACCT-001 | BlueDart Pro | PICKED_UP | 5100 | False | 2026-08-16 10:20 | Cancel requested AFTER pickup |
| ORD-2001 | ACCT-002 | SwiftShip | BOOKED | 1800 | False | 2026-08-16 10:15 | 75 min after booking, not picked up |
| ORD-2002 | ACCT-002 | RoadRunner | BOOKED | 2400 | True | NaN | Carrier missed pickup, fault admitted |
| ORD-3001 | ACCT-003 | RoadRunner | BOOKED | 1200 | False | 2026-08-16 10:40 | Within 30 min of booking |
| ORD-4001 | ACCT-004 | SwiftShip | DELIVERED | 3600 | False | NaN | Completed delivery |

**Key observations for testing:**
- ORD-1001: Northstar + BOOKED → should have NO cancellation fee (agreement override)
- ORD-1002: PICKED_UP → cannot cancel, must use return-to-origin
- ORD-2001: LumenWorks + BOOKED + 75 min → default SOP says INR 250 fee (no agreement override)
- ORD-2002: Carrier fault + BOOKED + pickup missed → potential service credit candidate
- ORD-3001: Beacon + BOOKED + within 30 min → NO cancellation fee (default SOP)
- ORD-4001: DELIVERED → cannot cancel

### 2.3 Tickets Sheet (7 records)

| Column | Type | Description |
|--------|------|-------------|
| ticket_id | str | Primary key (TKT-XXX) |
| account_id | str | Foreign key to accounts |
| created_at | datetime | When ticket was created |
| status | str | open / closed |
| subject | str | Ticket subject line |
| description | str | Full description |
| channel | str | email / chat |
| assigned_to | str | Agent name |
| last_customer_message_at | datetime | Last customer message time |
| historical_resolution | str | Past resolution text (NaN if open) |

**Records:**

| ticket_id | account | status | subject | severity暗示 | historical_resolution |
|-----------|---------|--------|---------|-------------|----------------------|
| TKT-501 | ACCT-001 | open | All shipment creation failing | P1 (production outage) | NaN |
| TKT-502 | ACCT-002 | open | Bulk upload fails 4,200-row CSV | P2 (feature degraded) | NaN |
| TKT-503 | ACCT-003 | open | How to change billing contact | P3 (how-to question) | NaN |
| TKT-504 | ACCT-001 | open | SwiftShip BOOKED after pickup | P2 (known issue KI-211) | NaN |
| TKT-505 | ACCT-004 | open | Possible API key exposure | P1 (security incident) | NaN |
| TKT-450 | ACCT-001 | closed | Cancellation fee after 30 min | Historical | "Agent told customer INR 250 fee applied" |
| TKT-451 | ACCT-002 | closed | Bulk upload fails large CSV | Historical | "Agent told customer Growth only supports 3,000 rows" |

**Key observations:**
- TKT-501: P1 candidate (complete production outage for Northstar)
- TKT-502: P2 candidate + relates to KI-208 (bulk upload known issue)
- TKT-503: P3 (simple how-to question)
- TKT-504: P2 + directly relates to KI-211 (SwiftShip webhook delay)
- TKT-505: P1 candidate (security incident - API key exposure)
- TKT-450: Historical resolution may be INCORRECT (Northstar agreement waives cancellation fee)
- TKT-451: Historical resolution may be INCORRECT (Growth supports 5,000 rows, not 3,000)

---

## 3. PDF Document Analysis

### 3.0 Document Identity Validation

| Filename | Expected Content | Actual Content | Match |
|----------|-----------------|----------------|-------|
| 01_Support_Policy_v3_CURRENT.pdf | Support Policy v3 | Support Policy v3 | MATCH |
| 02_Support_Policy_v2_DEPRECATED.pdf | Support Policy v2 | Support Policy v2 | MATCH |
| 03_Cancellation_and_Service_Credit_SOP_v4.pdf | Cancellation SOP v4 | Cancellation SOP v4 | MATCH |
| 04_Product_Operations_Guide_and_Known_Issues.pdf | Product Ops Guide | Product Ops Guide | MATCH |
| 05_Northstar_Logistics_Enterprise_Agreement.pdf | Northstar Agreement | Northstar Agreement | MATCH |
| 06_LumenWorks_Service_Agreement.pdf | LumenWorks Agreement | LumenWorks Agreement | MATCH |

All document identities validated. No mismatches found.

### 3.1 Support Policy v3 (CURRENT)

| Field | Value |
|-------|-------|
| Status | CURRENT |
| Effective | 1 May 2026 |
| Supersedes | Support Policy v2 |

**Source precedence rule (from document):**
1. Signed customer agreement (first)
2. Current support policy
3. Current product documentation
4. Historical tickets = context only, may contain incorrect guidance

**Severity definitions:**
- P1 Critical: Complete production outage, confirmed security incident, credential exposure, immediate material business risk with no workaround
- P2 High: Major feature unavailable/degraded, core operations possible or workaround exists
- P3 Normal: Minor defect, how-to question, configuration request, limited impact

**Default first-response targets:**

| Plan | P1 | P2 | P3 |
|------|----|----|-----|
| Enterprise | 30 min (24x7) | 2 hours | 1 business day |
| Growth | 2 business hours | 4 business hours | 2 business days |
| Standard | 4 business hours | 1 business day | 2 business days |

**Escalation rule:** P1 incidents escalated immediately. If response target breached, clearly state breach and recommend escalation.

### 3.2 Support Policy v2 (DEPRECATED)

| Field | Value |
|-------|-------|
| Status | DEPRECATED - DO NOT USE FOR CURRENT REQUESTS |
| Effective | 1 January 2025 |
| Superseded by | Support Policy v3 (1 May 2026) |

**Must NOT be used for current policy decisions.** Retained for historical reference only.

**Old targets (for reference only):**

| Plan | P1 | P2 | P3 |
|------|----|----|-----|
| Enterprise | 1 hour | 4 hours | 2 business days |
| Growth | 4 business hours | 1 business day | 3 business days |
| Standard | 8 business hours | 2 business days | 3 business days |

### 3.3 Cancellation & Service Credit SOP v4 (CURRENT)

| Field | Value |
|-------|-------|
| Status | CURRENT |
| Effective | 15 June 2026 |

**Order cancellation rules:**

| Status | Rule |
|--------|------|
| DRAFT | Cancel with no fee |
| BOOKED (not PICKED_UP) | No fee within 30 min. After 30 min: INR 250 unless agreement waives fee |
| PICKED_UP | Do not cancel. Use return-to-origin workflow |
| DELIVERED | Cannot be cancelled |

**Failed-pickup service credits:**
- Eligibility: pickup > 2 hours past window end + carrier fault + no customer fault
- Default credit: lower of INR 500 or 10% of shipment fee
- Agreement may replace: delay threshold, credit amount, or cap
- Credits > INR 1,000 require manager approval
- Do NOT promise credit when carrier fault, pickup timing, or customer fault is unknown

### 3.4 Product Operations Guide (CURRENT)

| Field | Value |
|-------|-------|
| Status | CURRENT |
| Updated | 14 August 2026 |

**Plan capabilities:**
- Bulk Upload: Growth + Enterprise only. Max 5,000 rows/CSV.
- Standard: No bulk upload.
- BOOKED = created, no pickup confirmation yet
- PICKED_UP = carrier pickup confirmed

**Known issues:**
- KI-208: Bulk upload failures on large CSVs (>3,000 rows). Status: Investigating. Workaround: split <3,000 rows.
- KI-211: SwiftShip pickup webhook delay up to 20 min. Status: Monitoring. BOOKED doesn't mean not picked up.
- KI-176: Address validation. Resolved 18 July 2026. Do not use for new incidents.

### 3.5 Northstar Logistics Enterprise Agreement

| Field | Value |
|-------|-------|
| Account | ACCT-001 |
| Customer | Northstar Logistics |
| Term | 1 Jan 2026 to 31 Dec 2026 |
| Status | ACTIVE |
| CSM | Priya Mehta |

**Custom terms (override defaults):**
- P1: 15 minutes (24x7) — vs default 30 min
- P2: 1 hour — vs default 2 hours
- P3: 8 business hours — vs default 1 business day
- Cancellation: ANY BOOKED shipment before pickup = NO FEE (overrides INR 250 default)
- Service credits: Monthly cap INR 5,000. Otherwise current SOP applies.

### 3.6 LumenWorks Service Agreement

| Field | Value |
|-------|-------|
| Account | ACCT-002 |
| Customer | LumenWorks |
| Plan | Growth |
| Term | 1 Mar 2026 to 28 Feb 2027 |
| Status | ACTIVE |

**Custom terms (override defaults):**
- P1: 2 business hours — vs default 2 business hours (same)
- P2: 4 business hours — vs default 4 business hours (same)
- P3: 2 business days — vs default 2 business days (same)
- No weekend/after-hours support
- Cancellation: NO special waiver. Standard SOP applies.
- Service credits: Fixed INR 300 if pickup > 4 hours past window + carrier fault + no customer fault. Replaces default credit rules.

---

## 4. Key Conflicts & Test Scenarios

### 4.1 Conflicts Identified

| Scenario | Default Rule | Agreement Override | Resolution |
|----------|-------------|-------------------|------------|
| Northstar cancellation (BOOKED, >30 min) | INR 250 fee | No fee (agreement) | Agreement wins |
| LumenWorks service credit | min(500, 10% fee) | Fixed INR 300, 4hr threshold | Agreement wins |
| Northstar P1 SLA | 30 minutes | 15 minutes | Agreement wins |
| TKT-450 historical resolution | Agent said INR 250 applies | Northstar has no-fee agreement | Historical resolution INCORRECT |
| TKT-451 historical resolution | Agent said 3,000 row limit | Product guide says 5,000 rows | Historical resolution INCORRECT |

### 4.2 Ready Test Scenarios

| ID | Question | Expected Behavior |
|----|----------|-------------------|
| T01 | Can Northstar cancel ORD-1001 without fee? | Yes — agreement waives fee for BOOKED |
| T02 | Can LumenWorks cancel ORD-2001 without fee? | No — 75 min elapsed, INR 250 fee applies (no waiver) |
| T03 | Can Beacon cancel ORD-3001 without fee? | Yes — within 30 min window |
| T04 | Should ORD-1002 be cancelled? | No — PICKED_UP, use return-to-origin |
| T05 | Should ORD-4001 be cancelled? | No — DELIVERED, cannot cancel |
| T06 | Is ORD-2002 eligible for service credit? | Check: carrier fault yes, pickup > 2hr past window? Calculate |
| T07 | What's Northstar's P1 SLA? | 15 minutes (agreement), not 30 min (policy) |
| T08 | What's Beacon's P1 SLA? | 4 business hours (standard policy, no agreement) |
| T09 | Is TKT-501 a P1? | Yes — complete production outage |
| T10 | Is TKT-505 a P1? | Yes — security incident (API key exposure) |
| T11 | What's causing TKT-502? | Likely KI-208 (bulk upload failures on large CSVs) |
| T12 | What's causing TKT-504? | KI-211 (SwiftShip webhook delay) |
| T13 | Was the resolution in TKT-450 correct? | No — Northstar agreement waives cancellation fee |
| T14 | Was the resolution in TKT-451 correct? | No — Growth supports 5,000 rows, not 3,000 |
| T15 | Can a customer see another customer's orders? | Access denied — enforced at DB layer |

---

## 5. Database Schema (Derived from Real Data)

### Table: accounts
```sql
CREATE TABLE accounts (
    account_id TEXT PRIMARY KEY,
    account_name TEXT NOT NULL,
    plan TEXT NOT NULL CHECK(plan IN ('Enterprise', 'Growth', 'Standard')),
    status TEXT NOT NULL DEFAULT 'active',
    csm TEXT,
    contract_file TEXT,
    premium_support BOOLEAN DEFAULT FALSE,
    notes TEXT
);
```

### Table: orders
```sql
CREATE TABLE orders (
    order_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(account_id),
    carrier TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('DRAFT', 'BOOKED', 'PICKED_UP', 'DELIVERED')),
    booked_at TEXT NOT NULL,
    pickup_window_start TEXT NOT NULL,
    pickup_window_end TEXT NOT NULL,
    pickup_actual_at TEXT,
    shipment_fee_inr INTEGER NOT NULL,
    carrier_fault BOOLEAN DEFAULT FALSE,
    customer_fault BOOLEAN DEFAULT FALSE,
    cancellation_requested_at TEXT,
    notes TEXT
);
```

### Table: tickets
```sql
CREATE TABLE tickets (
    ticket_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(account_id),
    created_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('open', 'closed')),
    subject TEXT NOT NULL,
    description TEXT,
    channel TEXT,
    assigned_to TEXT,
    last_customer_message_at TEXT,
    historical_resolution TEXT
);
```

### Table: escalations (for action tool)
```sql
CREATE TABLE escalations (
    escalation_id TEXT PRIMARY KEY,
    ticket_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    idempotency_key TEXT UNIQUE
);
```

### Table: audit_log
```sql
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    session_id TEXT,
    user_id TEXT,
    account_id TEXT,
    action TEXT NOT NULL,
    tool_calls TEXT,
    sources_consulted TEXT,
    confidence_gates TEXT,
    result TEXT,
    response_time_ms INTEGER
);
```

---

## 6. Document Metadata Schema

### For each chunk in ChromaDB:

```python
{
    "chunk_id": "policy_v3_sec2",
    "text": "...",
    "source_file": "01_Support_Policy_v3_CURRENT.pdf",
    "source_type": "support_policy",       # support_policy | sop | product_guide | customer_agreement | ticket
    "status": "current",                    # current | deprecated | historical
    "authority": "general_policy",          # customer_agreement | general_policy | product_docs | historical_context
    "account_id": null,                     # null for general, "ACCT-001" for customer-specific
    "effective_date": "2026-05-01",
    "end_date": null,                       # null if ongoing
    "section": "severity_definitions",
    "collection": "current"                 # current | historical
}
```

### Collection routing:

| Document | Collection | authority | status |
|----------|-----------|-----------|--------|
| Support Policy v3 | current | general_policy | current |
| Cancellation SOP v4 | current | general_policy | current |
| Product Ops Guide | current | product_docs | current |
| Northstar Agreement | current | customer_agreement | current |
| LumenWorks Agreement | current | customer_agreement | current |
| Support Policy v2 | historical | historical_context | deprecated |
| Closed tickets | historical | historical_context | historical |

---

## 7. Snapshot-Time Calculations

The dataset snapshot is **2026-08-16 11:00 Asia/Kolkata (IST)**.

All time-based calculations must use this as "now":

| Calculation | Example |
|-------------|---------|
| Time since booked | ORD-1001: booked 09:00, snapshot 11:00 = 2 hours elapsed |
| Pickup delay | ORD-2002: window_end 06:30, snapshot 11:00 = 4.5 hours past window |
| SLA elapsed | TKT-501: created 10:30, snapshot 11:00 = 30 min elapsed |
| Cancellation window | ORD-3001: booked 10:25, snapshot 11:00 = 35 min elapsed (>30 min) |

---

## 8. Historical Ticket Errors Found

These are intentional traps in the assessment data:

| Ticket | Agent Said | Actual Correct Answer | Error Type |
|--------|-----------|----------------------|------------|
| TKT-450 | INR 250 cancellation fee applies | Northstar agreement waives fee for BOOKED shipments | Agent didn't check customer agreement |
| TKT-451 | Growth only supports 3,000 rows | Growth supports 5,000 rows (KI-208 is a bug, not a limit) | Agent confused known issue with plan limit |

**Our system must NOT repeat these errors.** This is exactly the trust/reliability test.
