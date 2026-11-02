from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date
from itertools import combinations
from typing import Any, Sequence
from dateutil.relativedelta import relativedelta

from app.engine.analyze import check_blocking_data_gaps, normalize_offer
from app.engine.cashflow import simulate
from app.engine.cost import calculate_full_financing_cost
from app.engine.schedules import expand_rules
from app.engine.stress import stress
from app.engine.types import (
    CashEvent,
    FinancialSnapshot,
    FundingAndPayments,
    OutcomeBand,
    ReasonEvidence,
    ScenarioInput,
)


MAX_CANDIDATE_EVALUATIONS = 500
SAVINGS_STEP_PAISE = 50_000  # ₹500 in integer paise (non-negotiable blueprint rule)


@dataclass(frozen=True)
class GoalImpact:
    goal_id: str
    label: str
    target_amount_paise: int
    target_date: date | None
    protected: bool
    baseline_contribution_paise: int
    candidate_contribution_paise: int
    target_funding_gap_paise: int
    status: str = "on_track"


@dataclass
class Alternative:
    description: str
    changes: dict
    assumptions: list[str]
    financing_cost_diff_paise: int = 0
    min_cash_diff_paise: int = 0
    tradeoffs: list[str] = field(default_factory=list)
    approval_dependencies: list[str] = field(default_factory=list)
    goal_impacts: list[GoalImpact] = field(default_factory=list)
    user_changes_count: int = 0
    full_financing_cost_paise: int = 0
    min_cash_paise: int = 0


@dataclass
class Alternatives:
    feasible: list[Alternative]
    no_feasible_plan: bool = False
    binding_causes: list[str] = field(default_factory=list)
    tested_count: int = 0
    bounds: dict = field(default_factory=dict)
    truncated: bool = False
    insufficient_data: bool = False
    missing_fields: list[str] = field(default_factory=list)
    evidence: list[ReasonEvidence] = field(default_factory=list)


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


def _evaluate_goal_impacts(
    snapshot: FinancialSnapshot,
    modified_snapshot: FinancialSnapshot,
    start_date: date,
    end_date: date,
    candidate_min_cash: int,
) -> list[GoalImpact]:
    """
    Evaluates goal contributions and target-date funding gaps before and after changes.
    Uses actual contribution occurrences from schedule expansion up to the target date.
    Protected goals reserve funds in the cash ledger.
    If horizon/rules do not support completion-date estimation, reports target-date funding gap.
    """
    impacts: list[GoalImpact] = []

    for goal in snapshot.goals or ():
        g_id = str(_get_field(goal, "id", ""))
        label = str(_get_field(goal, "label", "Goal"))
        target_amt = int(_get_field(goal, "target_amount_paise", 0))
        target_d = _to_date(_get_field(goal, "target_date"))
        protected = bool(_get_field(goal, "protected", False))
        rule_id = _get_field(goal, "contribution_rule_id")

        effective_target = target_d or end_date
        baseline_contrib = 0
        candidate_contrib = 0

        if rule_id:
            if effective_target >= start_date:
                base_events = expand_rules(snapshot, start_date, effective_target)
                baseline_contrib = sum(
                    e.amount_paise
                    for e in base_events
                    if e.source_id == str(rule_id) and e.direction == "outflow"
                )
                cand_events = expand_rules(modified_snapshot, start_date, effective_target)
                candidate_contrib = sum(
                    e.amount_paise
                    for e in cand_events
                    if e.source_id == str(rule_id) and e.direction == "outflow"
                )
        else:
            if protected:
                baseline_contrib = target_amt
                candidate_contrib = target_amt

        target_gap = max(0, target_amt - candidate_contrib)

        status = "on_track"
        if target_gap > 0:
            status = "shortfall"
        elif candidate_min_cash < snapshot.reserve_floor_paise:
            status = "at_risk"

        impacts.append(
            GoalImpact(
                goal_id=g_id,
                label=label,
                target_amount_paise=target_amt,
                target_date=target_d,
                protected=protected,
                baseline_contribution_paise=baseline_contrib,
                candidate_contribution_paise=candidate_contrib,
                target_funding_gap_paise=target_gap,
                status=status,
            )
        )

    return impacts


