from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Sequence
from dateutil.relativedelta import relativedelta

from app.engine.types import AmortizationScheduleRow


def calculate_emi(principal_paise: int, annual_rate_pct: str | Decimal, term_months: int) -> list[int]:
    """
    Derives monthly installments for a term loan.
    If annual_rate_pct == 0, uses zero-rate equal division with residual paise reconciled.
    If annual_rate_pct > 0, uses standard reducing-balance formula and reconciles residual principal
    on the final installment so final principal becomes exactly zero, without removing interest.
    """
    if term_months <= 0:
        raise ValueError("term_months must be positive")
    if principal_paise < 0:
        raise ValueError("principal_paise cannot be negative")
    if principal_paise == 0:
        return [0] * term_months

    schedule = calculate_reducing_balance_schedule(
        principal_paise=principal_paise,
        annual_rate_pct=annual_rate_pct,
        term_months=term_months,
    )
    return [row.installment_paise for row in schedule]


def calculate_reducing_balance_schedule(
    principal_paise: int,
    annual_rate_pct: str | Decimal,
    term_months: int,
    first_due_date: date | None = None,
) -> list[AmortizationScheduleRow]:
    """
    Generates a full month-by-month reducing-balance amortization schedule.
    Uses Decimal with ROUND_HALF_UP for intermediate interest math.
    Adjusts the final principal payment so residual principal becomes zero.
    """
    if term_months <= 0:
        raise ValueError("term_months must be positive")
    if principal_paise < 0:
        raise ValueError("principal_paise cannot be negative")

    P = Decimal(principal_paise)
    annual_rate = Decimal(str(annual_rate_pct))
    if annual_rate < 0:
        raise ValueError("annual_rate_pct cannot be negative")

    rows: list[AmortizationScheduleRow] = []

    # Zero-rate term loan
    if annual_rate == Decimal(0):
        base_installment = (P / term_months).to_integral_value(rounding=ROUND_HALF_UP)
        remaining_balance = P
        for i in range(1, term_months + 1):
            due_date = first_due_date + relativedelta(months=i - 1) if first_due_date else None
            if i < term_months:
                principal_portion = min(base_installment, remaining_balance)
                remaining_balance -= principal_portion
                installment = principal_portion
            else:
                # Final payment absorbs any rounding difference to ensure residual principal is exactly zero
                principal_portion = remaining_balance
                installment = principal_portion
                remaining_balance = Decimal(0)

            rows.append(
                AmortizationScheduleRow(
                    period=i,
                    due_date=due_date,
                    installment_paise=int(installment),
                    principal_paise=int(principal_portion),
                    interest_paise=0,
                    remaining_balance_paise=int(remaining_balance),
                )
            )
        return rows

    # Non-zero rate: reducing-balance monthly amortization
    r = annual_rate / Decimal(100) / Decimal(12)
    # Standard formula: factor = r * (1 + r)^n / ((1 + r)^n - 1)
    one_plus_r_pow_n = (Decimal(1) + r) ** term_months
    factor = r * one_plus_r_pow_n / (one_plus_r_pow_n - Decimal(1))
    standard_emi = (P * factor).to_integral_value(rounding=ROUND_HALF_UP)

    remaining_principal = P
    for i in range(1, term_months + 1):
        due_date = first_due_date + relativedelta(months=i - 1) if first_due_date else None
        # Accrued interest on current outstanding principal
        monthly_interest = (remaining_principal * r).to_integral_value(rounding=ROUND_HALF_UP)

        if i < term_months:
            principal_portion = standard_emi - monthly_interest
            if principal_portion > remaining_principal:
                principal_portion = remaining_principal
            installment = principal_portion + monthly_interest
            remaining_principal -= principal_portion
        else:
            # Final installment: adjust final principal payment so residual principal becomes zero
            principal_portion = remaining_principal
            installment = principal_portion + monthly_interest
            remaining_principal = Decimal(0)

        rows.append(
            AmortizationScheduleRow(
                period=i,
                due_date=due_date,
                installment_paise=int(installment),
                principal_paise=int(principal_portion),
                interest_paise=int(monthly_interest),
                remaining_balance_paise=int(remaining_principal),
            )
        )

    return rows


def calculate_flat_rate_schedule(
    principal_paise: int,
    annual_rate_pct: str | Decimal,
    term_months: int,
    first_due_date: date | None = None,
) -> list[AmortizationScheduleRow]:
    """
    Generates an amortization schedule for a flat-rate loan.
    Flat interest is calculated on the original principal across the full term:
    total_interest = P * (annual_rate / 100) * (term_months / 12)
    """
    if term_months <= 0:
        raise ValueError("term_months must be positive")
    if principal_paise < 0:
        raise ValueError("principal_paise cannot be negative")

    P = Decimal(principal_paise)
    annual_rate = Decimal(str(annual_rate_pct))
    if annual_rate < 0:
        raise ValueError("annual_rate_pct cannot be negative")

    total_interest = (P * (annual_rate / Decimal(100)) * (Decimal(term_months) / Decimal(12))).to_integral_value(
        rounding=ROUND_HALF_UP
    )
    total_payable = P + total_interest

    base_principal = (P / term_months).to_integral_value(rounding=ROUND_HALF_UP)
    base_interest = (total_interest / term_months).to_integral_value(rounding=ROUND_HALF_UP)

    rows: list[AmortizationScheduleRow] = []
    accumulated_principal = Decimal(0)
    accumulated_interest = Decimal(0)
    remaining_balance = P

    for i in range(1, term_months + 1):
        due_date = first_due_date + relativedelta(months=i - 1) if first_due_date else None
        if i < term_months:
            p_portion = base_principal
            i_portion = base_interest
        else:
            p_portion = P - accumulated_principal
            i_portion = total_interest - accumulated_interest

        accumulated_principal += p_portion
        accumulated_interest += i_portion
        remaining_balance -= p_portion
        installment = p_portion + i_portion

        rows.append(
            AmortizationScheduleRow(
                period=i,
                due_date=due_date,
                installment_paise=int(installment),
                principal_paise=int(p_portion),
                interest_paise=int(i_portion),
                remaining_balance_paise=max(0, int(remaining_balance)),
            )
        )

    return rows


