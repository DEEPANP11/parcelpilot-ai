"""Ingest Excel data into SQLite database."""
import pandas as pd
from app.data.database import init_db, get_session, Account, Order, Ticket
from config.settings import EXCEL_DIR


def ingest_accounts(session, df):
    """Ingest accounts sheet."""
    for _, row in df.iterrows():
        account = Account(
            account_id=row["account_id"],
            account_name=row["account_name"],
            plan=row["plan"],
            status=row["status"],
            csm=row.get("csm"),
            contract_file=row.get("contract_file"),
            premium_support=bool(row.get("premium_support", False)),
            notes=row.get("notes"),
        )
        session.merge(account)
    session.commit()
    print(f"  Ingested {len(df)} accounts")


def ingest_orders(session, df):
    """Ingest orders sheet."""
    for _, row in df.iterrows():
        order = Order(
            order_id=row["order_id"],
            account_id=row["account_id"],
            carrier=row["carrier"],
            status=row["status"],
            booked_at=str(row["booked_at"]),
            pickup_window_start=str(row["pickup_window_start"]),
            pickup_window_end=str(row["pickup_window_end"]),
            pickup_actual_at=str(row.get("pickup_actual_at")) if pd.notna(row.get("pickup_actual_at")) else None,
            shipment_fee_inr=int(row["shipment_fee_inr"]),
            carrier_fault=bool(row.get("carrier_fault", False)),
            customer_fault=bool(row.get("customer_fault", False)),
            cancellation_requested_at=str(row["cancellation_requested_at"]) if pd.notna(row.get("cancellation_requested_at")) else None,
            notes=row.get("notes"),
        )
        session.merge(order)
    session.commit()
    print(f"  Ingested {len(df)} orders")


def ingest_tickets(session, df):
    """Ingest tickets sheet."""
    for _, row in df.iterrows():
        ticket = Ticket(
            ticket_id=row["ticket_id"],
            account_id=row["account_id"],
            created_at=str(row["created_at"]),
            status=row["status"],
            subject=row["subject"],
            description=row.get("description"),
            channel=row.get("channel"),
            assigned_to=row.get("assigned_to"),
            last_customer_message_at=str(row["last_customer_message_at"]) if pd.notna(row.get("last_customer_message_at")) else None,
            historical_resolution=row.get("historical_resolution"),
        )
        session.merge(ticket)
    session.commit()
    print(f"  Ingested {len(df)} tickets")


def run_ingestion():
    """Main ingestion pipeline."""
    print("=" * 60)
    print("EXCEL -> SQLite INGESTION")
    print("=" * 60)

    # Initialize database
    init_db()

    xlsx_path = EXCEL_DIR / "ParcelPilot_Assessment_Data.xlsx"
    xl = pd.ExcelFile(xlsx_path)

    session = get_session()
    try:
        # Clear existing data
        session.query(Ticket).delete()
        session.query(Order).delete()
        session.query(Account).delete()
        session.commit()

        # Ingest each sheet
        for sheet_name in xl.sheet_names:
            if sheet_name == "README":
                print(f"\nSkipping README sheet (metadata only)")
                continue

            df = pd.read_excel(xlsx_path, sheet_name=sheet_name)
            print(f"\nIngesting sheet: {sheet_name} ({len(df)} rows)")

            if sheet_name == "accounts":
                ingest_accounts(session, df)
            elif sheet_name == "orders":
                ingest_orders(session, df)
            elif sheet_name == "tickets":
                ingest_tickets(session, df)

        # Verify
        accounts = session.query(Account).count()
        orders = session.query(Order).count()
        tickets = session.query(Ticket).count()
        print(f"\nVerification: {accounts} accounts, {orders} orders, {tickets} tickets")
        print("Excel ingestion complete!")

    finally:
        session.close()


if __name__ == "__main__":
    run_ingestion()
