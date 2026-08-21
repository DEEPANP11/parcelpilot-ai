"""Data lookup tool — queries accounts, orders, tickets with RBAC."""
from typing import Optional
from app.data.access_control import (
    UserContext, get_account, get_order, get_orders_by_account,
    get_ticket, get_tickets_by_account, search_orders, search_tickets,
)
from app.data.database import get_session


class DataLookupTool:
    """Tool for querying structured data with access control."""

    def __init__(self):
        pass

    def run(self, query_type: str, user_ctx: UserContext,
            **params) -> dict:
        """Query operational data.

        Args:
            query_type: Type of query (account, order, orders_by_account,
                       ticket, tickets_by_account, search_orders, search_tickets)
            user_ctx: Authenticated user context
            **params: Query parameters
        """
        session = get_session()
        try:
            if query_type == "account":
                return self._get_account(session, user_ctx, **params)
            elif query_type == "order":
                return self._get_order(session, user_ctx, **params)
            elif query_type == "orders_by_account":
                return self._get_orders_by_account(session, user_ctx, **params)
            elif query_type == "ticket":
                return self._get_ticket(session, user_ctx, **params)
            elif query_type == "tickets_by_account":
                return self._get_tickets_by_account(session, user_ctx, **params)
            elif query_type == "search_orders":
                return self._search_orders(session, user_ctx, **params)
            elif query_type == "search_tickets":
                return self._search_tickets(session, user_ctx, **params)
            else:
                return {"error": f"Unknown query type: {query_type}"}
        except PermissionError as e:
            return {"error": f"Access denied: {str(e)}", "access_denied": True}
        except Exception as e:
            return {"error": f"Query failed: {str(e)}"}
        finally:
            session.close()

    def _get_account(self, session, user_ctx, account_id=None):
        if not account_id:
            return {"error": "account_id required"}
        account = get_account(session, account_id, user_ctx)
        if not account:
            return {"found": False, "error": f"Account {account_id} not found"}
        return {
            "found": True,
            "data": {
                "account_id": account.account_id,
                "account_name": account.account_name,
                "plan": account.plan,
                "status": account.status,
                "csm": account.csm,
                "contract_file": account.contract_file,
                "premium_support": account.premium_support,
                "notes": account.notes,
            },
        }

    def _get_order(self, session, user_ctx, order_id=None):
        if not order_id:
            return {"error": "order_id required"}
        order = get_order(session, order_id, user_ctx)
        if not order:
            return {"found": False, "error": f"Order {order_id} not found"}
        return {
            "found": True,
            "data": {
                "order_id": order.order_id,
                "account_id": order.account_id,
                "carrier": order.carrier,
                "status": order.status,
                "booked_at": order.booked_at,
                "pickup_window_start": order.pickup_window_start,
                "pickup_window_end": order.pickup_window_end,
                "pickup_actual_at": order.pickup_actual_at,
                "shipment_fee_inr": order.shipment_fee_inr,
                "carrier_fault": order.carrier_fault,
                "customer_fault": order.customer_fault,
                "cancellation_requested_at": order.cancellation_requested_at,
                "notes": order.notes,
            },
        }

    def _get_orders_by_account(self, session, user_ctx, account_id=None):
        if not account_id:
            return {"error": "account_id required"}
        orders = get_orders_by_account(session, account_id, user_ctx)
        return {
            "found": len(orders) > 0,
            "data": [
                {
                    "order_id": o.order_id,
                    "carrier": o.carrier,
                    "status": o.status,
                    "shipment_fee_inr": o.shipment_fee_inr,
                    "booked_at": o.booked_at,
                }
                for o in orders
            ],
            "count": len(orders),
        }

    def _get_ticket(self, session, user_ctx, ticket_id=None):
        if not ticket_id:
            return {"error": "ticket_id required"}
        ticket = get_ticket(session, ticket_id, user_ctx)
        if not ticket:
            return {"found": False, "error": f"Ticket {ticket_id} not found"}
        return {
            "found": True,
            "data": {
                "ticket_id": ticket.ticket_id,
                "account_id": ticket.account_id,
                "created_at": ticket.created_at,
                "status": ticket.status,
                "subject": ticket.subject,
                "description": ticket.description,
                "channel": ticket.channel,
                "assigned_to": ticket.assigned_to,
                "last_customer_message_at": ticket.last_customer_message_at,
                "historical_resolution": ticket.historical_resolution,
            },
        }

    def _get_tickets_by_account(self, session, user_ctx, account_id=None):
        if not account_id:
            return {"error": "account_id required"}
        tickets = get_tickets_by_account(session, account_id, user_ctx)
        return {
            "found": len(tickets) > 0,
            "data": [
                {
                    "ticket_id": t.ticket_id,
                    "status": t.status,
                    "subject": t.subject,
                    "created_at": t.created_at,
                }
                for t in tickets
            ],
            "count": len(tickets),
        }

    def _search_orders(self, session, user_ctx, **kwargs):
        orders = search_orders(session, user_ctx, **kwargs)
        return {
            "found": len(orders) > 0,
            "data": [
                {
                    "order_id": o.order_id,
                    "account_id": o.account_id,
                    "carrier": o.carrier,
                    "status": o.status,
                    "shipment_fee_inr": o.shipment_fee_inr,
                }
                for o in orders
            ],
            "count": len(orders),
        }

    def _search_tickets(self, session, user_ctx, **kwargs):
        tickets = search_tickets(session, user_ctx, **kwargs)
        return {
            "found": len(tickets) > 0,
            "data": [
                {
                    "ticket_id": t.ticket_id,
                    "account_id": t.account_id,
                    "status": t.status,
                    "subject": t.subject,
                }
                for t in tickets
            ],
            "count": len(tickets),
        }
