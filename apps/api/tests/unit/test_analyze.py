from datetime import date
import json
from pathlib import Path
from dateutil.relativedelta import relativedelta

from app.engine.analyze import analyze, normalize_offer
from app.engine.explanations import explain, format_inr
from app.engine.types import (
    FinancialSnapshot,
    OfferResult,
    OutcomeBand,
    ScenarioInput,
)


def _load_fixture(name: str) -> dict:
    # Locate packages/contracts/fixtures relative to repo root
    current = Path(__file__).resolve()
    # current: apps/api/tests/unit/test_analyze.py
    # repo root is 4 levels up
    repo_root = current.parents[4]
    fixture_path = repo_root / "packages" / "contracts" / "fixtures" / f"{name}.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_checked_example_page_12_fixture():
    """
    Blueprint Page 12 verified fixture ("0% can still hurt"):
    Bank cash ₹24,000, reserve floor ₹5,000, emergency merchant bill ₹30,000.
    BNPL 4 x ₹6,000 payments on 1 Nov, 15 Nov, 1 Dec, 15 Dec.
    Salary ₹30,000 arrives 7 Nov.

    Verified Invariants:
    - credit_benefit_paise = ₹24,000 (2,400,000 paise)
    - financing_cost_paise = ₹0
    - first_reserve_breach = 3 Nov 2026
    - normal_first_negative_balance = 3 Dec 2026
    - delayed_salary_first_negative_balance = 12 Nov 2026 (shortfall of -₹7,000)
    """
    data = _load_fixture("checked-example")

    snapshot = FinancialSnapshot(
        opening_cash_paise=data["profile"]["opening_cash_paise"],
        balance_as_of=date.fromisoformat(data["profile"]["balance_as_of"]),
        reserve_floor_paise=data["profile"]["reserve_floor_paise"],
        income_rules=tuple(data["income"]),
        expense_rules=tuple(data["expenses"]),
        obligations=tuple(data["obligations"]),
        goals=(),
        data_version=1,
    )

    scenario = ScenarioInput(
        expense_amount_paise=data["scenario"]["expense_amount_paise"],
        expense_date=date.fromisoformat(data["scenario"]["expense_date"]),
        need_cash=data["scenario"]["need_cash"],
        allowed_savings_paise=data["scenario"]["allowed_savings_paise"],
        horizon_days=data["scenario"]["horizon_days"],
        offers=tuple(data["offers"]),
    )

    res = analyze(snapshot, scenario)
    assert len(res.offers) == 1
    offer_res = res.offers[0]

    # Invariants check
    assert offer_res.financing_cost_paise == 0
    assert offer_res.first_reserve_breach == date(2026, 11, 3)
    assert offer_res.first_negative == date(2026, 12, 3)

    # Check delayed salary stress result
    delayed_salary_res = res.stress_results["income_delay_7d"][0]
    assert delayed_salary_res.first_negative == date(2026, 11, 12)

    # 12 Nov balance under delayed salary must be -₹7,000
    idx_nov12 = delayed_salary_res.cash_path.dates.index(date(2026, 11, 12))
    assert delayed_salary_res.cash_path.balances_paise[idx_nov12] == -700_000

    # Explanation includes the breach date
    text_exp = explain(offer_res)
    assert "3 Nov 2026" in text_exp or "below your ₹5,000 reserve" in text_exp


def test_acceptance_case_3_merchant_bnpl():
    """
    Blueprint Case 3 (p. 21):
    Merchant BNPL ₹24,000; 4 x ₹6,000 -> No ₹24,000 bank-cash inflow;
    first payment may be due today; debt ends after the fourth payment.
    """
    scenario = {
        "expense_amount_paise": 3_000_000,
        "expense_date": date(2026, 11, 1),
        "need_cash": False,
        "allowed_savings_paise": 600_000,
    }

    offer = {
        "offer_id": "bnpl-4x6k",
        "offer_type": "bnpl",
        "principal_paise": 2_400_000,
        "term_months": 2,
        "schedule": [
            {"due_date": "2026-11-01", "amount_paise": 600_000},
            {"due_date": "2026-11-15", "amount_paise": 600_000},
            {"due_date": "2026-12-01", "amount_paise": 600_000},
            {"due_date": "2026-12-15", "amount_paise": 600_000},
        ],
    }

    norm = normalize_offer(offer, scenario)
    assert norm.is_merchant_only is True
    assert norm.credit_benefit_paise == 2_400_000
    assert norm.financing_cost_paise == 0
    assert norm.upfront_cash_required_paise == 600_000  # First installment due today
    assert norm.payoff_date == date(2026, 12, 15)


