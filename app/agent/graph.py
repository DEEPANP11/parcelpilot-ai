"""LangGraph agent — orchestrates tools, reasoning, and response generation."""
import json
from typing import TypedDict, Annotated, Optional
from dataclasses import dataclass, asdict

from app.data.access_control import UserContext
from app.tools.document_search import DocumentSearchTool
from app.tools.data_lookup import DataLookupTool
from app.tools.actions import ActionTool
from app.engine.policy_rules import (
    calculate_cancellation_fee, calculate_service_credit,
    get_sla_targets, classify_severity, check_sla_breach, get_snapshot_time,
)
from app.engine.source_authority import resolve_authority


@dataclass
class AgentState:
    """State carried through the agent workflow."""
    user_query: str
    user_ctx: UserContext
    intent: str = ""
    entities: dict = None
    tools_called: list = None
    retrieved_docs: dict = None
    account_data: dict = None
    order_data: dict = None
    ticket_data: dict = None
    policy_result: dict = None
    authority_result: dict = None
    proposed_action: dict = None
    confirmation_required: bool = False
    final_answer: str = ""
    sources_cited: list = None
    confidence_gates: list = None
    error: str = ""

    def __post_init__(self):
        if self.entities is None:
            self.entities = {}
        if self.tools_called is None:
            self.tools_called = []
        if self.sources_cited is None:
            self.sources_cited = []
        if self.confidence_gates is None:
            self.confidence_gates = []


