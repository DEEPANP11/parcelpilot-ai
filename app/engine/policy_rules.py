"""Deterministic policy rules engine. LLM never does calculations."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

SNAPSHOT_TIME = datetime(2026, 8, 16, 11, 0, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))


@dataclass
class CancellationResult:
    eligible: bool
    fee_inr: int
    reason: str
    source: str  # Which rule/agreement was applied
    requires_return_to_origin: bool = False


@dataclass
class ServiceCreditResult:
    eligible: bool
    credit_inr: int
    reason: str
    source: str
    requires_manager_approval: bool = False
    unknown_factors: list = None

    def __post_init__(self):
        if self.unknown_factors is None:
            self.unknown_factors = []


@dataclass
class SLATarget:
    p1_minutes: int
    p2_minutes: int
    p3_minutes: int
    source: str


def get_snapshot_time() -> datetime:
    """Return the dataset snapshot time."""
    return SNAPSHOT_TIME


def calculate_cancellation_fee(
    order_status: str,
    booked_at: str,
    has_agreement_waiver: bool,
    agreement_waives_all: bool = False,
) -> CancellationResult:
    """Calculate cancellation fee based on SOP + agreement overrides.

    Args:
        order_status: DRAFT / BOOKED / PICKED_UP / DELIVERED
        booked_at: ISO datetime string of when order was booked
        has_agreement_waiver: Whether customer agreement waives cancellation fee
        agreement_waives_all: Whether agreement waives fee for ALL BOOKED (e.g. Northstar)
    """
    snapshot = get_snapshot_time()

    if order_status == "DRAFT":
        return CancellationResult(
            eligible=True,
            fee_inr=0,
            reason="Draft orders can be cancelled with no fee.",
            source="cancellation_sop_v4",
        )

    if order_status == "PICKED_UP":
        return CancellationResult(
            eligible=False,
            fee_inr=0,
            reason="Picked-up orders cannot be cancelled. Use return-to-origin workflow.",
            source="cancellation_sop_v4",
            requires_return_to_origin=True,
        )

    if order_status == "DELIVERED":
        return CancellationResult(
            eligible=False,
            fee_inr=0,
            reason="Delivered orders cannot be cancelled.",
            source="cancellation_sop_v4",
        )

    # BOOKED status — check time and agreement
    if order_status == "BOOKED":
        booked_time = datetime.fromisoformat(booked_at)
        # Make naive datetimes timezone-aware (IST)
        if booked_time.tzinfo is None:
            booked_time = booked_time.replace(tzinfo=timezone(timedelta(hours=5, minutes=30)))
        elapsed = snapshot - booked_time
        elapsed_minutes = elapsed.total_seconds() / 60

        # Agreement override: waive all fees for BOOKED
        if has_agreement_waiver and agreement_waives_all:
            return CancellationResult(
                eligible=True,
                fee_inr=0,
                reason="Customer agreement waives cancellation fee for all BOOKED shipments before pickup.",
                source="customer_agreement",
            )

        # Within 30 minutes — no fee
        if elapsed_minutes <= 30:
            return CancellationResult(
                eligible=True,
                fee_inr=0,
                reason="Cancellation within 30 minutes of booking — no fee.",
                source="cancellation_sop_v4",
            )

        # After 30 minutes — fee applies
        if has_agreement_waiver:
            # Agreement waives fee but not "all" — check specific terms
            return CancellationResult(
                eligible=True,
                fee_inr=0,
                reason="Customer agreement waives the cancellation fee.",
                source="customer_agreement",
            )

        return CancellationResult(
            eligible=True,
            fee_inr=250,
            reason=f"Cancellation {int(elapsed_minutes)} minutes after booking (>{30} min). Standard fee: INR 250.",
            source="cancellation_sop_v4",
        )

    return CancellationResult(
        eligible=False,
        fee_inr=0,
        reason=f"Unknown order status: {order_status}",
        source="error",
    )


def calculate_service_credit(
    pickup_scheduled_end: str,
    pickup_actual_at: Optional[str],
    carrier_fault: bool,
    customer_fault: bool,
    shipment_fee_inr: int,
    agreement_credit_fixed: Optional[int] = None,
    agreement_delay_threshold_hours: Optional[float] = None,
    agreement_cap: Optional[int] = None,
    monthly_credit_used: int = 0,
) -> ServiceCreditResult:
    """Calculate service credit eligibility and amount.

    Args:
        pickup_scheduled_end: End of pickup window (ISO datetime)
        pickup_actual_at: Actual pickup time (ISO datetime or None)
        carrier_fault: Whether carrier is at fault
        customer_fault: Whether customer is at fault
        shipment_fee_inr: Shipment fee
        agreement_credit_fixed: Fixed credit amount from agreement (e.g. LumenWorks 300)
        agreement_delay_threshold_hours: Delay threshold from agreement (e.g. LumenWorks 4hr)
        agreement_cap: Monthly aggregate cap from agreement (e.g. Northstar 5000)
        monthly_credit_used: Credits already used this month
    """
    unknown_factors = []

    # Check for unknown factors
    if carrier_fault is None:
        unknown_factors.append("carrier_fault")
    if customer_fault is None:
        unknown_factors.append("customer_fault")
    if pickup_actual_at is None:
        unknown_factors.append("pickup_timing")

    if unknown_factors:
        return ServiceCreditResult(
            eligible=False,
            credit_inr=0,
            reason=f"Cannot determine eligibility: {', '.join(unknown_factors)} unknown. Do not promise credit.",
            source="cancellation_sop_v4",
            unknown_factors=unknown_factors,
        )

    # Customer fault disqualifies
    if customer_fault:
        return ServiceCreditResult(
            eligible=False,
            credit_inr=0,
            reason="Customer-caused issue — not eligible for service credit.",
            source="cancellation_sop_v4",
        )

    # Carrier not at fault
    if not carrier_fault:
        return ServiceCreditResult(
            eligible=False,
            credit_inr=0,
            reason="Carrier is not at fault — not eligible for service credit.",
            source="cancellation_sop_v4",
        )

    # Calculate delay
    snapshot = get_snapshot_time()
    scheduled_end = datetime.fromisoformat(pickup_scheduled_end)
    if scheduled_end.tzinfo is None:
        scheduled_end = scheduled_end.replace(tzinfo=timezone(timedelta(hours=5, minutes=30)))

    if pickup_actual_at:
        actual = datetime.fromisoformat(pickup_actual_at)
        if actual.tzinfo is None:
            actual = actual.replace(tzinfo=timezone(timedelta(hours=5, minutes=30)))
        delay_hours = (actual - scheduled_end).total_seconds() / 3600
    else:
        # Not picked up yet — use snapshot time
        delay_hours = (snapshot - scheduled_end).total_seconds() / 3600

    # Determine threshold
    threshold_hours = agreement_delay_threshold_hours if agreement_delay_threshold_hours else 2.0

    if delay_hours < threshold_hours:
        return ServiceCreditResult(
            eligible=False,
            credit_inr=0,
            reason=f"Delay of {delay_hours:.1f} hours is below the {threshold_hours}-hour threshold.",
            source="customer_agreement" if agreement_delay_threshold_hours else "cancellation_sop_v4",
        )

    # Calculate credit amount
    if agreement_credit_fixed:
        credit = agreement_credit_fixed
        source = "customer_agreement"
    else:
        credit = min(500, int(shipment_fee_inr * 0.10))
        source = "cancellation_sop_v4"

    # Check monthly cap
    if agreement_cap:
        remaining = agreement_cap - monthly_credit_used
        if credit > remaining:
            credit = remaining
            if credit <= 0:
                return ServiceCreditResult(
                    eligible=False,
                    credit_inr=0,
                    reason=f"Monthly aggregate cap of INR {agreement_cap} reached.",
                    source="customer_agreement",
                )

    # Check manager approval threshold
    requires_approval = credit > 1000

    return ServiceCreditResult(
        eligible=True,
        credit_inr=credit,
        reason=f"Eligible: {delay_hours:.1f}hr delay, carrier fault confirmed, credit = INR {credit}.",
        source=source,
        requires_manager_approval=requires_approval,
    )


def get_sla_targets(plan: str, has_agreement: bool = False,
                    agreement_p1: Optional[int] = None,
                    agreement_p2: Optional[int] = None,
                    agreement_p3: Optional[int] = None) -> SLATarget:
    """Get SLA targets based on plan and agreement.

    Args:
        plan: Enterprise / Growth / Standard
        has_agreement: Whether customer has a signed agreement
        agreement_p1: Custom P1 target in minutes (from agreement)
        agreement_p2: Custom P2 target in minutes
        agreement_p3: Custom P3 target in minutes
    """
    # Default targets (from Support Policy v3) in minutes
    defaults = {
        "Enterprise": {"p1": 30, "p2": 120, "p3": 480},  # 30min, 2hr, 8hr (1 business day)
        "Growth": {"p1": 120, "p2": 240, "p3": 960},     # 2hr, 4hr, 2 business days
        "Standard": {"p1": 240, "p2": 480, "p3": 960},   # 4hr, 1 business day, 2 business days
    }

    plan_defaults = defaults.get(plan, defaults["Standard"])

    if has_agreement and agreement_p1 is not None:
        return SLATarget(
            p1_minutes=agreement_p1,
            p2_minutes=agreement_p2 or plan_defaults["p2"],
            p3_minutes=agreement_p3 or plan_defaults["p3"],
            source="customer_agreement",
        )

    return SLATarget(
        p1_minutes=plan_defaults["p1"],
        p2_minutes=plan_defaults["p2"],
        p3_minutes=plan_defaults["p3"],
        source="support_policy_v3",
    )


def classify_severity(subject: str, description: str) -> str:
    """Classify ticket severity based on content.

    This is a deterministic classifier using keyword matching.
    Returns: P1 / P2 / P3
    """
    text = f"{subject} {description}".lower()

    # P1 indicators
    p1_keywords = [
        "outage", "down", "production down", "cannot create",
        "security", "credential", "api key", "breach", "exposure",
        "all users", "complete failure", "http 500",
    ]

    # P2 indicators
    p2_keywords = [
        "degraded", "unavailable", "not working", "fails",
        "intermittent", "slow", "partial", "feature",
    ]

    p1_score = sum(1 for kw in p1_keywords if kw in text)
    p2_score = sum(1 for kw in p2_keywords if kw in text)

    if p1_score >= 2:
        return "P1"
    elif p1_score >= 1 and "security" in text:
        return "P1"
    elif p2_score >= 2:
        return "P2"
    elif p1_score >= 1:
        return "P2"
    elif p2_score >= 1:
        return "P3"
    else:
        return "P3"


def check_sla_breach(
    ticket_created_at: str,
    severity: str,
    plan: str,
    has_agreement: bool = False,
    agreement_p1: Optional[int] = None,
    agreement_p2: Optional[int] = None,
    agreement_p3: Optional[int] = None,
) -> dict:
    """Check if SLA has been breached."""
    targets = get_sla_targets(plan, has_agreement, agreement_p1, agreement_p2, agreement_p3)

    target_map = {"P1": targets.p1_minutes, "P2": targets.p2_minutes, "P3": targets.p3_minutes}
    target_minutes = target_map.get(severity, targets.p3_minutes)

    created = datetime.fromisoformat(ticket_created_at)
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone(timedelta(hours=5, minutes=30)))
    snapshot = get_snapshot_time()
    elapsed_minutes = (snapshot - created).total_seconds() / 60

    breached = elapsed_minutes > target_minutes

    return {
        "breached": breached,
        "severity": severity,
        "target_minutes": target_minutes,
        "elapsed_minutes": round(elapsed_minutes, 1),
        "source": targets.source,
    }
