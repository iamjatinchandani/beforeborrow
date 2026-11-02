from datetime import date
import pytest

from app.engine.cost import calculate_reducing_balance_schedule
from app.engine.schedules import (
    expand_monthly_dates,
    expand_rules,
    reconcile_schedule_balance,
    validate_repayment_schedule,
)
from app.engine.types import CashEvent, FinancialSnapshot


def test_expand_monthly_dates_leap_and_non_leap():
    # Non-leap year 2026
    dates_2026 = expand_monthly_dates(date(2026, 1, 31), 3)
    assert dates_2026 == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31)]

    # Leap year 2024
    dates_2024 = expand_monthly_dates(date(2024, 1, 31), 3)
    assert dates_2024 == [date(2024, 1, 31), date(2024, 2, 29), date(2024, 3, 31)]


def test_expand_rules_income_and_expenses():
    snapshot = FinancialSnapshot(
        opening_cash_paise=10_000_000,
        balance_as_of=date(2026, 1, 1),
        reserve_floor_paise=1_000_000,
        income_rules=(
            {
                "id": "inc-salary",
                "category": "salary",
                "amount_paise": 5_000_000,
                "due_date": "2026-01-05",
                "frequency": "monthly",
            },
            {
                "id": "inc-bonus",
                "category": "bonus",
                "amount_paise": 1_000_000,
                "due_date": "2026-02-15",
                "frequency": "once",
            },
        ),
        expense_rules=(
            {
                "id": "exp-rent",
                "category": "rent",
                "amount_paise": 2_000_000,
                "due_date": "2026-01-31",
                "frequency": "monthly",
            },
        ),
        obligations=(),
        goals=(),
        data_version=1,
    )

    events = expand_rules(snapshot, start=date(2026, 1, 1), end=date(2026, 3, 31))

    # Should have:
    # 2026-01-05: salary (+50k)
    # 2026-01-31: rent (-20k)
    # 2026-02-05: salary (+50k)
    # 2026-02-15: bonus (+10k)
    # 2026-02-28: rent (-20k, clamped from Jan 31)
    # 2026-03-05: salary (+50k)
    # 2026-03-31: rent (-20k, restored to 31st)
    assert len(events) == 7

    rent_feb = [e for e in events if e.category == "rent" and e.event_date.month == 2][0]
    assert rent_feb.event_date == date(2026, 2, 28)

    rent_mar = [e for e in events if e.category == "rent" and e.event_date.month == 3][0]
    assert rent_mar.event_date == date(2026, 3, 31)


def test_expand_rules_obligations_and_past_paid():
    snapshot = FinancialSnapshot(
        opening_cash_paise=5_000_000,
        balance_as_of=date(2026, 11, 1),
        reserve_floor_paise=500_000,
        income_rules=(),
        expense_rules=(),
        obligations=(
            {
                "id": "loan-1",
                "kind": "term_loan",
                "payments": [
                    # Paid before balance_as_of -> must be excluded
                    {
                        "id": "p-past",
                        "due_date": "2026-10-05",
                        "amount_paise": 400_000,
                        "payment_status": "paid",
                    },
                    # Scheduled after balance_as_of -> must be included
                    {
                        "id": "p-current",
                        "due_date": "2026-11-05",
                        "amount_paise": 400_000,
                        "payment_status": "scheduled",
                    },
                ],
            },
        ),
        goals=(),
        data_version=1,
    )

    events = expand_rules(snapshot, start=date(2026, 10, 1), end=date(2026, 12, 31))
    assert len(events) == 1
    assert events[0].event_id == "p-current"
    assert events[0].event_date == date(2026, 11, 5)
    assert events[0].direction == "outflow"


def test_expand_rules_protected_goals():
    snapshot = FinancialSnapshot(
        opening_cash_paise=5_000_000,
        balance_as_of=date(2026, 11, 1),
        reserve_floor_paise=500_000,
        income_rules=(),
        expense_rules=(),
        obligations=(),
        goals=(
            # Protected goal with target date -> creates goal_transfer event
            {
                "id": "goal-emergency",
                "label": "Emergency Fund",
                "target_amount_paise": 1_000_000,
                "target_date": "2026-11-15",
                "protected": True,
                "contribution_rule_id": None,
            },
            # Goal already linked to a contribution rule -> avoids double counting
            {
                "id": "goal-linked",
                "label": "Vacation Fund",
                "target_amount_paise": 500_000,
                "target_date": "2026-11-20",
                "protected": True,
                "contribution_rule_id": "rule-already-counted",
            },
        ),
        data_version=1,
    )

    events = expand_rules(snapshot, start=date(2026, 11, 1), end=date(2026, 11, 30))
    assert len(events) == 1
    assert events[0].category == "goal_transfer"
    assert events[0].amount_paise == 1_000_000
    assert events[0].event_date == date(2026, 11, 15)


def test_conservative_same_day_ordering():
    """
    Blueprint rule (p. 22):
    "Sort by date; if time unknown, debit before credit that day."
    """
    snapshot = FinancialSnapshot(
        opening_cash_paise=1_000_000,
        balance_as_of=date(2026, 11, 1),
        reserve_floor_paise=500_000,
        income_rules=(
            {
                "id": "inc-1",
                "amount_paise": 5_000_000,
                "due_date": "2026-11-05",
                "frequency": "once",
            },
        ),
        expense_rules=(
            {
                "id": "exp-1",
                "amount_paise": 2_000_000,
                "due_date": "2026-11-05",
                "frequency": "once",
            },
        ),
        obligations=(),
        goals=(),
        data_version=1,
    )

    events = expand_rules(snapshot, start=date(2026, 11, 1), end=date(2026, 11, 30))
    assert len(events) == 2
    assert events[0].event_date == date(2026, 11, 5)
    assert events[1].event_date == date(2026, 11, 5)
    # Debit (outflow) must come before credit (inflow)
    assert events[0].direction == "outflow"
    assert events[1].direction == "inflow"


def test_validate_repayment_schedule_valid():
    valid_payments = [
        {"due_date": "2026-11-01", "amount_paise": 600_000},
        {"due_date": "2026-11-15", "amount_paise": 600_000},
        {"due_date": "2026-12-01", "amount_paise": 600_000},
    ]
    validate_repayment_schedule(valid_payments)


def test_validate_repayment_schedule_non_positive():
    invalid_payments = [
        {"due_date": "2026-11-01", "amount_paise": 600_000},
        {"due_date": "2026-11-15", "amount_paise": 0},
    ]
    with pytest.raises(ValueError, match="Repayment amount must be positive"):
        validate_repayment_schedule(invalid_payments)


def test_validate_repayment_schedule_out_of_order():
    out_of_order = [
        {"due_date": "2026-11-15", "amount_paise": 600_000},
        {"due_date": "2026-11-01", "amount_paise": 600_000},
    ]
    with pytest.raises(ValueError, match="chronological order"):
        validate_repayment_schedule(out_of_order)


def test_reconcile_schedule_balance():
    # Reducing-balance schedule reconciliation
    schedule = calculate_reducing_balance_schedule(
        principal_paise=1_000_000,
        annual_rate_pct="12.00",
        term_months=6,
    )
    assert reconcile_schedule_balance(1_000_000, schedule) is True

    # Zero-rate installments reconciliation
    zero_installments = [200_000, 200_000, 200_000]
    assert reconcile_schedule_balance(600_000, zero_installments, is_zero_rate=True) is True
    assert reconcile_schedule_balance(700_000, zero_installments, is_zero_rate=True) is False
