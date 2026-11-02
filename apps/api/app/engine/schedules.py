from datetime import date
from typing import Any, Sequence
from dateutil.relativedelta import relativedelta

from app.engine.types import AmortizationScheduleRow, CashEvent, FinancialSnapshot


def _get_field(obj: Any, name: str, default: Any = None) -> Any:
    """Helper to extract attribute or dict key seamlessly."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _to_date(val: Any) -> date | None:
    """Helper to parse a date object or ISO string."""
    if val is None:
        return None
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        return date.fromisoformat(val)
    return None


def expand_monthly_dates(anchor_date: date, count: int, end_date: date | None = None) -> list[date]:
    """
    Generates monthly recurring dates from anchor_date.
    Preserves anchor day of month with automatic end-of-month clamping (e.g. Jan 31 -> Feb 28/29 -> Mar 31).
    """
    dates: list[date] = []
    for i in range(count):
        d = anchor_date + relativedelta(months=i)
        if end_date and d > end_date:
            break
        dates.append(d)
    return dates


def expand_rules(snapshot: FinancialSnapshot, start: date, end: date) -> list[CashEvent]:
    """
    Expands income rules, expense rules, obligation payments, and protected goal transfers
    into a chronological list of CashEvent records between start and end dates.

    Applies the conservative same-day ordering rule: debit (outflow) before credit (inflow).
    Clamps monthly recurring dates correctly across February and leap years.
    """
    events: list[CashEvent] = []

    # 1. Expand income rules (direction: inflow)
    for rule in snapshot.income_rules or ():
        amt = int(_get_field(rule, "amount_paise", 0))
        if amt <= 0:
            continue

        base_date = _to_date(_get_field(rule, "due_date") or _get_field(rule, "start_date"))
        if not base_date:
            continue

        freq = str(_get_field(rule, "frequency", "once")).lower()
        rule_end = _to_date(_get_field(rule, "end_date"))
        cat = str(_get_field(rule, "category", "income"))
        source_id = str(_get_field(rule, "id", ""))
        timing = str(_get_field(rule, "timing", "known"))
        source = str(_get_field(rule, "source", "manual"))

        effective_end = min(end, rule_end) if rule_end else end

        if freq == "once":
            if start <= base_date <= effective_end:
                events.append(
                    CashEvent(
                        event_date=base_date,
                        amount_paise=amt,
                        category=cat,
                        source_id=source_id,
                        direction="inflow",
                        timing=timing,
                        source=source,
                        status="scheduled",
                    )
                )
        elif freq == "monthly":
            i = 0
            while True:
                d = base_date + relativedelta(months=i)
                if d > effective_end:
                    break
                if d >= start:
                    events.append(
                        CashEvent(
                            event_date=d,
                            amount_paise=amt,
                            category=cat,
                            source_id=source_id,
                            direction="inflow",
                            timing=timing,
                            source=source,
                            status="scheduled",
                        )
                    )
                i += 1
                if i > 1200:
                    break
        elif freq == "weekly":
            i = 0
            while True:
                d = base_date + relativedelta(weeks=i)
                if d > effective_end:
                    break
                if d >= start:
                    events.append(
                        CashEvent(
                            event_date=d,
                            amount_paise=amt,
                            category=cat,
                            source_id=source_id,
                            direction="inflow",
                            timing=timing,
                            source=source,
                            status="scheduled",
                        )
                    )
                i += 1
                if i > 5200:
                    break
        elif freq in ("biweekly", "fortnightly"):
            i = 0
            while True:
                d = base_date + relativedelta(weeks=2 * i)
                if d > effective_end:
                    break
                if d >= start:
                    events.append(
                        CashEvent(
                            event_date=d,
                            amount_paise=amt,
                            category=cat,
                            source_id=source_id,
                            direction="inflow",
                            timing=timing,
                            source=source,
                            status="scheduled",
                        )
                    )
                i += 1
                if i > 2600:
                    break

    # 2. Expand expense rules (direction: outflow)
    for rule in snapshot.expense_rules or ():
        amt = int(_get_field(rule, "amount_paise", 0))
        if amt <= 0:
            continue

        base_date = _to_date(_get_field(rule, "due_date") or _get_field(rule, "start_date"))
        if not base_date:
            continue

        freq = str(_get_field(rule, "frequency", "once")).lower()
        rule_end = _to_date(_get_field(rule, "end_date"))
        cat = str(_get_field(rule, "category", "expense"))
        source_id = str(_get_field(rule, "id", ""))
        timing = str(_get_field(rule, "timing", "known"))
        source = str(_get_field(rule, "source", "manual"))

        effective_end = min(end, rule_end) if rule_end else end

        if freq == "once":
            if start <= base_date <= effective_end:
                events.append(
                    CashEvent(
                        event_date=base_date,
                        amount_paise=amt,
                        category=cat,
                        source_id=source_id,
                        direction="outflow",
                        timing=timing,
                        source=source,
                        status="scheduled",
                    )
                )
        elif freq == "monthly":
            i = 0
            while True:
                d = base_date + relativedelta(months=i)
                if d > effective_end:
                    break
                if d >= start:
                    events.append(
                        CashEvent(
                            event_date=d,
                            amount_paise=amt,
                            category=cat,
                            source_id=source_id,
                            direction="outflow",
                            timing=timing,
                            source=source,
                            status="scheduled",
                        )
                    )
                i += 1
                if i > 1200:
                    break
        elif freq == "weekly":
            i = 0
            while True:
                d = base_date + relativedelta(weeks=i)
                if d > effective_end:
                    break
                if d >= start:
                    events.append(
                        CashEvent(
                            event_date=d,
                            amount_paise=amt,
                            category=cat,
                            source_id=source_id,
                            direction="outflow",
                            timing=timing,
                            source=source,
                            status="scheduled",
                        )
                    )
                i += 1
                if i > 5200:
                    break
        elif freq in ("biweekly", "fortnightly"):
            i = 0
            while True:
                d = base_date + relativedelta(weeks=2 * i)
                if d > effective_end:
                    break
                if d >= start:
                    events.append(
                        CashEvent(
                            event_date=d,
                            amount_paise=amt,
                            category=cat,
                            source_id=source_id,
                            direction="outflow",
                            timing=timing,
                            source=source,
                            status="scheduled",
                        )
                    )
                i += 1
                if i > 2600:
                    break

    # 3. Expand obligations (direction: outflow)
    for ob in snapshot.obligations or ():
        ob_id = str(_get_field(ob, "id", ""))
        kind = str(_get_field(ob, "kind", "other"))
        ob_source = str(_get_field(ob, "source", "manual"))
        payments = _get_field(ob, "payments", [])

        for p in payments:
            due_d = _to_date(_get_field(p, "due_date"))
            if not due_d:
                continue

            amt = int(_get_field(p, "amount_paise", 0))
            if amt <= 0:
                continue

            p_status = str(_get_field(p, "payment_status", "scheduled")).lower()
            p_id = str(_get_field(p, "id", ""))

            # Exclude already-paid entries only if opening balance reflects them (Blueprint p. 20)
            if p_status in ("paid", "completed") and due_d < snapshot.balance_as_of:
                continue

            if start <= due_d <= end:
                events.append(
                    CashEvent(
                        event_date=due_d,
                        amount_paise=amt,
                        category=f"debt_{kind}" if kind else "debt",
                        source_id=ob_id,
                        event_id=p_id,
                        direction="outflow",
                        timing="known",
                        source=ob_source,
                        status=p_status,
                    )
                )

    # 4. Expand protected goals (direction: outflow)
    # A protected transfer reserves funds; do not double-count if already linked to a cashflow rule.
    for goal in snapshot.goals or ():
        is_protected = bool(_get_field(goal, "protected", False))
        rule_id = _get_field(goal, "contribution_rule_id")
        target_d = _to_date(_get_field(goal, "target_date"))
        amt = int(_get_field(goal, "target_amount_paise", 0))

        if is_protected and not rule_id and target_d and amt > 0:
            if start <= target_d <= end:
                events.append(
                    CashEvent(
                        event_date=target_d,
                        amount_paise=amt,
                        category="goal_transfer",
                        source_id=str(_get_field(goal, "id", "")),
                        direction="outflow",
                        timing="known",
                        source="manual",
                        status="scheduled",
                    )
                )

    # 5. Sort events chronologically, with conservative same-day rule:
    # Debits (outflow, sort key 0) occur BEFORE credits (inflow, sort key 1).
    events.sort(key=lambda e: (e.event_date, 0 if e.direction == "outflow" else 1, e.source_id))

    return events


def validate_repayment_schedule(
    payments: Sequence[CashEvent | dict | tuple[date, int]],
) -> None:
    """
    Validates that:
    1. Repayment amounts are strictly positive.
    2. Repayment dates are non-decreasing / strictly chronological.
    Raises ValueError on violation.
    """
    if not payments:
        return

    extracted: list[tuple[date, int]] = []
    for item in payments:
        if isinstance(item, CashEvent):
            extracted.append((item.event_date, item.amount_paise))
        elif isinstance(item, dict):
            d = _to_date(item.get("due_date") or item.get("event_date") or item.get("date"))
            amt = int(item.get("amount_paise", 0))
            if d is None:
                raise ValueError("Schedule payment missing due_date")
            extracted.append((d, amt))
        elif isinstance(item, tuple) and len(item) == 2:
            extracted.append((_to_date(item[0]), int(item[1])))
        else:
            raise ValueError(f"Unsupported payment format: {item!r}")

    for idx, (d, amt) in enumerate(extracted):
        if amt <= 0:
            raise ValueError(f"Repayment amount must be positive, got {amt} at index {idx}")

        if idx > 0:
            prev_date = extracted[idx - 1][0]
            if d < prev_date:
                raise ValueError(
                    f"Repayment dates must be in chronological order: {prev_date} followed by {d}"
                )


def reconcile_schedule_balance(
    principal_paise: int,
    schedule: Sequence[AmortizationScheduleRow | CashEvent | int],
    is_zero_rate: bool = False,
) -> bool:
    """
    Validates that the final outstanding principal reconciles to zero.
    - If schedule contains AmortizationScheduleRow, checks that remaining_balance_paise == 0
      and total principal portions equal principal_paise.
    - If schedule is zero-rate installments (integers or CashEvents), checks sum(installments) == principal_paise.
    """
    if not schedule:
        return principal_paise == 0

    first = schedule[0]
    if isinstance(first, AmortizationScheduleRow):
        last_row: AmortizationScheduleRow = schedule[-1]  # type: ignore
        total_p = sum(r.principal_paise for r in schedule)  # type: ignore
        return last_row.remaining_balance_paise == 0 and total_p == principal_paise

    if is_zero_rate:
        if isinstance(first, CashEvent):
            total_amt = sum(e.amount_paise for e in schedule)  # type: ignore
        else:
            total_amt = sum(int(x) for x in schedule)  # type: ignore
        return total_amt == principal_paise

    return True
