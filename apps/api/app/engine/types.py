from dataclasses import dataclass, field
from datetime import date as dt_date
from decimal import Decimal
from enum import Enum
from typing import Sequence

# Money is represented as integer paise (1 INR = 100 paise)
Money = int


class OutcomeBand(str, Enum):
    INSUFFICIENT_DATA = "insufficient_data"
    FUNDING_GAP = "funding_gap"
    SHORTFALL = "shortfall"
    BUFFER_BREACH = "buffer_breach"
    STRESS_SENSITIVE = "stress_sensitive"
    WITHIN_STATED_ASSUMPTIONS = "within_stated_assumptions"


@dataclass(frozen=True)
class CashEvent:
    event_date: dt_date
    amount_paise: int
    category: str
    source_id: str = ""
    event_id: str = ""
    direction: str = "outflow"  # "inflow" | "outflow"
    timing: str = "known"       # "known" | "estimated"
    source: str = "manual"      # "manual" | "csv" | "mock_aa"
    status: str = "scheduled"   # "scheduled" | "paid" | "actual"

    def __init__(
        self,
        event_date: dt_date | None = None,
        amount_paise: int = 0,
        category: str = "",
        source_id: str = "",
        event_id: str = "",
        direction: str = "outflow",
        timing: str = "known",
        source: str = "manual",
        status: str = "scheduled",
        date: dt_date | None = None,
    ):
        actual_date = date if date is not None else event_date
        if actual_date is None:
            raise ValueError("CashEvent requires an event_date or date")
        amt = int(amount_paise)
        if amt < 0:
            raise ValueError(f"amount_paise cannot be negative, got {amt}")
        object.__setattr__(self, "event_date", actual_date)
        object.__setattr__(self, "amount_paise", amt)
        object.__setattr__(self, "category", category)
        object.__setattr__(self, "source_id", source_id)
        object.__setattr__(self, "event_id", event_id)
        object.__setattr__(self, "direction", direction)
        object.__setattr__(self, "timing", timing)
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "status", status)

    @property
    def date(self) -> dt_date:
        return self.event_date


@dataclass(frozen=True)
class ReasonEvidence:
    code: str
    date: dt_date | None = None
    event_ids: tuple[str, ...] = ()
    before_paise: int = 0
    after_paise: int = 0
    threshold_paise: int = 0
    message_key: str = ""
    assumptions: tuple[str, ...] = ()

    def __init__(
        self,
        code: str,
        date: dt_date | None = None,
        event_ids: Sequence[str] = (),
        before_paise: int = 0,
        after_paise: int = 0,
        threshold_paise: int = 0,
        message_key: str = "",
        assumptions: Sequence[str] = (),
    ):
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "date", date)
        object.__setattr__(self, "event_ids", tuple(event_ids))
        object.__setattr__(self, "before_paise", int(before_paise))
        object.__setattr__(self, "after_paise", int(after_paise))
        object.__setattr__(self, "threshold_paise", int(threshold_paise))
        object.__setattr__(self, "message_key", message_key)
        object.__setattr__(self, "assumptions", tuple(assumptions))


@dataclass(frozen=True)
class AmortizationScheduleRow:
    period: int
    due_date: dt_date | None
    installment_paise: int
    principal_paise: int
    interest_paise: int
    remaining_balance_paise: int


@dataclass(frozen=True)
class FundingAndPayments:
    offer_id: str
    offer_type: str
    principal_paise: int
    credit_benefit_paise: int
    withheld_fees_paise: int
    cash_paid_fees_paise: int
    financed_fees_paise: int
    mandatory_fees_paise: int
    disbursement_date: dt_date
    is_merchant_only: bool
    payments: tuple[CashEvent, ...]
    total_repayment_paise: int
    financing_cost_paise: int
    upfront_cash_required_paise: int
    payoff_date: dt_date | None
    remaining_balance_beyond_horizon_paise: int = 0
    apr_annual_pct: Decimal | None = None
    nominal_annual_rate_pct: Decimal | None = None
    is_flat_rate: bool = False
    is_long_term_cost_unavailable: bool = False
    rejection_reason: str | None = None


@dataclass(frozen=True)
class OfferSchedule:
    offer_id: str
    offer_type: str
    credit_benefit_paise: int
    fees_cash_paise: int
    payments: tuple[CashEvent, ...]


@dataclass(frozen=True)
class FinancialSnapshot:
    opening_cash_paise: int
    balance_as_of: dt_date
    reserve_floor_paise: int
    income_rules: tuple
    expense_rules: tuple
    obligations: tuple
    goals: tuple
    data_version: int


@dataclass(frozen=True)
class ScenarioInput:
    expense_amount_paise: int
    expense_date: dt_date
    need_cash: bool
    allowed_savings_paise: int
    horizon_days: int
    offers: tuple[OfferSchedule, ...]


@dataclass
class CashPath:
    dates: list[dt_date]
    balances_paise: list[int]
    headrooms_paise: list[int]
    first_reserve_breach: dt_date | None = None
    first_negative: dt_date | None = None
    trough_paise: int | None = None
    trough_date: dt_date | None = None


@dataclass
class OfferResult:
    offer_id: str
    funding_gap_paise: int
    cash_required_now_paise: int
    total_repayment_paise: int
    financing_cost_paise: int
    remaining_balance_paise: int
    shortfall_paise: int
    cash_path: CashPath
    pressure_windows: list[tuple[dt_date, dt_date]]
    reason_codes: list[str]
    excluded_obligations: list[str]
    status: str
    band: str = ""
    payoff_date: dt_date | None = None
    evidence: list[ReasonEvidence] = field(default_factory=list)
    trough_paise: int | None = None
    trough_date: dt_date | None = None
    first_negative: dt_date | None = None
    first_reserve_breach: dt_date | None = None
    is_long_term_cost_unavailable: bool = False


@dataclass
class AnalysisResult:
    baseline: CashPath
    offers: list[OfferResult]
    model_version: str
    stress_results: dict[str, list[OfferResult]] = field(default_factory=dict)


# Type aliases per blueprint convention
Snapshot = FinancialSnapshot
Scenario = ScenarioInput
