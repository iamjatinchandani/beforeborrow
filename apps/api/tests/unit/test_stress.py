from datetime import date
from dateutil.relativedelta import relativedelta

from app.engine.stress import stress
from app.engine.types import FinancialSnapshot


def _create_sample_snapshot():
    return FinancialSnapshot(
        opening_cash_paise=2_400_000,
        balance_as_of=date(2026, 11, 1),
        reserve_floor_paise=500_000,
        income_rules=(
            {
                "id": "inc-salary",
                "category": "salary",
                "amount_paise": 3_000_000,
                "due_date": "2026-11-07",
                "frequency": "monthly",
            },
        ),
        expense_rules=(
            {
                "id": "exp-rent",
                "category": "rent",
                "amount_paise": 800_000,
                "due_date": "2026-11-03",
                "frequency": "monthly",
            },
        ),
        obligations=(),
        goals=(),
        data_version=1,
    )


def test_income_delay_7d():
    orig = _create_sample_snapshot()
    stressed = stress(orig, "income_delay_7d")

    orig_date = orig.income_rules[0]["due_date"]
    stressed_date = stressed.income_rules[0]["due_date"]

    assert orig_date == "2026-11-07"
    assert stressed_date == date(2026, 11, 14)


def test_income_drop_20pct_next_2():
    orig = _create_sample_snapshot()
    stressed = stress(orig, "income_drop_20pct_next_2")

    # 3,000,000 * 0.80 = 2,400,000 paise (₹24,000)
    # The monthly rule should be split: first 2 occurrences at 2,400,000, then resuming at 3,000,000
    reduced_rules = [r for r in stressed.income_rules if r["amount_paise"] == 2_400_000]
    assert len(reduced_rules) == 2
    assert reduced_rules[0]["due_date"] == date(2026, 11, 7)
    assert reduced_rules[1]["due_date"] == date(2026, 12, 7)

    # Future recurring rule resumes at normal 3,000,000
    resumed_rules = [r for r in stressed.income_rules if r["amount_paise"] == 3_000_000]
    assert len(resumed_rules) == 1
    assert resumed_rules[0]["due_date"] == date(2027, 1, 7)


def test_expense_spike_5000_30d():
    orig = _create_sample_snapshot()
    stressed = stress(orig, "expense_spike_5000_30d")

    assert len(orig.expense_rules) == 1
    assert len(stressed.expense_rules) == 2

    spike = stressed.expense_rules[-1]
    assert spike["amount_paise"] == 500_000
    assert spike["due_date"] == orig.balance_as_of + relativedelta(days=30)


def test_snapshot_immutability():
    orig = _create_sample_snapshot()
    orig_income_rule_len = len(orig.income_rules)
    orig_expense_rule_len = len(orig.expense_rules)
    orig_due_date = orig.income_rules[0]["due_date"]

    _ = stress(orig, "income_delay_7d")
    _ = stress(orig, "income_drop_20pct_next_2")
    _ = stress(orig, "expense_spike_5000_30d")

    # Original snapshot must remain strictly unchanged
    assert len(orig.income_rules) == orig_income_rule_len
    assert len(orig.expense_rules) == orig_expense_rule_len
    assert orig.income_rules[0]["due_date"] == orig_due_date
    assert orig.income_rules[0]["amount_paise"] == 3_000_000
