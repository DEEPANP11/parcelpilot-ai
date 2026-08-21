"""Source authority engine — resolves conflicts between documents."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class AuthorityResult:
    source_name: str
    source_type: str
    authority_level: int
    content: str
    confidence: str  # "high" | "medium" | "low"
    reasoning: str


# Topic-specific authority ordering
TOPIC_AUTHORITY = {
    "cancellation": ["customer_agreement", "sop", "support_policy", "product_guide"],
    "sla": ["customer_agreement", "support_policy", "product_guide"],
    "service_credit": ["customer_agreement", "sop", "support_policy"],
    "product_capability": ["customer_agreement", "product_guide"],
    "known_issue": ["product_guide"],
    "general": ["customer_agreement", "support_policy", "sop", "product_guide"],
}


def resolve_authority(
    topic: str,
    retrieved_sources: list[dict],
    account_id: Optional[str] = None,
) -> AuthorityResult:
    """Resolve which source takes authority for a given topic.

    Args:
        topic: The topic being queried (cancellation, sla, service_credit, etc.)
        retrieved_sources: List of retrieved document chunks with metadata
        account_id: Customer account ID (for agreement filtering)

    Returns:
        AuthorityResult with the winning source
    """
    authority_order = TOPIC_AUTHORITY.get(topic, TOPIC_AUTHORITY["general"])

    # Sort sources by authority
    scored = []
    for source in retrieved_sources:
        source_type = source.get("source_type", "unknown")
        status = source.get("status", "unknown")

        # Skip deprecated sources for authoritative answers
        if status == "deprecated":
            continue

        # Skip other customers' agreements
        if source_type == "customer_agreement":
            source_account = source.get("account_id")
            if source_account and source_account != account_id:
                continue

        # Score based on authority order
        try:
            score = authority_order.index(source_type)
        except ValueError:
            score = 99  # Unknown source type gets lowest priority

        scored.append((score, source))

    if not scored:
        return AuthorityResult(
            source_name="none",
            source_type="none",
            authority_level=99,
            content="",
            confidence="low",
            reasoning="No authoritative source found for this topic.",
        )

    # Pick the highest authority source
    scored.sort(key=lambda x: x[0])
    best_score, best_source = scored[0]

    confidence = "high" if best_score <= 1 else "medium" if best_score <= 2 else "low"

    return AuthorityResult(
        source_name=best_source.get("source_file", "unknown"),
        source_type=best_source.get("source_type", "unknown"),
        authority_level=best_score,
        content=best_source.get("text", ""),
        confidence=confidence,
        reasoning=f"Source '{best_source.get('source_type')}' selected from {len(retrieved_sources)} retrieved sources. Authority order: {authority_order}",
    )


def detect_conflicts(retrieved_sources: list[dict], topic: str) -> list[dict]:
    """Detect conflicts between retrieved sources."""
    conflicts = []

    # Group by source type
    by_type = {}
    for source in retrieved_sources:
        st = source.get("source_type", "unknown")
        if st not in by_type:
            by_type[st] = []
        by_type[st].append(source)

    # Check for conflicts between different source types
    source_types = list(by_type.keys())
    for i in range(len(source_types)):
        for j in range(i + 1, len(source_types)):
            type_a = source_types[i]
            type_b = source_types[j]

            # Check if these types might conflict on the topic
            if topic == "cancellation" and {type_a, type_b} == {"customer_agreement", "sop"}:
                conflicts.append({
                    "type_a": type_a,
                    "type_b": type_b,
                    "topic": topic,
                    "resolution": "customer_agreement takes precedence over sop",
                })

            if topic == "sla" and {type_a, type_b} == {"customer_agreement", "support_policy"}:
                conflicts.append({
                    "type_a": type_a,
                    "type_b": type_b,
                    "topic": topic,
                    "resolution": "customer_agreement takes precedence over support_policy",
                })

    return conflicts


def format_source_citation(authority: AuthorityResult) -> str:
    """Format a source citation for display."""
    return f"[Source: {authority.source_name} | Authority: {authority.source_type} | Confidence: {authority.confidence}]"
