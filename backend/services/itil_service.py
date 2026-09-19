"""
ITIL Priority Matrix Service for GEISER ITSM Helpdesk.
Determines TicketPriority based on orthogonal Impact and Urgency dimensions:
IMPACT × URGENCY → PRIORITY
"""
from typing import Union, Optional
from schemas.schemas import ImpactLevel, UrgencyLevel, TicketPriority


# ──────────────────────────────────────────────────────────────
# Centralized ITIL Priority Matrix (3×3)
# ──────────────────────────────────────────────────────────────
#                     URGENCY
#                 LOW      MEDIUM      HIGH
# IMPACT HIGH     HIGH     URGENT      URGENT
#        MEDIUM   MEDIUM   HIGH        URGENT
#        LOW      LOW      MEDIUM      HIGH
# ──────────────────────────────────────────────────────────────
ITIL_PRIORITY_MATRIX = {
    ImpactLevel.HIGH: {
        UrgencyLevel.HIGH: TicketPriority.URGENT,
        UrgencyLevel.MEDIUM: TicketPriority.URGENT,
        UrgencyLevel.LOW: TicketPriority.HIGH,
    },
    ImpactLevel.MEDIUM: {
        UrgencyLevel.HIGH: TicketPriority.URGENT,
        UrgencyLevel.MEDIUM: TicketPriority.HIGH,
        UrgencyLevel.LOW: TicketPriority.MEDIUM,
    },
    ImpactLevel.LOW: {
        UrgencyLevel.HIGH: TicketPriority.HIGH,
        UrgencyLevel.MEDIUM: TicketPriority.MEDIUM,
        UrgencyLevel.LOW: TicketPriority.LOW,
    },
}


def calculate_priority_from_impact_urgency(
    impact: Union[ImpactLevel, str, None],
    urgency: Union[UrgencyLevel, str, None]
) -> TicketPriority:
    """
    Computes ticket priority from impact and urgency using the centralized ITIL matrix.
    Raises ValueError with explanatory message if impact or urgency is missing or invalid.
    """
    if not impact or not urgency:
        raise ValueError("Both 'impact' and 'urgency' must be provided to compute ITIL priority.")

    impact_str = impact.value if hasattr(impact, "value") else str(impact).upper().strip()
    urgency_str = urgency.value if hasattr(urgency, "value") else str(urgency).upper().strip()

    try:
        impact_level = ImpactLevel(impact_str)
    except ValueError:
        raise ValueError(f"Invalid impact level: '{impact}'. Allowed values: {[e.value for e in ImpactLevel]}")

    try:
        urgency_level = UrgencyLevel(urgency_str)
    except ValueError:
        raise ValueError(f"Invalid urgency level: '{urgency}'. Allowed values: {[e.value for e in UrgencyLevel]}")

    return ITIL_PRIORITY_MATRIX[impact_level][urgency_level]
