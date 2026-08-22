# Product Note — ParcelPilot AI Support Agent

## 1. Which Additional Problem I Addressed

I chose **Problem 2: Trust and Reliability** as the primary additional problem to address, with **Problem 1: Proactive Issue Detection** implemented in the Operations Dashboard.

### Problem 2: Trust and Reliability

**Why this matters**: A confidently incorrect answer would quickly reduce adoption. Support teams need to trust the system's recommendations.

**How I addressed it**:

1. **Source Citations**: Every answer includes "Based on: [document name]" so users know where the information came from

2. **Authority Hierarchy**: Customer-specific agreements override general policies
   - Example: Northstar's agreement waives cancellation fees, even though general policy charges INR 250
   - The system explicitly checks agreements first

3. **Confidence Gates**: Each response passes through 5 validation gates:
   - customer_identified: We know who's asking
   - order/ticket_found: We found the requested data
   - source_found: We have relevant documents
   - authority_resolved: We can determine which source is authoritative
   - policy_applied: We applied the correct policy rule

4. **Conflict Detection**: If sources disagree, the system flags it
   - Example: If deprecated policy conflicts with current policy, current wins
   - Example: If historical ticket resolution contradicts policy, policy wins

5. **When to Escalate**: The system knows its limits
   - Complex edge cases → escalate to human
   - Ambiguous requests → ask for clarification
   - Actions outside scope → require confirmation

### Problem 1: Proactive Issue Detection

**Implementation in Operations Dashboard**:

1. **Severity Classification**: Every ticket is classified as P1/P2/P3 using keyword matching
   - P1: "outage", "security", "all users", "HTTP 500"
   - P2: "degraded", "fails", "intermittent"
   - P3: Everything else

2. **Pattern Detection**: Dashboard highlights:
   - Multiple tickets from same account
   - Tickets related to known issues (KI-208, KI-211)
   - Security-related tickets (auto-escalate)

3. **SLA Breach Detection**: Shows which tickets are approaching or exceeding SLA targets

---

## 2. What Else I Would Build for ParcelPilot

### Priority 1: Conversation Memory (High Impact)
**Current limitation**: Each query is stateless — no conversation history.

**What I'd build**: 
- Store conversation context per session
- Allow follow-up questions: "What about the second one?"
- Reference previous answers: "You mentioned ORD-1001 earlier..."

**Why**: Most customer conversations are multi-turn. Without memory, users must repeat context.

### Priority 2: LLM Fallback for Edge Cases (High Impact)
**Current limitation**: Rules-based system can't handle unusual queries.

**What I'd build**:
- Detect when no rule matches
- Fallback to LLM (Ollama/GPT) with retrieved documents as context
- Generate natural language answers for complex questions

**Why**: Rules cover 80% of cases. LLM handles the remaining 20% of edge cases.

### Priority 3: Real-Time Carrier Integration (Medium Impact)
**Current limitation**: Service credit checks are based on static data.

**What I'd build**:
- API integration with carrier systems
- Real-time pickup status tracking
- Automatic service credit calculation when delay is detected

**Why**: Proactive credit issuance improves customer satisfaction.

### Priority 4: Customer Portal (Medium Impact)
**Current limitation**: Customers must contact support for everything.

**What I'd build**:
- Self-service portal for order tracking
- Automatic cancellation/refund requests
- SLA dashboard for enterprise customers

**Why**: Reduces support load, empowers customers.

### Priority 5: Analytics Dashboard (Low Impact)
**Current limitation**: No visibility into support trends.

**What I'd build**:
- Ticket volume trends
- Resolution time metrics
- Common issue categories
- Agent performance metrics

**Why**: Data-driven decisions for support team optimization.

---

## 3. What I Intentionally Left Out

| Item | Reason |
|------|--------|
| **LLM Integration** | Not required for assessment; rules-based is sufficient for demo |
| **Real Authentication** | Mocked for simplicity; would add OAuth/JWT in production |
| **Conversation History** | Stateless design simplifies demo; would add for production |
| **Streaming Responses** | Not needed for assessment; would add for better UX |
| **Unit Tests** | Assessment doesn't require; would add for production |
| **CI/CD Pipeline** | Assessment doesn't require; would add for production |
| **Docker Containerization** | Not required; would add for deployment |
| **Multi-language Support** | Assessment doesn't require; would add for global use |

---

## 4. One Metric to Judge Product Usefulness

### **First Contact Resolution Rate (FCR)**

**Definition**: Percentage of customer queries resolved without escalation to human agent.

**Why this metric**:
1. **Direct measure of agent capability**: If the agent can answer without escalation, it's working
2. **Customer satisfaction**: Faster resolution = happier customers
3. **Operational efficiency**: Lower FCR means less human workload
4. **Trust indicator**: High FCR means customers trust the agent

**Target**: 70% FCR within first month of deployment.

**How to measure**:
- Track all queries
- Count queries resolved directly by agent
- Count queries escalated to human
- FCR = (Resolved / Total) × 100

**Improvement levers**:
- Add more rules for edge cases
- Improve document coverage
- Add LLM fallback for complex queries
- Better entity extraction
