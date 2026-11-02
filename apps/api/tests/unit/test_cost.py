from datetime import date
from decimal import Decimal
import pytest

from app.engine.cost import (
    calculate_emi,
    calculate_flat_rate_schedule,
    calculate_full_financing_cost,
    calculate_reducing_balance_schedule,
    calculate_xirr,
    generate_schedule_dates,
    separate_and_validate_fees,
)


def test_zero_rate_emi():
    principal = 6_000_000
    installments = calculate_emi(principal, "0.00", 3)
    assert len(installments) == 3
    assert sum(installments) == principal


def test_nonzero_rate_residual_zero():
    principal = 10_000_000
    installments = calculate_emi(principal, "18.00", 12)
    assert len(installments) == 12
    assert sum(installments) > principal
    assert all(i > 0 for i in installments)


def test_single_installment():
    installments = calculate_emi(1_000_000, "12.00", 1)
    assert len(installments) == 1
    assert installments[0] > 1_000_000


def test_invalid_term():
    with pytest.raises(ValueError, match="term_months must be positive"):
        calculate_emi(1_000_000, "12.00", 0)


def test_invalid_principal():
    with pytest.raises(ValueError, match="principal_paise cannot be negative"):
        calculate_emi(-100, "12.00", 6)


def test_acceptance_zero_rate_12k_three_installments():
    """
    Blueprint Case 1 (p. 21):
    ₹12,000; 0%; 3 equal installments -> Three ₹4,000 payments;
    principal reconciles exactly; zero financing cost if no fees.
    """
    principal = 1_200_000  # ₹12,000
    installments = calculate_emi(principal, "0.00", 3)
    assert installments == [400_000, 400_000, 400_000]
    assert sum(installments) == principal

    cost = calculate_full_financing_cost(
        credit_benefit_paise=principal,
        total_repayments_paise=sum(installments),
        cash_paid_fees_paise=0,
    )
    assert cost == 0


def test_reducing_balance_amortization_schedule_details():
    """
    Checks that reducing-balance schedule generates proper principal/interest breakdown,
    residual principal is adjusted to exactly zero in final installment, and all interest is retained.
    """
    principal = 10_000_000  # ₹100,000
    term = 12
    schedule = calculate_reducing_balance_schedule(
        principal_paise=principal,
        annual_rate_pct="18.00",
        term_months=term,
        first_due_date=date(2026, 11, 1),
    )

    assert len(schedule) == 12
    assert schedule[0].due_date == date(2026, 11, 1)
    assert schedule[-1].due_date == date(2027, 10, 1)

    total_principal_paid = sum(r.principal_paise for r in schedule)
    total_interest_paid = sum(r.interest_paise for r in schedule)
    total_installments = sum(r.installment_paise for r in schedule)

    # Every row satisfies installment = principal + interest
    for r in schedule:
        assert r.installment_paise == r.principal_paise + r.interest_paise
        assert r.installment_paise > 0
        assert r.principal_paise > 0
        assert r.interest_paise > 0

    # Principal reconciles exactly to initial loan
    assert total_principal_paid == principal
    assert schedule[-1].remaining_balance_paise == 0

    # Total installments equal principal + interest
    assert total_installments == principal + total_interest_paid
    assert total_installments > principal


def test_acceptance_withheld_fee_counted_once():
    """
    Blueprint Case 2 (p. 21):
    ₹10,000 gross; ₹500 withheld; repayments ₹10,800 ->
    Usable benefit ₹9,500; financing cost ₹1,300; fee is counted exactly once.
    """
    gross_principal = 1_000_000   # ₹10,000
    withheld_fee = 50_000         # ₹500
    repayments = 1_080_000        # ₹10,800

    fee_info = separate_and_validate_fees(
        principal_paise=gross_principal,
        withheld_fees_paise=withheld_fee,
        cash_paid_fees_paise=0,
        financed_fees_paise=0,
    )

    assert fee_info["usable_benefit_paise"] == 950_000  # ₹9,500
    assert fee_info["mandatory_fees_paise"] == 50_000

    # Fee is already reflected in usable benefit, not added to borrower outflows
    financing_cost = calculate_full_financing_cost(
        credit_benefit_paise=fee_info["usable_benefit_paise"],
        total_repayments_paise=repayments,
        cash_paid_fees_paise=0,
    )
    assert financing_cost == 130_000  # ₹1,300


def test_fee_validation_and_categories():
    principal = 5_000_000  # ₹50,000
    withheld = 100_000     # ₹1,000
    cash_paid = 50_000     # ₹500
    financed = 150_000     # ₹1,500

    fee_info = separate_and_validate_fees(
        principal_paise=principal,
        withheld_fees_paise=withheld,
        cash_paid_fees_paise=cash_paid,
        financed_fees_paise=financed,
    )

    assert fee_info["usable_benefit_paise"] == 4_900_000  # 50,000 - 1,000
    assert fee_info["financed_principal_paise"] == 5_150_000  # 50,000 + 1,500
    assert fee_info["mandatory_fees_paise"] == 300_000

    # Withheld cannot exceed principal
    with pytest.raises(ValueError, match="Withheld fees cannot exceed gross principal"):
        separate_and_validate_fees(100_000, withheld_fees_paise=150_000)

    # Negative fees rejected
    with pytest.raises(ValueError, match="Fees cannot be negative"):
        separate_and_validate_fees(100_000, cash_paid_fees_paise=-10)


def test_flat_rate_schedule():
    """Flat rate loan: 12% flat on ₹12,000 for 12 months = ₹1,440 interest."""
    principal = 1_200_000  # ₹12,000
    schedule = calculate_flat_rate_schedule(principal, "12.00", 12)
    assert len(schedule) == 12

    total_p = sum(r.principal_paise for r in schedule)
    total_i = sum(r.interest_paise for r in schedule)
    total_inst = sum(r.installment_paise for r in schedule)

    assert total_p == principal
    assert total_i == 144_000  # ₹1,440
    assert total_inst == 1_344_000  # ₹13,440
    assert schedule[-1].remaining_balance_paise == 0


def test_generate_schedule_dates_month_clamping():
    start = date(2026, 1, 31)
    dates = generate_schedule_dates(start, 5)
    assert dates == [
        date(2026, 1, 31),
        date(2026, 2, 28),
        date(2026, 3, 31),
        date(2026, 4, 30),
        date(2026, 5, 31),
    ]


def test_xirr_calculation():
    # Borrow ₹100,000 on 2026-01-01, repay ₹110,000 on 2027-01-01 (approx 10% annual)
    cashflows = [
        (date(2026, 1, 1), 10_000_000),
        (date(2027, 1, 1), -11_000_000),
    ]
    rate = calculate_xirr(cashflows)
    assert rate is not None
    assert rate == Decimal("10.00")
