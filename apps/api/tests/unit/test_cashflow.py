from datetime import date
from app.engine.cashflow import identify_pressure_windows, simulate
from app.engine.types import CashEvent


def test_sameday_debit_before_credit():
    """
    On same date, debits (outflow) must be processed before credits (inflow).
    If cash is ₹1,000, debit is ₹1,500 and credit is ₹2,000 on the same date:
    - Intraday balance must drop to -₹500 (triggering negative).
    - Day-close balance will end at +₹1,500.
    """
    events = [
        # Inflow listed first in array to verify that sorting puts outflow first
        CashEvent(date=date(2026, 11, 5), amount_paise=200_000, category="salary", direction="inflow"),
        CashEvent(date=date(2026, 11, 5), amount_paise=150_000, category="bill", direction="outflow"),
    ]

    path = simulate(
        events=events,
        opening_cash=100_000,   # ₹1,000
        reserve=50_000,         # ₹500
        start=date(2026, 11, 1),
        end=date(2026, 11, 10),
    )

    # Intraday balance drops to 1,000 - 1,500 = -500
    assert path.trough_paise == -50_000
    assert path.trough_date == date(2026, 11, 5)
    assert path.first_negative == date(2026, 11, 5)
    assert path.first_reserve_breach == date(2026, 11, 5)

    # Day-close balance is 1,000 - 1,500 + 2,000 = +1,500
    idx = path.dates.index(date(2026, 11, 5))
    assert path.balances_paise[idx] == 150_000


def test_reserve_breach_without_negative():
    """
    Cash drops below reserve floor, but remains non-negative.
    """
    events = [
        CashEvent(date=date(2026, 11, 3), amount_paise=600_000, category="rent", direction="outflow"),
    ]

    path = simulate(
        events=events,
        opening_cash=1_000_000,  # ₹10,000
        reserve=500_000,         # ₹5,000
        start=date(2026, 11, 1),
        end=date(2026, 11, 10),
    )

    # Balance drops to 10,000 - 6,000 = 4,000 (breaches 5,000 reserve, but not negative)
    assert path.trough_paise == 400_000
    assert path.first_reserve_breach == date(2026, 11, 3)
    assert path.first_negative is None


def test_pressure_windows_detection():
    # Construct a 10-day path where headroom is <= 0 for 8 consecutive days
    dates = [date(2026, 11, 1) for _ in range(10)]
    from dateutil.relativedelta import relativedelta
    dates = [date(2026, 11, 1) + relativedelta(days=i) for i in range(10)]
    balances = [400_000] * 10
    headrooms = [-100_000] * 10

    from app.engine.types import CashPath
    path = CashPath(dates=dates, balances_paise=balances, headrooms_paise=headrooms)

    windows = identify_pressure_windows(path, pressure_headroom_paise=0, min_days=7)
    assert len(windows) == 1
    assert windows[0] == (date(2026, 11, 1), date(2026, 11, 10))
