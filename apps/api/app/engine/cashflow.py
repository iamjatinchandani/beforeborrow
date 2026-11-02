from datetime import date
from typing import Sequence
from dateutil.relativedelta import relativedelta

from app.engine.types import CashEvent, CashPath


def simulate(
    events: Sequence[CashEvent],
    opening_cash: int,
    reserve: int,
    start: date | None = None,
    end: date | None = None,
    pressure_threshold_paise: int | None = None,
    pressure_min_days: int = 7,
) -> CashPath:
    """
    Simulates a dated cash path from opening cash balance, reserve floor, and events ledger.

    Algorithm (Blueprint p. 22):
    1. Sorts events chronologically with conservative same-day rule (debit before credit).
    2. Updates cash balance after each event, retaining the intraday trough and trough date.
    3. Identifies first reserve breach date and first negative balance date.
    4. Generates a daily calendar trajectory of closing balances and reserve headroom.
    """
    opening_cash = int(opening_cash)
    reserve = int(reserve)

    if start is None:
        start = min((e.event_date for e in events), default=date.today())
    if end is None:
        end = max((e.event_date for e in events), default=start + relativedelta(days=180))

    if end < start:
        raise ValueError(f"End date {end} cannot precede start date {start}")

    # 1. Conservative same-day sort: debit (outflow, 0) before credit (inflow, 1)
    sorted_events = sorted(
        events,
        key=lambda e: (e.event_date, 0 if e.direction == "outflow" else 1, e.source_id),
    )

    # Group events by date
    events_by_date: dict[date, list[CashEvent]] = {}
    # Also collect any events strictly before start to adjust initial cash
    pre_start_events: list[CashEvent] = []

    for e in sorted_events:
        if e.event_date < start:
            pre_start_events.append(e)
        elif e.event_date <= end:
            events_by_date.setdefault(e.event_date, []).append(e)

    current_cash = opening_cash
    for e in pre_start_events:
        if e.direction == "outflow":
            current_cash -= e.amount_paise
        else:
            current_cash += e.amount_paise

    trough = current_cash
    trough_date = start
    first_reserve_breach: date | None = None
    first_negative: date | None = None

    if current_cash < reserve:
        first_reserve_breach = start
    if current_cash < 0:
        first_negative = start

    dates: list[date] = []
    balances: list[int] = []
    headrooms: list[int] = []

    # 2. Iterate daily from start to end
    curr_date = start
    while curr_date <= end:
        day_events = events_by_date.get(curr_date, [])
        for e in day_events:
            if e.direction == "outflow":
                current_cash -= e.amount_paise
            else:
                current_cash += e.amount_paise

            # Check intraday trough after each event
            if current_cash < trough:
                trough = current_cash
                trough_date = curr_date

            if current_cash < 0 and first_negative is None:
                first_negative = curr_date

            if current_cash < reserve and first_reserve_breach is None:
                first_reserve_breach = curr_date

        headroom = current_cash - reserve
        dates.append(curr_date)
        balances.append(current_cash)
        headrooms.append(headroom)

        curr_date += relativedelta(days=1)

    return CashPath(
        dates=dates,
        balances_paise=balances,
        headrooms_paise=headrooms,
        first_reserve_breach=first_reserve_breach,
        first_negative=first_negative,
        trough_paise=trough,
        trough_date=trough_date,
    )


def identify_pressure_windows(
    cash_path: CashPath,
    pressure_headroom_paise: int = 500_000,
    min_days: int = 7,
) -> list[tuple[date, date]]:
    """
    Finds contiguous periods of at least `min_days` where cash headroom drops below `pressure_headroom_paise`.
    """
    windows: list[tuple[date, date]] = []
    in_window = False
    win_start: date | None = None
    win_days = 0

    for d, hr in zip(cash_path.dates, cash_path.headrooms_paise):
        if hr <= pressure_headroom_paise:
            if not in_window:
                in_window = True
                win_start = d
                win_days = 1
            else:
                win_days += 1
        else:
            if in_window:
                if win_days >= min_days and win_start is not None:
                    prev_date = d - relativedelta(days=1)
                    windows.append((win_start, prev_date))
                in_window = False
                win_start = None
                win_days = 0

    if in_window and win_days >= min_days and win_start is not None:
        windows.append((win_start, cash_path.dates[-1]))

    return windows