def test_acceptance_case_4_apr_without_contractual_rate():
    """
    Blueprint Case 4 (p. 21):
    APR quoted but contract rate missing ->
    Do not derive EMI by dividing APR by 12; request a schedule or contractual interest rate.
    """
    scenario = {
        "expense_amount_paise": 1_000_000,
        "expense_date": date(2026, 11, 1),
        "need_cash": True,
        "allowed_savings_paise": 0,
    }

    offer = {
        "offer_id": "loan-apr-only",
        "offer_type": "term_loan",
        "principal_paise": 1_000_000,
        "apr_annual_pct": "18.00",
        "rate_annual_pct": "",  # Contract rate missing!
        "term_months": 12,
    }

    norm = normalize_offer(offer, scenario)
    assert norm.rejection_reason is not None
    assert "contractual rate" in norm.rejection_reason.lower()


def test_missing_data_fixture_returns_insufficient_data():
    """
    Blueprint missing-data fixture:
    Income timing unknown -> engine returns insufficient_data outcome band.
    """
    data = _load_fixture("missing-data")

    snapshot = FinancialSnapshot(
        opening_cash_paise=data["profile"]["opening_cash_paise"],
        balance_as_of=date.fromisoformat(data["profile"]["balance_as_of"]),
        reserve_floor_paise=data["profile"]["reserve_floor_paise"],
        income_rules=tuple(data["income"]),
        expense_rules=tuple(data["expenses"]),
        obligations=tuple(data["obligations"]),
        goals=(),
        data_version=1,
    )

    scenario = ScenarioInput(
        expense_amount_paise=data["scenario"]["expense_amount_paise"],
        expense_date=date.fromisoformat(data["scenario"]["expense_date"]),
        need_cash=data["scenario"]["need_cash"],
        allowed_savings_paise=data["scenario"]["allowed_savings_paise"],
        horizon_days=data["scenario"]["horizon_days"],
        offers=tuple(data["offers"]),
    )

    res = analyze(snapshot, scenario)
    assert len(res.offers) == 1
    assert res.offers[0].band == OutcomeBand.INSUFFICIENT_DATA.value
    assert res.offers[0].status == OutcomeBand.INSUFFICIENT_DATA.value


def test_disbursement_after_emergency_rejected():
    scenario = {
        "expense_amount_paise": 1_000_000,
        "expense_date": date(2026, 11, 1),
        "need_cash": True,
    }
    offer = {
        "offer_id": "late-loan",
        "offer_type": "term_loan",
        "principal_paise": 1_000_000,
        "disbursement_date": date(2026, 11, 5),  # 4 days after emergency!
    }
    norm = normalize_offer(offer, scenario)
    assert norm.rejection_reason is not None
    assert "after the emergency" in norm.rejection_reason


def test_merchant_only_rejected_for_cash_need():
    scenario = {
        "expense_amount_paise": 1_000_000,
        "expense_date": date(2026, 11, 1),
        "need_cash": True,  # Cash needed!
    }
    offer = {
        "offer_id": "bnpl-offer",
        "offer_type": "bnpl",
        "principal_paise": 1_000_000,
    }
    norm = normalize_offer(offer, scenario)
    assert norm.rejection_reason is not None
    assert "Merchant-only" in norm.rejection_reason


def test_outcome_bands():
    # 1. Comfortable under stated assumptions
    snap = FinancialSnapshot(
        opening_cash_paise=10_000_000,
        balance_as_of=date(2026, 11, 1),
        reserve_floor_paise=1_000_000,
        income_rules=(
            {"amount_paise": 5_000_000, "due_date": "2026-11-05", "frequency": "monthly", "timing": "known"},
        ),
        expense_rules=(
            {"amount_paise": 500_000, "due_date": "2026-11-10", "frequency": "monthly", "timing": "known"},
        ),
        obligations=(),
        goals=(),
        data_version=1,
    )

    scen = ScenarioInput(
        expense_amount_paise=1_000_000,
        expense_date=date(2026, 11, 1),
        need_cash=False,
        allowed_savings_paise=1_000_000,
        horizon_days=90,
        offers=(
            {
                "offer_id": "safe-bnpl",
                "offer_type": "bnpl",
                "principal_paise": 1_000_000,
                "term_months": 2,
                "schedule": [
                    {"due_date": "2026-11-01", "amount_paise": 500_000},
                    {"due_date": "2026-12-01", "amount_paise": 500_000},
                ],
            },
        ),
    )

    res = analyze(snap, scen)
    assert res.offers[0].band == OutcomeBand.WITHIN_STATED_ASSUMPTIONS.value


def test_format_inr_helper():
    assert format_inr(500_000) == "₹5,000"
    assert format_inr(10_000_000) == "₹1,00,000"
    assert format_inr(-700_000) == "-₹7,000"
    assert format_inr(0) == "₹0"
