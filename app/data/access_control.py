"""Data access layer with role-based access control."""
from dataclasses import dataclass
from typing import Optional
from app.data.database import get_session, Account, Order, Ticket


@dataclass
class UserContext:
    """Authenticated user context."""
    user_id: str
    role: str           # "customer" | "support" | "manager"
    account_id: Optional[str]  # Set for customer role


# Permission matrix
PERMISSIONS = {
    "customer": {
        "view_own_orders": True,
        "view_other_orders": False,
        "view_own_tickets": True,
        "view_other_tickets": False,
        "view_general_policy": True,
        "view_own_agreement": True,
        "view_other_agreement": False,
        "create_escalation": True,  # Can request
        "approve_credit_above_1000": False,
        "view_ops_dashboard": False,
    },
    "support": {
        "view_own_orders": True,
        "view_other_orders": True,  # Scoped
        "view_own_tickets": True,
        "view_other_tickets": True,  # Scoped
        "view_general_policy": True,
        "view_own_agreement": True,
        "view_other_agreement": True,  # Scoped
        "create_escalation": True,
        "approve_credit_above_1000": False,
        "view_ops_dashboard": True,
    },
    "manager": {
        "view_own_orders": True,
        "view_other_orders": True,
        "view_own_tickets": True,
        "view_other_tickets": True,
        "view_general_policy": True,
        "view_own_agreement": True,
        "view_other_agreement": True,
        "create_escalation": True,
        "approve_credit_above_1000": True,
        "view_ops_dashboard": True,
    },
}


def check_permission(user_ctx: UserContext, permission: str) -> bool:
    """Check if user has a specific permission."""
    role_perms = PERMISSIONS.get(user_ctx.role, {})
    return role_perms.get(permission, False)


def get_account(session, account_id: str, user_ctx: UserContext) -> Optional[Account]:
    """Get account with access control."""
    # Customers can only see their own account
    if user_ctx.role == "customer" and user_ctx.account_id != account_id:
        raise PermissionError(f"Unauthorized: cannot access account {account_id}")

    account = session.query(Account).filter(Account.account_id == account_id).first()
    return account


def get_order(session, order_id: str, user_ctx: UserContext) -> Optional[Order]:
    """Get order with access control."""
    order = session.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        return None

    # Customers can only see their own orders
    if user_ctx.role == "customer" and order.account_id != user_ctx.account_id:
        raise PermissionError(f"Unauthorized: cannot access order {order_id}")

    return order


def get_orders_by_account(session, account_id: str, user_ctx: UserContext) -> list[Order]:
    """Get all orders for an account with access control."""
    if user_ctx.role == "customer" and user_ctx.account_id != account_id:
        raise PermissionError(f"Unauthorized: cannot access orders for {account_id}")

    return session.query(Order).filter(Order.account_id == account_id).all()


def get_ticket(session, ticket_id: str, user_ctx: UserContext) -> Optional[Ticket]:
    """Get ticket with access control."""
    ticket = session.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if not ticket:
        return None

    # Customers can only see their own tickets
    if user_ctx.role == "customer" and ticket.account_id != user_ctx.account_id:
        raise PermissionError(f"Unauthorized: cannot access ticket {ticket_id}")

    return ticket


def get_tickets_by_account(session, account_id: str, user_ctx: UserContext) -> list[Ticket]:
    """Get all tickets for an account with access control."""
    if user_ctx.role == "customer" and user_ctx.account_id != account_id:
        raise PermissionError(f"Unauthorized: cannot access tickets for {account_id}")

    return session.query(Ticket).filter(Ticket.account_id == account_id).all()


def get_all_orders(session, user_ctx: UserContext) -> list[Order]:
    """Get all orders (internal use only)."""
    if user_ctx.role == "customer":
        raise PermissionError("Unauthorized: customers cannot list all orders")
    return session.query(Order).all()


def get_all_tickets(session, user_ctx: UserContext) -> list[Ticket]:
    """Get all tickets (internal use only)."""
    if user_ctx.role == "customer":
        raise PermissionError("Unauthorized: customers cannot list all tickets")
    return session.query(Ticket).all()


def search_orders(session, user_ctx: UserContext, **filters) -> list[Order]:
    """Search orders with access control."""
    query = session.query(Order)

    # Apply account filter for customers
    if user_ctx.role == "customer":
        query = query.filter(Order.account_id == user_ctx.account_id)

    # Apply additional filters
    for key, value in filters.items():
        if hasattr(Order, key) and value is not None:
            query = query.filter(getattr(Order, key) == value)

    return query.all()


def search_tickets(session, user_ctx: UserContext, **filters) -> list[Ticket]:
    """Search tickets with access control."""
    query = session.query(Ticket)

    # Apply account filter for customers
    if user_ctx.role == "customer":
        query = query.filter(Ticket.account_id == user_ctx.account_id)

    # Apply additional filters
    for key, value in filters.items():
        if hasattr(Ticket, key) and value is not None:
            query = query.filter(getattr(Ticket, key) == value)

    return query.all()
