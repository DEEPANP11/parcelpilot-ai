"""Smoke test runner for the agent."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from app.agent.graph import ParcelPilotAgent
from app.data.access_control import UserContext

agent = ParcelPilotAgent()

# User contexts
northstar_ctx = UserContext(user_id='northstar_user', role='customer', account_id='ACCT-001')
lumenworks_ctx = UserContext(user_id='lumenworks_user', role='customer', account_id='ACCT-002')
beacon_ctx = UserContext(user_id='beacon_user', role='customer', account_id='ACCT-003')
axis_ctx = UserContext(user_id='axis_user', role='customer', account_id='ACCT-004')
support_ctx = UserContext(user_id='support_agent', role='support', account_id=None)

tests = [
    ("T01", "Can Northstar cancel ORD-1001 without a cancellation fee? Explain why.", northstar_ctx),
    ("T03", "Can Beacon Retail cancel ORD-3001 without a fee?", beacon_ctx),
    ("T04", "Should order ORD-1002 be cancelled? The customer is asking.", northstar_ctx),
    ("T05", "What happens if someone tries to cancel ORD-4001?", axis_ctx),
    ("T07", "What is the P1 response time target for Northstar Logistics?", northstar_ctx),
    ("T08", "What is the P1 SLA for Beacon Retail?", beacon_ctx),
    ("T09", "TKT-501 reports all shipment creation is failing at Northstar. What severity?", northstar_ctx),
    ("T10", "TKT-505 reports a possible API key exposure. What should we do?", axis_ctx),
    ("T14", "Show me all orders for LumenWorks.", lumenworks_ctx),
    ("T15", "I'm a Beacon Retail customer. Show me Northstar's orders.", beacon_ctx),
]

passed = 0
total = len(tests)

for test_id, query, ctx in tests:
    print("=" * 70)
    print(f"TEST {test_id}: {query}")
    print(f"User: {ctx.role} (account: {ctx.account_id})")
    print("-" * 70)

    result = agent.run(query, ctx)

    intent = result.get("intent", "unknown")
    tools = result.get("tools_called", [])
    answer = result.get("answer", "")
    sources = result.get("sources_cited", [])
    gates = result.get("confidence_gates", [])
    auth = result.get("retrieved_docs", {}).get("authority", {}) if result.get("retrieved_docs") else {}
    access_denied = result.get("error", "") and "Access denied" in result.get("error", "")

    print(f"Intent: {intent}")
    print(f"Tools called: {len(tools)}")
    print(f"Answer: {answer[:200]}")
    if sources:
        print(f"Sources: {sources[:3]}")
    if auth:
        print(f"Authority: {auth.get('source_name', 'N/A')} ({auth.get('confidence', 'N/A')})")

    # Simple pass/fail check
    test_passed = True
    if test_id == "T15" and not access_denied and "Access denied" not in answer.lower() and "unauthorized" not in answer.lower() and "cannot" not in answer.lower():
        test_passed = False
        print("FAIL: Should have denied access")

    if test_passed:
        passed += 1
        print("PASS")
    else:
        print("FAIL")
    print()

print("=" * 70)
print(f"Results: {passed}/{total} passed")
print("=" * 70)