def generate_schedule_dates(first_date: date, term_months: int) -> list[date]:
    """
    Generates monthly recurring dates from a given start date.
    Preserves anchor day of month with automatic end-of-month clamping (e.g. Jan 31 -> Feb 28/29 -> Mar 31).
    """
    return [first_date + relativedelta(months=i) for i in range(term_months)]


def separate_and_validate_fees(
    principal_paise: int,
    withheld_fees_paise: int = 0,
    cash_paid_fees_paise: int = 0,
    financed_fees_paise: int = 0,
) -> dict[str, int]:
    """
    Separates and validates loan fees:
    - withheld_fees: deducted from principal upfront, reduces net usable cash benefit.
    - cash_paid_fees: paid upfront by borrower from cash reserves.
    - financed_fees: added to principal to be repaid over time.
    """
    if principal_paise < 0:
        raise ValueError("principal_paise cannot be negative")
    if withheld_fees_paise < 0 or cash_paid_fees_paise < 0 or financed_fees_paise < 0:
        raise ValueError("Fees cannot be negative")
    if withheld_fees_paise > principal_paise:
        raise ValueError("Withheld fees cannot exceed gross principal")

    usable_benefit_paise = principal_paise - withheld_fees_paise
    financed_principal_paise = principal_paise + financed_fees_paise
    mandatory_fees_paise = withheld_fees_paise + cash_paid_fees_paise + financed_fees_paise

    return {
        "principal_paise": principal_paise,
        "withheld_fees_paise": withheld_fees_paise,
        "cash_paid_fees_paise": cash_paid_fees_paise,
        "financed_fees_paise": financed_fees_paise,
        "mandatory_fees_paise": mandatory_fees_paise,
        "usable_benefit_paise": usable_benefit_paise,
        "financed_principal_paise": financed_principal_paise,
    }


def calculate_full_financing_cost(
    credit_benefit_paise: int,
    total_repayments_paise: int,
    cash_paid_fees_paise: int = 0,
) -> int:
    """
    Financing cost formula (Blueprint p. 11):
    cost = all_borrower_outflows_for_credit - credit_benefit

    Where:
    - all_borrower_outflows_for_credit = sum(repayments) + cash_paid_fees
    - Withheld fees are already reflected in the reduced credit_benefit, ensuring
      fee is counted exactly once and not doubled.
    """
    all_borrower_outflows = total_repayments_paise + cash_paid_fees_paise
    return all_borrower_outflows - credit_benefit_paise


def calculate_xirr(
    cashflows: Sequence[tuple[date, int]],
    max_iterations: int = 100,
    tolerance: Decimal = Decimal("1e-7"),
) -> Decimal | None:
    """
    Solves for effective annualized internal rate of return (XIRR) using Newton-Raphson.
    cashflows: Sequence of (date, amount_paise) where positive is borrower inflow, negative is outflow.
    Discloses day basis (actual/365).
    Returns rate as a percentage Decimal (e.g. Decimal("18.45")), or None if no unique valid root exists.
    """
    if len(cashflows) < 2:
        return None

    # Must have at least one positive and one negative cashflow
    has_pos = any(amount > 0 for _, amount in cashflows)
    has_neg = any(amount < 0 for _, amount in cashflows)
    if not (has_pos and has_neg):
        return None

    # Sort cashflows chronologically to ensure canonical earliest-date anchor
    sorted_cfs = sorted(cashflows, key=lambda x: x[0])
    d0 = sorted_cfs[0][0]
    days_amounts: list[tuple[Decimal, Decimal]] = [
        (Decimal((d - d0).days) / Decimal(365), Decimal(amt)) for d, amt in sorted_cfs
    ]
    total_flow = sum(abs(amt) for _, amt in days_amounts)

    # Initial guess 10%
    rate = Decimal("0.10")

    for _ in range(max_iterations):
        if rate <= Decimal("-0.999"):
            return None

        one_plus_r = Decimal(1) + rate
        f_val = Decimal(0)
        df_val = Decimal(0)

        for t_i, c_i in days_amounts:
            try:
                discount = one_plus_r ** (-t_i)
                f_val += c_i * discount
                if t_i != Decimal(0):
                    df_val += -t_i * c_i * (one_plus_r ** (-t_i - Decimal(1)))
            except (ArithmeticError, OverflowError):
                return None

        # Scaled residual tolerance: within 1 paise or tolerance * total_flow
        if total_flow > 0 and (abs(f_val) <= Decimal("1.0") or abs(f_val) <= tolerance * total_flow):
            pct = (rate * Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            return pct

        if abs(df_val) < Decimal("1e-12"):
            return None

        new_rate = rate - (f_val / df_val)
        if abs(new_rate - rate) < tolerance:
            pct = (new_rate * Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            return pct

        rate = new_rate

    return None