def search_changes(
    snapshot: FinancialSnapshot,
    scenario: ScenarioInput,
    bounds: dict | None = None,
) -> Alternatives:
    """
    Searches for bounded, feasible counterfactual alternatives that resolve reserve breaches.

    Allowed Candidate Changes (Blueprint p. 23):
    1. Savings contributions in exact ₹500 steps (50,000 paise).
    2. Lender-confirmed alternative payment terms or dates.
    3. User-approved discretionary expense reductions.

    Enforces:
    - Rejection of insufficient or estimated snapshot data with explicit evidence.
    - Hard cap of 500 candidate evaluations (returns tested_count, bounds, truncated status).
    - Inclusion of cash-paid fees in candidate minimum cash and reserve feasibility.
    - Reserve feasibility under base and all named stress cases.
    - Lexicographic ranking: (1) Fewest user changes -> (2) Lower financing cost -> (3) Higher min cash.
    - Top 3 recommendations with exact changed fields, tradeoffs, approval dependencies.
    - `no_feasible_plan` with binding causes if no candidate works.
    - Pure, deterministic calculation without mutating original snapshot.
    """
    bounds = bounds or {}

    # 1. Blocking data gap validation (Blueprint p. 9, 23)
    has_blocking_gap, missing_fields = check_blocking_data_gaps(snapshot)
    if has_blocking_gap:
        gap_str = ", ".join(missing_fields)
        return Alternatives(
            feasible=[],
            no_feasible_plan=True,
            binding_causes=[
                f"Insufficient data: required financial information is missing or estimated ({gap_str}). "
                "Counterfactual recommendations cannot be calculated without verified dates."
            ],
            tested_count=0,
            bounds=bounds,
            truncated=False,
            insufficient_data=True,
            missing_fields=missing_fields,
            evidence=[
                ReasonEvidence(
                    code="INSUFFICIENT_DATA",
                    message_key="insufficient_data",
                    assumptions=tuple(missing_fields),
                )
            ],
        )

    start_date = snapshot.balance_as_of
    horizon_days = scenario.horizon_days if scenario.horizon_days > 0 else 180
    end_date = start_date + relativedelta(days=horizon_days)

    # 2. Establish baseline and original offer metrics for comparison
    orig_offer = scenario.offers[0] if scenario.offers else None
    orig_norm = normalize_offer(orig_offer, scenario) if orig_offer else None
    orig_cost = orig_norm.financing_cost_paise if orig_norm else 0

    base_events = expand_rules(snapshot, start_date, end_date)
    base_path = simulate(
        events=base_events,
        opening_cash=snapshot.opening_cash_paise,
        reserve=snapshot.reserve_floor_paise,
        start=start_date,
        end=end_date,
    )
    orig_min_cash = base_path.trough_paise if base_path.trough_paise is not None else 0

    # 3. Extract allowed candidate search space
    # (a) Savings variations (exact ₹500 increments / 50,000 paise only)
    raw_min_s = int(bounds.get("min_savings_paise", 0))
    min_savings = ((raw_min_s + SAVINGS_STEP_PAISE - 1) // SAVINGS_STEP_PAISE) * SAVINGS_STEP_PAISE

    raw_max_limit = min(
        scenario.expense_amount_paise,
        snapshot.opening_cash_paise,
        int(bounds.get("max_savings_paise", snapshot.opening_cash_paise)),
    )
    max_savings = (raw_max_limit // SAVINGS_STEP_PAISE) * SAVINGS_STEP_PAISE

    savings_candidates: list[int] = []
    curr_s = min_savings
    while curr_s <= max_savings:
        savings_candidates.append(curr_s)
        curr_s += SAVINGS_STEP_PAISE

    orig_savings = scenario.allowed_savings_paise
    if (
        orig_savings % SAVINGS_STEP_PAISE == 0
        and min_savings <= orig_savings <= max_savings
        and orig_savings not in savings_candidates
    ):
        savings_candidates.append(orig_savings)
        savings_candidates.sort()

    # (b) Lender-confirmed alternative offers only (do not invent unconfirmed terms)
    candidate_offers: list[Any] = list(scenario.offers or ())
    confirmed_alternates = bounds.get("confirmed_alternate_offers", [])
    candidate_offers.extend(confirmed_alternates)

    # (c) User-approved discretionary reductions (combinations of approved reductions)
    discretionary_reductions = bounds.get("discretionary_expense_reductions", [])
    valid_reductions: list[tuple[str, int]] = []
    seen_rule_ids = set()
    for red in discretionary_reductions:
        rule_id = str(_get_field(red, "rule_id", "")).strip()
        max_red = int(_get_field(red, "max_reduction_paise", 0))
        if rule_id and max_red > 0 and rule_id not in seen_rule_ids:
            seen_rule_ids.add(rule_id)
            valid_reductions.append((rule_id, max_red))

    # Sort valid_reductions for deterministic evaluation order
    valid_reductions.sort(key=lambda x: x[0])

    # Power set of reduction combinations ordered by combination size (fewest user changes first)
    reduction_combinations: list[dict[str, int]] = [{}]
    for r_len in range(1, len(valid_reductions) + 1):
        for combo in combinations(valid_reductions, r_len):
            reduction_combinations.append(dict(combo))

    # 4. Grid search bounded by 500 evaluations
    evaluated_count = 0
    truncated = False
    feasible_alternatives: list[Alternative] = []
    binding_causes: set[str] = set()

    for off in candidate_offers:
        is_alternate_offer = off in confirmed_alternates

        for sav in savings_candidates:
            for red_map in reduction_combinations:
                # Check evaluation limit before running the candidate
                if evaluated_count >= MAX_CANDIDATE_EVALUATIONS:
                    truncated = True
                    break

                evaluated_count += 1

                # Step 4.1: Check funding coverage gap
                cand_scenario = ScenarioInput(
                    expense_amount_paise=scenario.expense_amount_paise,
                    expense_date=scenario.expense_date,
                    need_cash=scenario.need_cash,
                    allowed_savings_paise=sav,
                    horizon_days=horizon_days,
                    offers=(off,),
                )
                cand_norm = normalize_offer(off, cand_scenario)

                if cand_norm.rejection_reason:
                    binding_causes.add(cand_norm.rejection_reason)
                    continue

                gap = max(
                    0,
                    scenario.expense_amount_paise - sav - cand_norm.credit_benefit_paise,
                )
                if gap > 0:
                    binding_causes.add(
                        f"Savings of ₹{sav // 100} and credit benefit of ₹{cand_norm.credit_benefit_paise // 100} leave a funding gap of ₹{gap // 100}."
                    )
                    continue

                # Step 4.2: Build modified snapshot with discretionary reductions
                mod_expense_rules = []
                for exp in snapshot.expense_rules or ():
                    exp_dict = dict(exp) if isinstance(exp, dict) else {k: getattr(exp, k) for k in dir(exp) if not k.startswith("_")}
                    r_id = str(exp_dict.get("id", ""))
                    if r_id in red_map:
                        cut = red_map[r_id]
                        cur_amt = int(exp_dict.get("amount_paise", 0))
                        exp_dict["amount_paise"] = max(0, cur_amt - cut)
                    mod_expense_rules.append(exp_dict)

                mod_snapshot = FinancialSnapshot(
                    opening_cash_paise=snapshot.opening_cash_paise,
                    balance_as_of=snapshot.balance_as_of,
                    reserve_floor_paise=snapshot.reserve_floor_paise,
                    income_rules=deepcopy(snapshot.income_rules),
                    expense_rules=tuple(mod_expense_rules),
                    obligations=deepcopy(snapshot.obligations),
                    goals=deepcopy(snapshot.goals),
                    data_version=snapshot.data_version,
                )

                # Step 4.3: Simulate candidate base cash path
                mod_base_events = expand_rules(mod_snapshot, start_date, end_date)
                cand_events = list(mod_base_events)

                if cand_norm.is_merchant_only:
                    emergency_share = max(0, scenario.expense_amount_paise - cand_norm.credit_benefit_paise)
                    if emergency_share > 0:
                        cand_events.append(
                            CashEvent(
                                event_date=scenario.expense_date,
                                amount_paise=emergency_share,
                                category="emergency_cash_share",
                                direction="outflow",
                            )
                        )
                else:
                    cand_events.append(
                        CashEvent(
                            event_date=scenario.expense_date,
                            amount_paise=scenario.expense_amount_paise,
                            category="emergency_expense",
                            direction="outflow",
                        )
                    )
                    cand_events.append(
                        CashEvent(
                            event_date=cand_norm.disbursement_date,
                            amount_paise=cand_norm.credit_benefit_paise,
                            category="loan_disbursement",
                            direction="inflow",
                        )
                    )

                # Include cash-paid upfront fees (Blueprint p. 11 formula)
                if cand_norm.cash_paid_fees_paise > 0:
                    cand_events.append(
                        CashEvent(
                            event_date=cand_norm.disbursement_date,
                            amount_paise=cand_norm.cash_paid_fees_paise,
                            category="cash_paid_fee",
                            direction="outflow",
                            source_id=f"fee-{cand_norm.offer_id}",
                        )
                    )

                for p in cand_norm.payments:
                    if p.event_date <= end_date:
                        cand_events.append(p)

                cand_path = simulate(
                    events=cand_events,
                    opening_cash=mod_snapshot.opening_cash_paise,
                    reserve=mod_snapshot.reserve_floor_paise,
                    start=start_date,
                    end=end_date,
                )

                # Check base reserve feasibility
                if cand_path.first_reserve_breach is not None:
                    binding_causes.add(
                        f"Base cash drops below ₹{snapshot.reserve_floor_paise // 100} reserve floor on {cand_path.first_reserve_breach}."
                    )
                    continue

                if cand_path.first_negative is not None:
                    binding_causes.add(f"Base cash drops negative on {cand_path.first_negative}.")
                    continue

                # Step 4.4: Simulate under named stress presets
                stress_failed = False
                for case_name in ("income_delay_7d", "income_drop_20pct_next_2", "expense_spike_5000_30d"):
                    s_snap = stress(mod_snapshot, case_name)
                    s_events = list(expand_rules(s_snap, start_date, end_date))

                    if cand_norm.is_merchant_only:
                        if emergency_share > 0:
                            s_events.append(
                                CashEvent(
                                    event_date=scenario.expense_date,
                                    amount_paise=emergency_share,
                                    category="emergency_cash_share",
                                    direction="outflow",
                                )
                            )
                    else:
                        s_events.append(
                            CashEvent(
                                event_date=scenario.expense_date,
                                amount_paise=scenario.expense_amount_paise,
                                category="emergency_expense",
                                direction="outflow",
                            )
                        )
                        s_events.append(
                            CashEvent(
                                event_date=cand_norm.disbursement_date,
                                amount_paise=cand_norm.credit_benefit_paise,
                                category="loan_disbursement",
                                direction="inflow",
                            )
                        )

                    # Include cash-paid upfront fees under stress
                    if cand_norm.cash_paid_fees_paise > 0:
                        s_events.append(
                            CashEvent(
                                event_date=cand_norm.disbursement_date,
                                amount_paise=cand_norm.cash_paid_fees_paise,
                                category="cash_paid_fee",
                                direction="outflow",
                                source_id=f"fee-{cand_norm.offer_id}",
                            )
                        )

                    for p in cand_norm.payments:
                        if p.event_date <= end_date:
                            s_events.append(p)

                    s_path = simulate(
                        events=s_events,
                        opening_cash=s_snap.opening_cash_paise,
                        reserve=s_snap.reserve_floor_paise,
                        start=start_date,
                        end=end_date,
                    )

                    if s_path.first_reserve_breach is not None:
                        stress_failed = True
                        binding_causes.add(
                            f"Reserve floor breached under stress '{case_name}' on {s_path.first_reserve_breach}."
                        )
                        break

                if stress_failed:
                    continue

                # Step 4.5: Candidate is feasible!
                changes_count = 0
                changed_fields: dict[str, Any] = {}
                tradeoffs: list[str] = []
                dependencies: list[str] = []

                if sav != orig_savings:
                    changes_count += 1
                    changed_fields["allowed_savings_paise"] = sav
                    diff_s = (sav - orig_savings) // 100
                    prefix = "+" if diff_s > 0 else ""
                    tradeoffs.append(f"Savings allocation changed by {prefix}₹{abs(diff_s):,}")

                if is_alternate_offer:
                    changes_count += 1
                    changed_fields["offer_id"] = cand_norm.offer_id
                    tradeoffs.append(f"Switch to confirmed alternate offer '{cand_norm.offer_id}'")
                    dependencies.append("Requires lender confirmation of alternate terms")

                if red_map:
                    changes_count += len(red_map)
                    changed_fields["discretionary_reductions"] = red_map
                    total_cut = sum(red_map.values()) // 100
                    tradeoffs.append(f"User discretionary spending reduced by ₹{total_cut:,}")
                    dependencies.append("User committed to discretionary budget cut")

                cand_trough = cand_path.trough_paise if cand_path.trough_paise is not None else 0
                cost_diff = cand_norm.financing_cost_paise - orig_cost
                min_cash_diff = cand_trough - orig_min_cash

                # Goal impact analysis
                goal_impacts = _evaluate_goal_impacts(
                    snapshot=snapshot,
                    modified_snapshot=mod_snapshot,
                    start_date=start_date,
                    end_date=end_date,
                    candidate_min_cash=cand_trough,
                )

                desc_parts = []
                if sav != orig_savings:
                    desc_parts.append(f"Contribute ₹{sav // 100:,} from savings")
                if is_alternate_offer:
                    desc_parts.append(f"Use alternate offer '{cand_norm.offer_id}'")
                if red_map:
                    desc_parts.append("Apply discretionary spending reduction")
                desc = " & ".join(desc_parts) if desc_parts else "Original plan is feasible under tested constraints"

                feasible_alternatives.append(
                    Alternative(
                        description=desc,
                        changes=changed_fields,
                        assumptions=["base_reserve_met", "stress_resilient"],
                        financing_cost_diff_paise=cost_diff,
                        min_cash_diff_paise=min_cash_diff,
                        tradeoffs=tradeoffs,
                        approval_dependencies=dependencies,
                        goal_impacts=goal_impacts,
                        user_changes_count=changes_count,
                        full_financing_cost_paise=cand_norm.financing_cost_paise,
                        min_cash_paise=cand_trough,
                    )
                )

            if truncated:
                break
        if truncated:
            break

    # 5. Lexicographic Ranking (Blueprint p. 23):
    # (1) Fewest user changes -> (2) Lower full financing cost -> (3) Higher minimum cash
    feasible_alternatives.sort(
        key=lambda alt: (
            alt.user_changes_count,
            alt.full_financing_cost_paise,
            -alt.min_cash_paise,
        )
    )

    top_three = feasible_alternatives[:3]

    if not top_three:
        binding_causes.add(
            "Next action: Contact provider to negotiate payment terms (do not assume unconfirmed payment holiday)."
        )
        return Alternatives(
            feasible=[],
            no_feasible_plan=True,
            binding_causes=sorted(list(binding_causes)),
            tested_count=evaluated_count,
            bounds=bounds,
            truncated=truncated,
        )

    return Alternatives(
        feasible=top_three,
        no_feasible_plan=False,
        binding_causes=[],
        tested_count=evaluated_count,
        bounds=bounds,
        truncated=truncated,
    )
