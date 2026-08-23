"""ParcelPilot AI - Streamlit Chat Interface + Operations Dashboard."""
import sys
sys.path.insert(0, ".")

import streamlit as st
import json
from datetime import datetime

# Initialize database and data on first run
@st.cache_resource
def initialize_app():
    """Initialize database and ingest data if needed."""
    from app.data.database import init_db, get_session, Account
    from app.data.ingest_excel import run_ingestion
    
    # Initialize database tables
    init_db()
    
    # Check if data exists, if not ingest from Excel
    session = get_session()
    try:
        account_count = session.query(Account).count()
        if account_count == 0:
            run_ingestion()
    finally:
        session.close()
    
    return True

# Run initialization
initialize_app()

from app.agent.graph import ParcelPilotAgent
from app.data.access_control import UserContext

st.set_page_config(page_title="ParcelPilot AI Support", page_icon="📦", layout="wide")

if "agent" not in st.session_state:
    st.session_state.agent = ParcelPilotAgent()
if "messages" not in st.session_state:
    st.session_state.messages = []
if "user_ctx" not in st.session_state:
    st.session_state.user_ctx = None
if "pending_action" not in st.session_state:
    st.session_state.pending_action = None

# Sidebar
with st.sidebar:
    st.title("ParcelPilot AI")
    st.caption("Trustworthy Agentic Support")
    st.divider()
    st.subheader("User Context")

    role = st.selectbox("Role", ["customer", "support", "manager"],
        format_func=lambda x: {"customer": "Customer", "support": "Support Agent", "manager": "Operations Manager"}[x])

    if role == "customer":
        account = st.selectbox("Account", ["ACCT-001", "ACCT-002", "ACCT-003", "ACCT-004"],
            format_func=lambda x: {"ACCT-001": "Northstar Logistics", "ACCT-002": "LumenWorks",
                "ACCT-003": "Beacon Retail", "ACCT-004": "Axis Labs"}[x])
        user_id = f"{account.lower()}_user"
    else:
        account = None
        user_id = f"{role}_agent"

    st.session_state.user_ctx = UserContext(user_id=user_id, role=role, account_id=account)

    st.divider()
    st.markdown(f"**Role:** {role.title()}")
    if account:
        st.markdown(f"**Account:** {account}")

    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.session_state.pending_action = None
        st.rerun()

    # Suggested questions
    st.divider()
    st.subheader("Try These Questions")
    suggestions = {
        "customer": [
            "How many orders do I have?",
            "Show order ORD-1001",
            "Cancel order ORD-1001",
            "What are the SLA targets?",
            "Show my tickets",
            "Request service credit",
        ],
        "support": [
            "Show ticket TKT-501",
            "Classify severity for TKT-501",
            "Escalate ticket TKT-501",
            "Show all open tickets",
        ],
        "manager": [
            "How many orders for Northstar?",
            "Show all open tickets",
            "Approve service credit",
        ],
    }
    for q in suggestions.get(role, []):
        if st.button(q, key=f"suggest_{q}", use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": q})
            st.rerun()

    if st.session_state.pending_action:
        st.divider()
        st.warning("Pending Action - Confirmation Required")
        pa = st.session_state.pending_action
        details = pa.get("details", pa.get("confirmation_message", {}))

        # Display confirmation details nicely
        if isinstance(details, dict):
            if "order_id" in details:
                st.markdown(f"**Order:** {details['order_id']}")
                st.markdown(f"**Cancellation Fee:** {details.get('cancellation_fee', 'N/A')}")
                st.markdown(f"**Reason:** {details.get('reason', 'N/A')}")
            elif "ticket_id" in details:
                st.markdown(f"**Ticket:** {details['ticket_id']}")
                st.markdown(f"**Severity:** {details.get('severity', 'N/A')}")
                st.markdown(f"**Reason:** {details.get('reason', 'N/A')}")
            else:
                st.json(details)
        else:
            st.markdown(details)

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Yes, Confirm", type="primary", use_container_width=True):
                action_id = pa.get("action_id")
                if action_id:
                    result = st.session_state.agent.confirm_action(action_id, True)
                    st.session_state.messages.append({"role": "assistant", "content": result.get("message", "Action completed successfully!")})
                st.session_state.pending_action = None
                st.rerun()
        with c2:
            if st.button("No, Cancel", use_container_width=True):
                action_id = pa.get("action_id")
                if action_id:
                    st.session_state.agent.confirm_action(action_id, False)
                    st.session_state.messages.append({"role": "assistant", "content": "Action cancelled."})
                st.session_state.pending_action = None
                st.rerun()

# Tabs
tab_chat, tab_dashboard = st.tabs(["AI Support Chat", "Operations Dashboard"])

with tab_chat:
    st.header("ParcelPilot AI Support Agent")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("tool_activity"):
                with st.expander("Tool Activity", expanded=False):
                    for tool in msg["tool_activity"]:
                        st.markdown(f"- {tool}")
            if msg.get("sources"):
                with st.expander("Sources", expanded=False):
                    for src in msg["sources"]:
                        st.markdown(f"- {src}")
            if msg.get("gates"):
                with st.expander("Confidence Gates", expanded=False):
                    for gate in msg["gates"]:
                        status = "PASS" if gate.get("passed") else "FAIL"
                        st.markdown(f"- [{status}] {gate.get('gate', 'unknown')}")

    if prompt := st.chat_input("Ask ParcelPilot AI..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                result = st.session_state.agent.run(prompt, st.session_state.user_ctx)

            st.markdown(result["answer"])

            # Store proposed action for confirmation
            if result.get("proposed_action"):
                st.session_state.pending_action = result["proposed_action"]

            tool_activity = result.get("tools_called", [])
            sources = result.get("sources_cited", [])
            gates = result.get("confidence_gates", [])

            if tool_activity:
                with st.expander("Tool Activity", expanded=False):
                    for tool in tool_activity:
                        st.markdown(f"- {tool}")
            if sources:
                with st.expander("Sources", expanded=False):
                    for src in sources:
                        st.markdown(f"- {src}")
            if gates:
                with st.expander("Confidence Gates", expanded=False):
                    for gate in gates:
                        status = "PASS" if gate.get("passed") else "FAIL"
                        st.markdown(f"- [{status}] {gate.get('gate', 'unknown')}")

            auth = result.get("retrieved_docs", {})
            if auth and auth.get("authority"):
                with st.expander("Authority Resolution", expanded=False):
                    a = auth["authority"]
                    st.markdown(f"**Source:** {a.get('source_name', 'N/A')}")
                    st.markdown(f"**Type:** {a.get('source_type', 'N/A')}")
                    st.markdown(f"**Confidence:** {a.get('confidence', 'N/A')}")

            st.session_state.messages.append({
                "role": "assistant", "content": result["answer"],
                "tool_activity": tool_activity, "sources": sources, "gates": gates,
            })

with tab_dashboard:
    st.header("Operations Intelligence Dashboard")
    st.info("Dataset snapshot: 2026-08-16 11:00 IST")

    from app.data.database import get_session, Account, Order, Ticket
    from app.engine.policy_rules import classify_severity

    session = get_session()
    try:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Accounts", session.query(Account).count())
        with c2:
            st.metric("Orders", session.query(Order).count())
        with c3:
            st.metric("Tickets", session.query(Ticket).count())
        with c4:
            st.metric("Open Tickets", session.query(Ticket).filter(Ticket.status == "open").count())

        st.divider()
        st.subheader("Open Tickets")

        open_tickets = session.query(Ticket).filter(Ticket.status == "open").all()
        for t in open_tickets:
            acct = session.query(Account).filter(Account.account_id == t.account_id).first()
            acct_name = acct.account_name if acct else t.account_id
            severity = classify_severity(t.subject, t.description or "")
            severity_color = {"P1": "red", "P2": "orange", "P3": "blue"}.get(severity, "gray")

            with st.expander(f"[{severity}] {t.ticket_id}: {t.subject} ({acct_name})"):
                st.markdown(f"**Account:** {acct_name} ({t.account_id})")
                st.markdown(f"**Severity:** :{severity_color}[{severity}]")
                st.markdown(f"**Channel:** {t.channel}")
                st.markdown(f"**Assigned to:** {t.assigned_to}")
                st.markdown(f"**Created:** {t.created_at}")
                st.markdown(f"**Description:** {t.description}")

                # Check known issues
                desc_lower = (t.description or "").lower()
                if "bulk upload" in desc_lower or "csv" in desc_lower:
                    st.warning("Related to KI-208: Bulk Upload failures on large CSVs. Workaround: split files below 3,000 rows.")
                if "swiftship" in desc_lower and "booked" in desc_lower:
                    st.warning("Related to KI-211: SwiftShip pickup webhook delay up to 20 minutes.")
                if "api key" in desc_lower or "credential" in desc_lower or "security" in desc_lower:
                    st.error("Security incident - P1 priority. Escalate immediately.")

        st.divider()
        st.subheader("Order Overview")

        orders = session.query(Order).all()
        for o in orders:
            acct = session.query(Account).filter(Account.account_id == o.account_id).first()
            acct_name = acct.account_name if acct else o.account_id
            status_color = {"BOOKED": "blue", "PICKED_UP": "green", "DELIVERED": "darkgreen"}.get(o.status, "gray")

            with st.expander(f"{o.order_id}: {o.status} ({acct_name})"):
                st.markdown(f"**Account:** {acct_name}")
                st.markdown(f"**Carrier:** {o.carrier}")
                st.markdown(f"**Status:** :{status_color}[{o.status}]")
                st.markdown(f"**Fee:** INR {o.shipment_fee_inr}")
                st.markdown(f"**Booked:** {o.booked_at}")
                st.markdown(f"**Pickup Window:** {o.pickup_window_start} to {o.pickup_window_end}")
                if o.pickup_actual_at:
                    st.markdown(f"**Actual Pickup:** {o.pickup_actual_at}")
                if o.carrier_fault:
                    st.error("Carrier at fault")
                if o.customer_fault:
                    st.warning("Customer at fault")
                if o.notes:
                    st.caption(o.notes)

    finally:
        session.close()
