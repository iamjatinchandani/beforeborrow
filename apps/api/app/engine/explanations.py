from datetime import date
from decimal import Decimal
from app.engine.types import OfferResult, ReasonEvidence


REASON_CODE_MESSAGES: dict[str, str] = {
    "insufficient_data": "Required data is missing; this comparison cannot be completed.",
    "funding_gap": "Usable credit and allowed savings do not cover the emergency expense.",
    "shortfall": "Cash balance would go below zero.",
    "reserve_breach": "Cash balance would fall below the reserve floor.",
    "stress_sensitive": "Cash buffer breached under pressure scenarios.",
    "within_stated_assumptions": "Cash remains at or above the reserve floor under stated assumptions.",
    "tight_pressure_window": "Cash headroom drops into pressure zone for consecutive days.",
}


def format_inr(amount_paise: int) -> str:
    """Formats integer paise into an Indian Rupee string (e.g. 500000 -> '₹5,000')."""
    is_neg = amount_paise < 0
    abs_rupees = abs(amount_paise) // 100
    s = str(abs_rupees)
    if len(s) > 3:
        last3 = s[-3:]
        rest = s[:-3]
        # Group in pairs for lakhs/crores
        groups = []
        while len(rest) > 2:
            groups.append(rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.append(rest)
        groups.reverse()
        formatted_num = ",".join(groups) + "," + last3
    else:
        formatted_num = s

    prefix = "-₹" if is_neg else "₹"
    return f"{prefix}{formatted_num}"


def format_date_human(d: date | None) -> str:
    """Formats YYYY-MM-DD into human-readable format like '3 Nov 2026'."""
    if d is None:
        return ""
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return f"{d.day} {months[d.month - 1]} {d.year}"


def explain(result: OfferResult, mode: str = "template") -> str:
    """
    Generates a pressure-aware explanation based on structured ReasonEvidence and reason codes.
    P0 strictly uses deterministic templates.
    """
    if mode != "template":
        raise NotImplementedError("LLM mode is P1 only")

    lines: list[str] = []

    # Check evidence for concrete details
    breach_ev = next((e for e in result.evidence if e.code in ("RESERVE_BREACH", "SHORTFALL")), None)
    if breach_ev and breach_ev.date:
        d_str = format_date_human(breach_ev.date)
        after_str = format_inr(breach_ev.after_paise)
        thresh_str = format_inr(breach_ev.threshold_paise)

        if breach_ev.code == "SHORTFALL":
            lines.append(f"• Cash drops below zero to {after_str} on {d_str}.")
        else:
            lines.append(f"• Cash falls to {after_str} on {d_str}, below your {thresh_str} reserve floor.")

    stress_ev = [e for e in result.evidence if e.code == "STRESS_RESERVE_BREACH"]
    for s in stress_ev:
        assumptions = ", ".join(s.assumptions)
        d_str = format_date_human(s.date) if s.date else "within horizon"
        lines.append(f"• Under stress ({assumptions}), a reserve breach occurs on {d_str}.")

    # Fallback to general reason code messages if no specific evidence lines
    if not lines:
        for code in result.reason_codes:
            msg = REASON_CODE_MESSAGES.get(code, code)
            lines.append(f"• {msg}")

    return "\n".join(lines) if lines else "Within stated assumptions."