class ParcelPilotAgent:
    """Main agent that orchestrates the full workflow."""

    def __init__(self):
        self.doc_tool = DocumentSearchTool()
        self.data_tool = DataLookupTool()
        self.action_tool = ActionTool()

    def run(self, query: str, user_ctx: UserContext) -> dict:
        """Execute the full agent workflow.

        Args:
            query: User's natural language query
            user_ctx: Authenticated user context
        """
        state = AgentState(user_query=query, user_ctx=user_ctx)

        try:
            # Step 1: Classify intent
            state = self._classify_intent(state)
            if state.error:
                return self._format_response(state)

            # Step 2: Extract entities
            state = self._extract_entities(state)

            # Step 3: Gather evidence
            state = self._gather_evidence(state)

            # Step 4: Apply policy rules
            state = self._apply_policy_rules(state)

            # Step 5: Check evidence gates
            state = self._check_evidence_gates(state)

            # Step 6: Generate answer
            state = self._generate_answer(state)

            return self._format_response(state)

        except PermissionError as e:
            state.final_answer = f"Access denied: {str(e)}"
            state.confidence_gates.append({"gate": "access_control", "passed": False})
            return self._format_response(state)
        except Exception as e:
            if "Access denied" in str(e) or "unauthorized" in str(e).lower():
                state.error = str(e)
                state.final_answer = "Access denied. You are not authorized to access this data."
                state.confidence_gates.append({"gate": "access_control", "passed": False})
                return self._format_response(state)
            import traceback
            traceback.print_exc()
            state.error = str(e)
            state.final_answer = "I encountered an error processing your request. Please try again or contact support."
            return self._format_response(state)

    def _classify_intent(self, state: AgentState) -> AgentState:
        """Classify the user's intent from the query."""
        query_lower = state.user_query.lower()

        # Rule-based intent classification (deterministic)
        if any(w in query_lower for w in ["cancel", "cancellation"]):
            state.intent = "cancellation"
        elif any(w in query_lower for w in ["credit", "service credit", "compensation"]):
            state.intent = "service_credit"
        elif any(w in query_lower for w in ["sla", "response time", "response target", "p1", "p2", "p3"]):
            state.intent = "sla"
        elif any(w in query_lower for w in ["escalat", "priority", "urgent"]):
            state.intent = "escalation"
        elif any(w in query_lower for w in ["show", "find", "list", "get", "what is", "tell me"]):
            state.intent = "lookup"
        elif any(w in query_lower for w in ["known issue", "bug", "problem", "ki-"]):
            state.intent = "known_issue"
        elif any(w in query_lower for w in ["how do", "how to", "change", "update"]):
            state.intent = "how_to"
        else:
            state.intent = "general"

        state.tools_called.append("intent_classifier")
        return state

    def _extract_entities(self, state: AgentState) -> AgentState:
        """Extract entities (order IDs, account IDs, ticket IDs) from query."""
        import re
        query = state.user_query

        # Extract IDs
        order_match = re.search(r"ORD-\d+", query, re.IGNORECASE)
        if order_match:
            state.entities["order_id"] = order_match.group().upper()

        ticket_match = re.search(r"TKT-\d+", query, re.IGNORECASE)
        if ticket_match:
            state.entities["ticket_id"] = ticket_match.group().upper()

        account_match = re.search(r"ACCT-\d+", query, re.IGNORECASE)
        if account_match:
            state.entities["account_id"] = account_match.group().upper()

        # Extract company names — only set if not already the user's own account
        company_map = {
            "northstar": "ACCT-001",
            "lumenworks": "ACCT-002",
            "beacon": "ACCT-003",
            "axis": "ACCT-004",
        }
        query_lower = query.lower()
        user_account = state.user_ctx.account_id
        for name, acct_id in company_map.items():
            if name in query_lower:
                # Don't let user's own company override a previously extracted target
                if acct_id == user_account and "account_id" in state.entities:
                    continue
                state.entities["account_id"] = acct_id
                state.entities["company_name"] = name.title()

        # Use user context account if customer
        if state.user_ctx.role == "customer" and "account_id" not in state.entities:
            state.entities["account_id"] = state.user_ctx.account_id

        state.tools_called.append("entity_extractor")
        return state

    def _gather_evidence(self, state: AgentState) -> AgentState:
        """Gather evidence from all relevant tools."""
        account_id = state.entities.get("account_id")

        # ACCESS CONTROL: Check if customer is trying to access another account's data
        if state.user_ctx.role == "customer" and account_id:
            if account_id != state.user_ctx.account_id:
                state.error = f"Access denied: unauthorized to access account {account_id}"
                state.confidence_gates.append({"gate": "access_control", "passed": False})
                return state

        # 1. Look up structured data
        if "order_id" in state.entities:
            result = self.data_tool.run(
                "order", state.user_ctx,
                order_id=state.entities["order_id"],
            )
            state.order_data = result
            state.tools_called.append("data_lookup:order")
            # Use order's account_id if not already set
            if result.get("found") and not account_id:
                account_id = result["data"].get("account_id")
                state.entities["account_id"] = account_id

        if "ticket_id" in state.entities:
            result = self.data_tool.run(
                "ticket", state.user_ctx,
                ticket_id=state.entities["ticket_id"],
            )
            state.ticket_data = result
            state.tools_called.append("data_lookup:ticket")

        if account_id and "order_id" not in state.entities:
            result = self.data_tool.run(
                "account", state.user_ctx,
                account_id=account_id,
            )
            state.account_data = result
            state.tools_called.append("data_lookup:account")

        # 2. Search documents
        topic = state.intent
        doc_result = self.doc_tool.run(
            query=state.user_query,
            topic=topic,
            account_id=account_id,
        )
        state.retrieved_docs = doc_result
        state.tools_called.append("document_search")

        return state

    def _apply_policy_rules(self, state: AgentState) -> AgentState:
        """Apply deterministic policy rules."""
        account_id = state.entities.get("account_id")

        # Determine if customer has agreement
        has_agreement = False
        agreement_p1 = None
        agreement_p2 = None
        agreement_p3 = None
        agreement_waives_cancellation = False
        agreement_waives_all_booked = False
        agreement_credit_fixed = None
        agreement_delay_threshold = None
        agreement_credit_cap = None

        if account_id == "ACCT-001":  # Northstar
            has_agreement = True
            agreement_p1 = 15
            agreement_p2 = 60
            agreement_p3 = 480
            agreement_waives_all_booked = True
            agreement_credit_cap = 5000
        elif account_id == "ACCT-002":  # LumenWorks
            has_agreement = True
            agreement_credit_fixed = 300
            agreement_delay_threshold = 4.0

        # Cancellation logic
        if state.intent == "cancellation" and state.order_data and state.order_data.get("found"):
            order = state.order_data["data"]
            result = calculate_cancellation_fee(
                order_status=order["status"],
                booked_at=order["booked_at"],
                has_agreement_waiver=has_agreement and agreement_waives_all_booked,
                agreement_waives_all=agreement_waives_all_booked,
            )
            state.policy_result = {
                "type": "cancellation",
                "eligible": result.eligible,
                "fee_inr": result.fee_inr,
                "reason": result.reason,
                "source": result.source,
            }

        # Service credit logic
        elif state.intent == "service_credit" and state.order_data and state.order_data.get("found"):
            order = state.order_data["data"]
            result = calculate_service_credit(
                pickup_scheduled_end=order["pickup_window_end"],
                pickup_actual_at=order.get("pickup_actual_at"),
                carrier_fault=order["carrier_fault"],
                customer_fault=order["customer_fault"],
                shipment_fee_inr=order["shipment_fee_inr"],
                agreement_credit_fixed=agreement_credit_fixed,
                agreement_delay_threshold_hours=agreement_delay_threshold,
                agreement_cap=agreement_credit_cap,
            )
            state.policy_result = {
                "type": "service_credit",
                "eligible": result.eligible,
                "credit_inr": result.credit_inr,
                "reason": result.reason,
                "source": result.source,
                "requires_approval": result.requires_manager_approval,
            }

        # SLA logic
        elif state.intent == "sla":
            plan = None
            if state.account_data and state.account_data.get("found"):
                plan = state.account_data["data"].get("plan")
            elif account_id == "ACCT-001":
                plan = "Enterprise"
            elif account_id == "ACCT-002":
                plan = "Growth"
            elif account_id == "ACCT-003":
                plan = "Standard"
            elif account_id == "ACCT-004":
                plan = "Enterprise"

            if plan:
                targets = get_sla_targets(
                    plan=plan,
                    has_agreement=has_agreement,
                    agreement_p1=agreement_p1,
                    agreement_p2=agreement_p2,
                    agreement_p3=agreement_p3,
                )
                state.policy_result = {
                    "type": "sla",
                    "p1_minutes": targets.p1_minutes,
                    "p2_minutes": targets.p2_minutes,
                    "p3_minutes": targets.p3_minutes,
                    "source": targets.source,
                }

            # Check SLA breach for tickets
            if state.ticket_data and state.ticket_data.get("found"):
                ticket = state.ticket_data["data"]
                severity = classify_severity(ticket["subject"], ticket.get("description", ""))
                breach = check_sla_breach(
                    ticket_created_at=ticket["created_at"],
                    severity=severity,
                    plan=plan or "Standard",
                    has_agreement=has_agreement,
                    agreement_p1=agreement_p1,
                    agreement_p2=agreement_p2,
                    agreement_p3=agreement_p3,
                )
                state.policy_result["breach_check"] = breach
                state.policy_result["classified_severity"] = severity

        # Severity classification
        elif state.intent == "lookup" and state.ticket_data and state.ticket_data.get("found"):
            ticket = state.ticket_data["data"]
            severity = classify_severity(ticket["subject"], ticket.get("description", ""))
            state.policy_result = {
                "type": "severity",
                "classified_severity": severity,
            }

        state.tools_called.append("policy_rules_engine")
        return state

    def _check_evidence_gates(self, state: AgentState) -> AgentState:
        """Check evidence gates before giving definitive answer."""
        gates = []

        # Gate 1: Customer identified?
        gate1 = {"gate": "customer_identified", "passed": bool(state.entities.get("account_id"))}
        gates.append(gate1)

        # Gate 2: Record found?
        if state.order_data:
            gates.append({"gate": "order_found", "passed": state.order_data.get("found", False)})
        if state.ticket_data:
            gates.append({"gate": "ticket_found", "passed": state.ticket_data.get("found", False)})

        # Gate 3: Source found?
        if state.retrieved_docs:
            gates.append({"gate": "source_found", "passed": state.retrieved_docs.get("found", False)})
        else:
            gates.append({"gate": "source_found", "passed": False})

        # Gate 4: Authority resolved?
        if state.retrieved_docs and state.retrieved_docs.get("authority"):
            gates.append({"gate": "authority_resolved", "passed": True})

        # Gate 5: Policy applied?
        if state.policy_result:
            gates.append({"gate": "policy_applied", "passed": True})

        state.confidence_gates = gates
        return state

    def _generate_answer(self, state: AgentState) -> AgentState:
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
        return state
    def _format_response(self, state: AgentState) -> dict:
        """Format the final response."""
        # Determine if action is needed
        action_needed = state.intent == "escalation"

        return {
            "answer": state.final_answer,
            "intent": state.intent,
            "entities": state.entities,
            "tools_called": state.tools_called,
            "sources_cited": state.sources_cited,
            "confidence_gates": state.confidence_gates,
            "policy_result": state.policy_result,
            "retrieved_docs": {
                "authority": state.retrieved_docs.get("authority") if state.retrieved_docs else None,
                "conflicts": state.retrieved_docs.get("conflicts", []) if state.retrieved_docs else [],
            } if state.retrieved_docs else None,
            "action_needed": action_needed,
            "error": state.error,
        }

    def prepare_action(self, action_type: str, params: dict, user_ctx: UserContext) -> dict:
        """Prepare an action for confirmation."""
        return self.action_tool.prepare(action_type, params, user_ctx)

    def confirm_action(self, action_id: str, confirmed: bool) -> dict:
        """Confirm or cancel a prepared action."""
        return self.action_tool.confirm(action_id, confirmed)
