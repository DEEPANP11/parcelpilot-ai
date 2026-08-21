"""Fix the _generate_answer method in graph.py."""
import re

with open("app/agent/graph.py", "r", encoding="utf-8") as f:
    content = f.read()

# Find and replace the _generate_answer method
old_start = '    def _generate_answer(self, state: AgentState) -> AgentState:\n        """Generate the final answer based on gathered evidence."""'
new_start = '    def _generate_answer(self, state: AgentState) -> AgentState:\n        """Generate the final answer based on gathered evidence."""'

# Find the method boundaries
lines = content.split('\n')
start_idx = None
end_idx = None

for i, line in enumerate(lines):
    if 'def _generate_answer' in line:
        start_idx = i
    elif start_idx is not None and line.strip().startswith('def ') and not line.strip().startswith('def _generate_answer'):
        end_idx = i
        break

if start_idx is None:
    print("Method not found!")
    exit(1)

if end_idx is None:
    end_idx = len(lines)

print(f"Found method at lines {start_idx}-{end_idx}")

# Build new method
new_method_lines = '''    def _generate_answer(self, state: AgentState) -> AgentState:
        """Generate the final answer based on gathered evidence."""
        parts = []

        # Handle access denied
        if state.error and "Access denied" in state.error:
            state.final_answer = "Access denied. You are not authorized to access this data."
            return state

        # Add data context
        if state.order_data and state.order_data.get("found"):
            order = state.order_data["data"]
            parts.append(f"Order {order['order_id']} ({order['status']}) for account {order['account_id']}.")
            if order.get("carrier"):
                parts.append(f"Carrier: {order['carrier']}.")
            if order.get("shipment_fee_inr"):
                parts.append(f"Shipment fee: INR {order['shipment_fee_inr']}.")

        if state.ticket_data and state.ticket_data.get("found"):
            ticket = state.ticket_data["data"]
            parts.append(f"Ticket {ticket['ticket_id']}: {ticket['subject']} (status: {ticket['status']}).")
            if ticket.get("description"):
                parts.append(f"Description: {ticket['description'][:200]}.")

        # Add account context
        if state.account_data and state.account_data.get("found"):
            acct = state.account_data["data"]
            if state.intent == "lookup" and not state.order_data:
                parts.append(f"Account: {acct['account_name']} ({acct['plan']} plan).")

        # Handle orders list for lookup queries without specific IDs
        if state.intent == "lookup" and "order_id" not in state.entities and "ticket_id" not in state.entities:
            if state.account_data and state.account_data.get("found"):
                acct = state.account_data["data"]
                orders_result = self.data_tool.run(
                    "orders_by_account", state.user_ctx,
                    account_id=acct["account_id"],
                )
                if orders_result.get("found"):
                    parts.append(f"Orders for {acct['account_name']}:")
                    for o in orders_result["data"]:
                        parts.append(f"- {o['order_id']}: {o['status']} (INR {o['shipment_fee_inr']}, {o['carrier']})")

        # Add policy result
        if state.policy_result:
            pr = state.policy_result
            if pr["type"] == "cancellation":
                if pr["eligible"]:
                    if pr["fee_inr"] == 0:
                        parts.append(f"Yes. {pr['reason']}")
                    else:
                        parts.append(f"Cancellation is possible with a fee of INR {pr['fee_inr']}. {pr['reason']}")
                else:
                    parts.append(f"No. {pr['reason']}")

            elif pr["type"] == "service_credit":
                if pr["eligible"]:
                    parts.append(f"Eligible for service credit of INR {pr['credit_inr']}. {pr['reason']}")
                    if pr.get("requires_approval"):
                        parts.append("This credit requires manager approval (above INR 1,000).")
                else:
                    parts.append(f"Not eligible for service credit. {pr['reason']}")

            elif pr["type"] == "sla":
                acct_data = state.account_data["data"] if state.account_data and state.account_data.get("found") else {}
                plan = acct_data.get("plan", "Standard")
                parts.append(f"SLA targets for {plan} plan:")
                parts.append(f"P1: {pr['p1_minutes']} minutes, P2: {pr['p2_minutes']} minutes, P3: {pr['p3_minutes']} minutes.")
                if "breach_check" in pr:
                    bc = pr["breach_check"]
                    if bc["breached"]:
                        parts.append(f"SLA BREACHED: {bc['severity']} ticket exceeded {bc['target_minutes']}-minute target (elapsed: {bc['elapsed_minutes']} minutes).")
                    else:
                        parts.append(f"SLA within target: {bc['severity']} ({bc['elapsed_minutes']} min elapsed, target: {bc['target_minutes']} min).")
                if "classified_severity" in pr:
                    parts.append(f"Classified severity: {pr['classified_severity']}.")

            elif pr["type"] == "severity":
                sev = pr["classified_severity"]
                parts.append(f"Classified severity: {sev}.")
                if sev == "P1":
                    parts.append("This is a critical incident. P1 incidents should be escalated immediately.")
                elif sev == "P2":
                    parts.append("This is a high-severity issue requiring prompt attention.")

        # Add document context
        if state.retrieved_docs and state.retrieved_docs.get("found"):
            authority = state.retrieved_docs.get("authority", {})
            if authority:
                parts.append(f"Based on: {authority.get('source_name', 'documents')}.")

        # Collect sources
        if state.retrieved_docs and state.retrieved_docs.get("sources"):
            for s in state.retrieved_docs["sources"][:3]:
                src = s.get("source_file", "unknown")
                if src not in state.sources_cited:
                    state.sources_cited.append(src)

        # Handle empty case
        if not parts:
            if state.error:
                parts.append(f"Error: {state.error}")
            else:
                parts.append("I don't have enough information to answer that question. Could you provide more details or let me connect you with a support agent?")

        state.final_answer = " ".join(parts)
        return state'''

# Replace
lines[start_idx:end_idx] = new_method_lines.split('\n')
content = '\n'.join(lines)

with open("app/agent/graph.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Method replaced successfully!")
