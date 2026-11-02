from datetime import date
from decimal import Decimal
import json
from typing import Any
from dateutil.relativedelta import relativedelta

from app.engine.cashflow import identify_pressure_windows, simulate
from app.engine.cost import (
    calculate_full_financing_cost,
    calculate_reducing_balance_schedule,
    separate_and_validate_fees,
)
from app.engine.policy import DEFAULT_POLICY, Policy
from app.engine.schedules import expand_rules, validate_repayment_schedule
from app.engine.stress import SUPPORTED_STRESS_CASES, stress
from app.engine.types import (
    AnalysisResult,
    CashEvent,
    CashPath,
    FinancialSnapshot,
    FundingAndPayments,
    OfferResult,
    OutcomeBand,
    ReasonEvidence,
    ScenarioInput,
)


def _get_field(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _to_date(val: Any) -> date | None:
    if val is None:
        return None
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        return date.fromisoformat(val)
    return None


def normalize_offer(offer: Any, scenario: Any) -> FundingAndPayments:
    """
    Normalizes a funding offer into a FundingAndPayments contract.
    Enforces Blueprint requirements:
    - Separates gross principal, usable benefit, withheld, cash-paid and financed fees.
    - Validates category and disbursement date against the emergency expense.
    - Respects merchant-only restrictions (merchant BNPL never enters bank cash).
    - Rejects offers disbursed after the emergency date.
    - Rejects dividing quoted APR by 12 when contractual interest rate is missing.
    """
    offer_id = str(_get_field(offer, "offer_id", _get_field(offer, "id", "offer-1")))
    offer_type = str(_get_field(offer, "offer_type", _get_field(offer, "type", "term_loan"))).lower()
    principal_paise = int(_get_field(offer, "principal_paise", _get_field(offer, "principal", 0)))
    fees_paise = int(_get_field(offer, "fees_paise", _get_field(offer, "fees", 0)))

    disb_date = _to_date(_get_field(offer, "disbursement_date"))
    expense_date = _to_date(_get_field(scenario, "expense_date"))
    if disb_date is None:
        disb_date = expense_date or date.today()

    need_cash = bool(_get_field(scenario, "need_cash", False))
    is_merchant_only = offer_type in ("bnpl", "merchant_credit")

    # 1. Reject if disbursed after emergency expense date
    if expense_date and disb_date > expense_date:
        return FundingAndPayments(
            offer_id=offer_id,
            offer_type=offer_type,
            principal_paise=principal_paise,
            credit_benefit_paise=0,
            withheld_fees_paise=0,
            cash_paid_fees_paise=0,
            financed_fees_paise=0,
            mandatory_fees_paise=fees_paise,
            disbursement_date=disb_date,
            is_merchant_only=is_merchant_only,
            payments=(),
            total_repayment_paise=0,
            financing_cost_paise=0,
            upfront_cash_required_paise=0,
            payoff_date=None,
            rejection_reason="Offer disbursement date is after the emergency expense date.",
        )

    # 2. Reject if merchant-only financing cannot fund cash expenses
    if need_cash and is_merchant_only:
        return FundingAndPayments(
            offer_id=offer_id,
            offer_type=offer_type,
            principal_paise=principal_paise,
            credit_benefit_paise=0,
            withheld_fees_paise=0,
            cash_paid_fees_paise=0,
            financed_fees_paise=0,
            mandatory_fees_paise=fees_paise,
            disbursement_date=disb_date,
            is_merchant_only=is_merchant_only,
            payments=(),
            total_repayment_paise=0,
            financing_cost_paise=0,
            upfront_cash_required_paise=0,
            payoff_date=None,
            rejection_reason="Merchant-only financing cannot fund cash expenses.",
        )

    # 3. Check APR without contractual rate (Blueprint Case 4)
    apr_val = _get_field(offer, "apr_annual_pct", _get_field(offer, "apr"))
    rate_val = _get_field(offer, "rate_annual_pct", _get_field(offer, "rate"))
    schedule_raw = _get_field(offer, "schedule", _get_field(offer, "payments", _get_field(offer, "schedule_json")))

    if apr_val and (rate_val is None or str(rate_val).strip() == "") and not schedule_raw:
        return FundingAndPayments(
            offer_id=offer_id,
            offer_type=offer_type,
            principal_paise=principal_paise,
            credit_benefit_paise=0,
            withheld_fees_paise=0,
            cash_paid_fees_paise=0,
            financed_fees_paise=0,
            mandatory_fees_paise=fees_paise,
            disbursement_date=disb_date,
            is_merchant_only=is_merchant_only,
            payments=(),
            total_repayment_paise=0,
            financing_cost_paise=0,
            upfront_cash_required_paise=0,
            payoff_date=None,
            rejection_reason="Quoted APR cannot be divided by 12; contractual rate or explicit schedule required.",
        )

    # 4. Fee breakdown
    withheld_fees = int(_get_field(offer, "withheld_fees_paise", fees_paise if offer_type == "term_loan" else 0))
    cash_paid_fees = int(_get_field(offer, "cash_paid_fees_paise", 0))
    financed_fees = int(_get_field(offer, "financed_fees_paise", 0))

    fee_info = separate_and_validate_fees(
        principal_paise=principal_paise,
        withheld_fees_paise=withheld_fees,
        cash_paid_fees_paise=cash_paid_fees,
        financed_fees_paise=financed_fees,
    )

    credit_benefit_paise = principal_paise if is_merchant_only else fee_info["usable_benefit_paise"]

    # 5. Extract or derive repayment schedule
    payments_list: list[CashEvent] = []

    if schedule_raw:
        if isinstance(schedule_raw, str):
            try:
                parsed_schedule = json.loads(schedule_raw)
            except Exception:
                parsed_schedule = []
        else:
            parsed_schedule = schedule_raw

        for item in parsed_schedule:
            if isinstance(item, CashEvent):
                payments_list.append(item)
            elif isinstance(item, dict):
                p_date = _to_date(item.get("due_date") or item.get("date") or item.get("event_date"))
                p_amt = int(item.get("amount_paise") or item.get("amount", 0))
                if p_date and p_amt > 0:
                    payments_list.append(
                        CashEvent(
                            event_date=p_date,
                            amount_paise=p_amt,
                            category="offer_repayment",
                            source_id=offer_id,
                            direction="outflow",
                        )
                    )
        validate_repayment_schedule(payments_list)
    else:
        # Derive schedule if missing
        term_months = _get_field(offer, "term_months")
        if term_months is None or int(term_months) <= 0:
            return FundingAndPayments(
                offer_id=offer_id,
                offer_type=offer_type,
                principal_paise=principal_paise,
                credit_benefit_paise=credit_benefit_paise,
                withheld_fees_paise=withheld_fees,
                cash_paid_fees_paise=cash_paid_fees,
                financed_fees_paise=financed_fees,
                mandatory_fees_paise=fee_info["mandatory_fees_paise"],
                disbursement_date=disb_date,
                is_merchant_only=is_merchant_only,
                payments=(),
                total_repayment_paise=0,
                financing_cost_paise=0,
                upfront_cash_required_paise=cash_paid_fees,
                payoff_date=None,
                rejection_reason="Missing term_months to derive repayment schedule.",
            )

        term_m = int(term_months)
        contract_rate = str(rate_val or "0.00")

        # First payment date: BNPL often starts day 0; loans start 1 month out
        first_due = disb_date if offer_type == "bnpl" else disb_date + relativedelta(months=1)
        amort_rows = calculate_reducing_balance_schedule(
            principal_paise=fee_info["financed_principal_paise"],
            annual_rate_pct=contract_rate,
            term_months=term_m,
            first_due_date=first_due,
        )
        for r in amort_rows:
            if r.due_date:
                payments_list.append(
                    CashEvent(
                        event_date=r.due_date,
                        amount_paise=r.installment_paise,
                        category="offer_repayment",
                        source_id=offer_id,
                        direction="outflow",
                    )
                )

    total_repayments = sum(p.amount_paise for p in payments_list)
    financing_cost = calculate_full_financing_cost(
        credit_benefit_paise=credit_benefit_paise,
        total_repayments_paise=total_repayments,
        cash_paid_fees_paise=cash_paid_fees,
    )

    payoff_date = max((p.event_date for p in payments_list), default=None)

    # Upfront cash required today
    immediate_payments = sum(p.amount_paise for p in payments_list if p.event_date == disb_date)
    upfront_cash_required = cash_paid_fees + immediate_payments

    return FundingAndPayments(
        offer_id=offer_id,
        offer_type=offer_type,
        principal_paise=principal_paise,
        credit_benefit_paise=credit_benefit_paise,
        withheld_fees_paise=withheld_fees,
        cash_paid_fees_paise=cash_paid_fees,
        financed_fees_paise=financed_fees,
        mandatory_fees_paise=fee_info["mandatory_fees_paise"],
        disbursement_date=disb_date,
        is_merchant_only=is_merchant_only,
        payments=tuple(payments_list),
        total_repayment_paise=total_repayments,
        financing_cost_paise=financing_cost,
        upfront_cash_required_paise=upfront_cash_required,
        payoff_date=payoff_date,
    )


def check_blocking_data_gaps(snapshot: FinancialSnapshot) -> tuple[bool, list[str]]:
    """
    Validates mandatory snapshot fields for blocking data gaps (e.g. unknown or estimated income timing).
    Returns (has_gap, missing_fields).
    """
    missing_fields: list[str] = []
    for inc in snapshot.income_rules or ():
        timing = str(_get_field(inc, "timing", "known"))
        due_d = _get_field(inc, "due_date")
        start_d = _get_field(inc, "start_date")
        if (due_d is None and start_d is None) or timing == "estimated":
            if "income_timing" not in missing_fields:
                missing_fields.append("income_timing")

    return len(missing_fields) > 0, missing_fields


def analyze(
    snapshot: FinancialSnapshot,
    scenario: ScenarioInput,
    policy: Policy = DEFAULT_POLICY,
) -> AnalysisResult:
    """
    Orchestrates the decision engine:
    1. Validates mandatory financial inputs.
    2. Simulates baseline cash path (existing commitments without emergency).
    3. Normalizes candidate offers and evaluates funding gaps.
    4. Simulates candidate cash paths under base and named stress presets.
    5. Categorizes deterministic outcome bands and structured evidence.
    """
    start_date = snapshot.balance_as_of
    horizon_days = scenario.horizon_days if scenario.horizon_days > 0 else policy.default_horizon_days
    end_date = start_date + relativedelta(days=horizon_days)

    # Check for blocking gaps (e.g. unknown income timing as in missing-data fixture)
    has_blocking_data_gap, missing_fields = check_blocking_data_gaps(snapshot)

    # Expand baseline commitments (reference path)
    baseline_events = expand_rules(snapshot, start_date, end_date)
    baseline_path = simulate(
        events=baseline_events,
        opening_cash=snapshot.opening_cash_paise,
        reserve=snapshot.reserve_floor_paise,
        start=start_date,
        end=end_date,
    )

    offer_results: list[OfferResult] = []
    stress_results_map: dict[str, list[OfferResult]] = {}

    for offer_input in scenario.offers or ():
        norm = normalize_offer(offer_input, scenario)
        offer_id = norm.offer_id

        # 1. Check if blocking data gap or unsupported contract rate
        if has_blocking_data_gap or (norm.rejection_reason and "rate" in norm.rejection_reason.lower()):
            empty_path = CashPath(dates=[], balances_paise=[], headrooms_paise=[])
            ev = ReasonEvidence(
                code="INSUFFICIENT_DATA",
                message_key="insufficient_data",
                assumptions=("mandatory_data_missing",),
            )
            offer_results.append(
                OfferResult(
                    offer_id=offer_id,
                    funding_gap_paise=scenario.expense_amount_paise,
                    cash_required_now_paise=0,
                    total_repayment_paise=0,
                    financing_cost_paise=0,
                    remaining_balance_paise=0,
                    shortfall_paise=0,
                    cash_path=empty_path,
                    pressure_windows=[],
                    reason_codes=["insufficient_data"],
                    excluded_obligations=[],
                    status=OutcomeBand.INSUFFICIENT_DATA.value,
                    band=OutcomeBand.INSUFFICIENT_DATA.value,
                    evidence=[ev],
                )
            )
            continue

        # 2. Check funding coverage gap or rejection
        funding_gap = max(0, scenario.expense_amount_paise - scenario.allowed_savings_paise - norm.credit_benefit_paise)
        if norm.rejection_reason or funding_gap > 0:
            ev = ReasonEvidence(
                code="FUNDING_GAP",
                message_key="funding_gap",
                assumptions=(norm.rejection_reason or "expense_exceeds_benefit",),
            )
            offer_results.append(
                OfferResult(
                    offer_id=offer_id,
                    funding_gap_paise=funding_gap,
                    cash_required_now_paise=0,
                    total_repayment_paise=norm.total_repayment_paise,
                    financing_cost_paise=norm.financing_cost_paise,
                    remaining_balance_paise=0,
                    shortfall_paise=0,
                    cash_path=baseline_path,
                    pressure_windows=[],
                    reason_codes=["funding_gap"],
                    excluded_obligations=[],
                    status=OutcomeBand.FUNDING_GAP.value,
                    band=OutcomeBand.FUNDING_GAP.value,
                    evidence=[ev],
                )
            )
            continue

        # 3. Build candidate cash events
        candidate_events = list(baseline_events)

        # Add emergency expense and funding flows
        if norm.is_merchant_only:
            # Merchant paid directly: cash emergency payment is only the savings / down-payment share
            cash_emergency_share = max(0, scenario.expense_amount_paise - norm.credit_benefit_paise)
            if cash_emergency_share > 0:
                candidate_events.append(
                    CashEvent(
                        event_date=scenario.expense_date,
                        amount_paise=cash_emergency_share,
                        category="emergency_cash_share",
                        direction="outflow",
                        source_id=f"emergency-{offer_id}",
                    )
                )
        else:
            # Cash loan: full emergency expense paid from cash; net credit benefit received as cash
            candidate_events.append(
                CashEvent(
                    event_date=scenario.expense_date,
                    amount_paise=scenario.expense_amount_paise,
                    category="emergency_expense",
                    direction="outflow",
                    source_id=f"emergency-{offer_id}",
                )
            )
            candidate_events.append(
                CashEvent(
                    event_date=norm.disbursement_date,
                    amount_paise=norm.credit_benefit_paise,
                    category="loan_disbursement",
                    direction="inflow",
                    source_id=f"disb-{offer_id}",
                )
            )

        if norm.cash_paid_fees_paise > 0:
            candidate_events.append(
                CashEvent(
                    event_date=norm.disbursement_date,
                    amount_paise=norm.cash_paid_fees_paise,
                    category="cash_paid_fee",
                    direction="outflow",
                    source_id=f"fee-{offer_id}",
                )
            )

        # Add new debt repayments
        for p in norm.payments:
            if p.event_date <= end_date:
                candidate_events.append(p)

        # Simulate base case candidate path
        cand_path = simulate(
            events=candidate_events,
            opening_cash=snapshot.opening_cash_paise,
            reserve=snapshot.reserve_floor_paise,
            start=start_date,
            end=end_date,
        )

        # Upfront cash required now
        emergency_cash_share = (
            max(0, scenario.expense_amount_paise - norm.credit_benefit_paise)
            if norm.is_merchant_only
            else scenario.expense_amount_paise
        )
        immediate_payment = sum(p.amount_paise for p in norm.payments if p.event_date == norm.disbursement_date)
        cash_required_now = emergency_cash_share + immediate_payment + norm.cash_paid_fees_paise

        # Remaining debt balance beyond horizon
        remaining_balance_beyond = sum(p.amount_paise for p in norm.payments if p.event_date > end_date)

        # Calculate shortfall (max deficit below zero)
        shortfall_paise = max(0, -cand_path.trough_paise) if cand_path.trough_paise is not None and cand_path.trough_paise < 0 else 0

        # Pressure windows
        windows = identify_pressure_windows(cand_path, policy.pressure_headroom_paise, policy.pressure_window_days)

        # 4. Run stress cases
        stress_breached = False
        evidence_list: list[ReasonEvidence] = []
        reason_codes: list[str] = []

        for case_name in ("income_delay_7d", "income_drop_20pct_next_2", "expense_spike_5000_30d"):
            stressed_snap = stress(snapshot, case_name)
            stressed_base_events = expand_rules(stressed_snap, start_date, end_date)

            stressed_cand_events = list(stressed_base_events)
            if norm.is_merchant_only:
                if cash_emergency_share > 0:
                    stressed_cand_events.append(
                        CashEvent(
                            event_date=scenario.expense_date,
                            amount_paise=cash_emergency_share,
                            category="emergency_cash_share",
                            direction="outflow",
                            source_id=f"emergency-{offer_id}",
                        )
                    )
            else:
                stressed_cand_events.append(
                    CashEvent(
                        event_date=scenario.expense_date,
                        amount_paise=scenario.expense_amount_paise,
                        category="emergency_expense",
                        direction="outflow",
                        source_id=f"emergency-{offer_id}",
                    )
                )
                stressed_cand_events.append(
                    CashEvent(
                        event_date=norm.disbursement_date,
                        amount_paise=norm.credit_benefit_paise,
                        category="loan_disbursement",
                        direction="inflow",
                        source_id=f"disb-{offer_id}",
                    )
                )

            if norm.cash_paid_fees_paise > 0:
                stressed_cand_events.append(
                    CashEvent(
                        event_date=norm.disbursement_date,
                        amount_paise=norm.cash_paid_fees_paise,
                        category="cash_paid_fee",
                        direction="outflow",
                        source_id=f"fee-{offer_id}",
                    )
                )

            for p in norm.payments:
                if p.event_date <= end_date:
                    stressed_cand_events.append(p)

            s_path = simulate(
                events=stressed_cand_events,
                opening_cash=stressed_snap.opening_cash_paise,
                reserve=stressed_snap.reserve_floor_paise,
                start=start_date,
                end=end_date,
            )

            # Record stress result
            s_shortfall = max(0, -s_path.trough_paise) if s_path.trough_paise is not None and s_path.trough_paise < 0 else 0
            s_res = OfferResult(
                offer_id=offer_id,
                funding_gap_paise=0,
                cash_required_now_paise=cash_required_now,
                total_repayment_paise=norm.total_repayment_paise,
                financing_cost_paise=norm.financing_cost_paise,
                remaining_balance_paise=remaining_balance_beyond,
                shortfall_paise=s_shortfall,
                cash_path=s_path,
                pressure_windows=[],
                reason_codes=[],
                excluded_obligations=[],
                status=case_name,
                trough_paise=s_path.trough_paise,
                trough_date=s_path.trough_date,
                first_negative=s_path.first_negative,
                first_reserve_breach=s_path.first_reserve_breach,
            )
            stress_results_map.setdefault(case_name, []).append(s_res)

            if s_path.first_reserve_breach is not None:
                stress_breached = True
                evidence_list.append(
                    ReasonEvidence(
                        code="STRESS_RESERVE_BREACH",
                        date=s_path.first_reserve_breach,
                        before_paise=s_path.trough_paise or 0,
                        after_paise=s_path.trough_paise or 0,
                        threshold_paise=snapshot.reserve_floor_paise,
                        message_key="stress_reserve_breach",
                        assumptions=(case_name,),
                    )
                )

        # 5. Deterministic outcome band hierarchy (Blueprint p. 22)
        if cand_path.first_negative is not None:
            band = OutcomeBand.SHORTFALL
            reason_codes.append("shortfall")
            evidence_list.append(
                ReasonEvidence(
                    code="SHORTFALL",
                    date=cand_path.first_negative,
                    before_paise=0,
                    after_paise=cand_path.trough_paise or 0,
                    threshold_paise=0,
                    message_key="shortfall",
                )
            )
        elif cand_path.first_reserve_breach is not None:
            band = OutcomeBand.BUFFER_BREACH
            reason_codes.append("reserve_breach")
            evidence_list.append(
                ReasonEvidence(
                    code="RESERVE_BREACH",
                    date=cand_path.first_reserve_breach,
                    before_paise=snapshot.reserve_floor_paise,
                    after_paise=cand_path.trough_paise or 0,
                    threshold_paise=snapshot.reserve_floor_paise,
                    message_key="reserve_breach",
                )
            )
        elif stress_breached:
            band = OutcomeBand.STRESS_SENSITIVE
            reason_codes.append("stress_sensitive")
        else:
            band = OutcomeBand.WITHIN_STATED_ASSUMPTIONS
            reason_codes.append("within_stated_assumptions")

        offer_results.append(
            OfferResult(
                offer_id=offer_id,
                funding_gap_paise=0,
                cash_required_now_paise=cash_required_now,
                total_repayment_paise=norm.total_repayment_paise,
                financing_cost_paise=norm.financing_cost_paise,
                remaining_balance_paise=remaining_balance_beyond,
                shortfall_paise=shortfall_paise,
                cash_path=cand_path,
                pressure_windows=windows,
                reason_codes=reason_codes,
                excluded_obligations=[],
                status=band.value,
                band=band.value,
                payoff_date=norm.payoff_date,
                evidence=evidence_list,
                trough_paise=cand_path.trough_paise,
                trough_date=cand_path.trough_date,
                first_negative=cand_path.first_negative,
                first_reserve_breach=cand_path.first_reserve_breach,
            )
        )

    return AnalysisResult(
        baseline=baseline_path,
        offers=offer_results,
        model_version=policy.model_version,
        stress_results=stress_results_map,
    )
