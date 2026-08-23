"""SQLite database schema and session management."""
from sqlalchemy import (
    create_engine, Column, String, Integer, Boolean, Text,
    ForeignKey, DateTime, UniqueConstraint, Constraint
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from config.settings import DB_PATH, DATA_DIR

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Account(Base):
    __tablename__ = "accounts"

    account_id = Column(String, primary_key=True)
    account_name = Column(String, nullable=False)
    plan = Column(String, nullable=False)  # Enterprise / Growth / Standard
    status = Column(String, default="active")
    csm = Column(String)
    contract_file = Column(String)
    premium_support = Column(Boolean, default=False)
    notes = Column(Text)

    orders = relationship("Order", back_populates="account")
    tickets = relationship("Ticket", back_populates="account")


class Order(Base):
    __tablename__ = "orders"

    order_id = Column(String, primary_key=True)
    account_id = Column(String, ForeignKey("accounts.account_id"), nullable=False)
    carrier = Column(String, nullable=False)
    status = Column(String, nullable=False)  # DRAFT / BOOKED / PICKED_UP / DELIVERED
    booked_at = Column(String, nullable=False)
    pickup_window_start = Column(String, nullable=False)
    pickup_window_end = Column(String, nullable=False)
    pickup_actual_at = Column(String)
    shipment_fee_inr = Column(Integer, nullable=False)
    carrier_fault = Column(Boolean, default=False)
    customer_fault = Column(Boolean, default=False)
    cancellation_requested_at = Column(String)
    notes = Column(Text)

    account = relationship("Account", back_populates="orders")


class Ticket(Base):
    __tablename__ = "tickets"

    ticket_id = Column(String, primary_key=True)
    account_id = Column(String, ForeignKey("accounts.account_id"), nullable=False)
    created_at = Column(String, nullable=False)
    status = Column(String, nullable=False)  # open / closed
    subject = Column(String, nullable=False)
    description = Column(Text)
    channel = Column(String)
    assigned_to = Column(String)
    last_customer_message_at = Column(String)
    historical_resolution = Column(Text)

    account = relationship("Account", back_populates="tickets")


class Escalation(Base):
    __tablename__ = "escalations"

    escalation_id = Column(String, primary_key=True)
    ticket_id = Column(String, nullable=False)
    account_id = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    created_by = Column(String, nullable=False)
    created_at = Column(String, nullable=False)
    status = Column(String, default="active")
    idempotency_key = Column(String, unique=True)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(String, nullable=False)
    session_id = Column(String)
    user_id = Column(String)
    account_id = Column(String)
    action = Column(String, nullable=False)
    tool_calls = Column(Text)
    sources_consulted = Column(Text)
    result = Column(Text)
    response_time_ms = Column(Integer)


def init_db():
    """Create all tables."""
    Base.metadata.create_all(engine)
    print(f"Database initialized at {DB_PATH}")


def get_session():
    """Get a database session."""
    return SessionLocal()


if __name__ == "__main__":
    init_db()
