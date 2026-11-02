from copy import deepcopy
from datetime import date
from dateutil.relativedelta import relativedelta

from app.engine.counterfactuals import (
    MAX_CANDIDATE_EVALUATIONS,
    SAVINGS_STEP_PAISE,
    Alternative,
    search_changes,
)
from app.engine.types import FinancialSnapshot, ScenarioInput


def _create_sample_environment(opening_cash=2_000_000, reserve=500_000, expense=1_500_000):
    snapshot = FinancialSnapshot(
        opening_cash_paise=opening_cash,
        balance_as_of=date(2026, 11, 1),
        reserve_floor_paise=reserve,
        income_rules=(
            {
                "id": "inc-salary",
                "category": "salary",
                "amount_paise": 4_000_000,  # ₹40,000
                "due_date": "2026-11-05",
                "frequency": "monthly",
                "timing": "known",
            },
        ),
        expense_rules=(
            {
                "id": "exp-rent",
                "category": "rent",
                "amount_paise": 1_000_000,  # ₹10,000
                "due_date": "2026-11-02",
                "frequency": "monthly",
                "timing": "known",
            },
            {
                "id": "exp-dining",
                "category": "discretionary",
                "amount_paise": 300_000,   # ₹3,000
                "due_date": "2026-11-10",
                "frequency": "monthly",
                "timing": "known",
            },
        ),
        obligations=(),
        goals=(
            {
                "id": "goal-laptop",
                "label": "New Laptop",
                "target_amount_paise": 5_000_000,
                "target_date": "2027-02-01",
                "protected": True,
                "contribution_rule_id": None,
            },
        ),
        data_version=1,
    )

    scenario = ScenarioInput(
        expense_amount_paise=expense,
        expense_date=date(2026, 11, 1),
        need_cash=False,
        allowed_savings_paise=500_000,   # ₹5,000 savings
        horizon_days=90,
        offers=(
            {
                "offer_id": "bnpl-short",
                "offer_type": "bnpl",
                "principal_paise": 1_000_000,  # ₹10,000
                "term_months": 2,
                "schedule": [
                    {"due_date": "2026-11-01", "amount_paise": 500_000},
                    {"due_date": "2026-12-01", "amount_paise": 500_000},
                ],
            },
        ),
    )
    return snapshot, scenario


def test_hard_cap_500_evaluations_and_truncation():
    """Search space must never exceed 500 candidate evaluations and flag truncated=True when > 500 exist."""
    snapshot, scenario = _create_sample_environment(
        opening_cash=50_000_000,
        expense=50_000_000,
    )

    bounds = {
        "min_savings_paise": 0,
        "max_savings_paise": 35_000_000,  # 700 steps of 50,000 paise
    }

    res = search_changes(snapshot, scenario, bounds)
    assert res.tested_count <= MAX_CANDIDATE_EVALUATIONS
    assert res.tested_count == MAX_CANDIDATE_EVALUATIONS
    assert res.truncated is True


def test_search_space_exactly_500_not_truncated():
    """Search space with exactly 500 candidate evaluations must test all 500 and not flag truncated."""
    snapshot, scenario = _create_sample_environment(
        opening_cash=50_000_000,
        expense=50_000_000,
    )

    # Exactly 500 steps: 0, 50k, 100k, ..., 24,950,000 (499 * 50,000)
    bounds = {
        "min_savings_paise": 0,
        "max_savings_paise": 24_950_000,
    }

    res = search_changes(snapshot, scenario, bounds)
    assert res.tested_count == 500
    assert res.truncated is False


def test_savings_increments_of_500():
    """All savings changes must be exact ₹500 (50,000 paise) increments."""
    snapshot, scenario = _create_sample_environment()

    bounds = {
        "min_savings_paise": 0,
        "max_savings_paise": 1_000_000,
    }

    res = search_changes(snapshot, scenario, bounds)
    for alt in res.feasible:
        if "allowed_savings_paise" in alt.changes:
            s_val = alt.changes["allowed_savings_paise"]
            assert s_val % SAVINGS_STEP_PAISE == 0


def test_starting_savings_not_divisible_by_50000():
    """Starting savings not divisible by 50,000 paise must never be injected as a candidate step."""
    snapshot, scenario = _create_sample_environment(opening_cash=5_000_000, expense=1_500_000)

    # User enters ₹4,321 (432,100 paise), which is not a multiple of 50,000
    scenario = ScenarioInput(
        expense_amount_paise=scenario.expense_amount_paise,
        expense_date=scenario.expense_date,
        need_cash=scenario.need_cash,
        allowed_savings_paise=432_100,
        horizon_days=90,
        offers=scenario.offers,
    )

    bounds = {
        "min_savings_paise": 0,
        "max_savings_paise": 1_000_000,
    }

    res = search_changes(snapshot, scenario, bounds)
    assert len(res.feasible) > 0
    for alt in res.feasible:
        if "allowed_savings_paise" in alt.changes:
            s_val = alt.changes["allowed_savings_paise"]
            assert s_val % SAVINGS_STEP_PAISE == 0
            assert s_val != 432_100


def test_cash_paid_fees_reserve_breach_rejection():
    """Candidate offer with cash-paid upfront fees causing reserve breach must be rejected."""
    # Opening cash ₹7,000, reserve floor ₹5,000.
    snapshot = FinancialSnapshot(
        opening_cash_paise=700_000,
        balance_as_of=date(2026, 11, 1),
        reserve_floor_paise=500_000,
        income_rules=(),
        expense_rules=(),
        obligations=(),
        goals=(),
        data_version=1,
    )

    # Emergency ₹10,000. Loan principal ₹10,000 with cash-paid fee of ₹2,500.
    # Without fee: Cash = ₹7,000 - ₹10,000 + ₹10,000 = ₹7,000 (>= ₹5,000 reserve floor).
    # With fee: Cash = ₹7,000 - ₹2,500 = ₹4,500 (< ₹5,000 reserve floor -> BREACH).
    scenario = ScenarioInput(
        expense_amount_paise=1_000_000,
        expense_date=date(2026, 11, 1),
        need_cash=True,
        allowed_savings_paise=0,
        horizon_days=60,
        offers=(
            {
                "offer_id": "loan-with-cash-fee",
                "offer_type": "term_loan",
                "principal_paise": 1_000_000,
                "cash_paid_fees_paise": 250_000,  # ₹2,500 cash fee paid upfront
                "term_months": 2,
                "rate_annual_pct": "0.00",
            },
        ),
    )

    res = search_changes(snapshot, scenario, bounds={"min_savings_paise": 0, "max_savings_paise": 0})
    assert res.no_feasible_plan is True
    assert len(res.feasible) == 0
    assert any("reserve floor" in cause.lower() for cause in res.binding_causes)


def test_missing_snapshot_data_insufficient_data():
    """Snapshot with missing or estimated income timing must return insufficient_data with explicit evidence."""
    snapshot = FinancialSnapshot(
        opening_cash_paise=1_500_000,
        balance_as_of=date(2026, 11, 1),
        reserve_floor_paise=500_000,
        income_rules=(
            {
                "id": "inc-unknown-timing",
                "amount_paise": 5_000_000,
                "due_date": None,
                "frequency": "monthly",
                "timing": "estimated",
            },
        ),
        expense_rules=(),
        obligations=(),
        goals=(),
        data_version=1,
    )

    scenario = ScenarioInput(
        expense_amount_paise=1_000_000,
        expense_date=date(2026, 11, 20),
        need_cash=True,
        allowed_savings_paise=0,
        horizon_days=60,
        offers=(
            {
                "offer_id": "loan-1",
                "offer_type": "term_loan",
                "principal_paise": 1_000_000,
                "term_months": 6,
                "rate_annual_pct": "18.00",
            },
        ),
    )

    res = search_changes(snapshot, scenario)
    assert res.no_feasible_plan is True
    assert res.insufficient_data is True
    assert len(res.feasible) == 0
    assert "income_timing" in res.missing_fields
    assert any("insufficient data" in cause.lower() for cause in res.binding_causes)
    assert len(res.evidence) > 0
    assert res.evidence[0].code == "INSUFFICIENT_DATA"


def test_combined_discretionary_reductions():
    """Search must explore combinations of multiple approved reductions when single reductions are insufficient."""
    # Opening cash ₹10,000, reserve floor ₹6,000.
    # Day 1: Emergency covered by loan (0 net cash impact).
    # Day 2: Dining ₹3,000 (300,000 paise).
    # Day 3: Subscriptions ₹2,500 (250,000 paise).
    # Day 10: Salary ₹20,000.
    # On Day 3: Cash balance = ₹10,000 - ₹3,000 - ₹2,500 = ₹4,500 (< ₹6,000 reserve -> breach by ₹1,500).
    # If dining cut by ₹1,000: cash = ₹5,500 (< ₹6,000 -> breach).
    # If subscription cut by ₹1,000: cash = ₹5,500 (< ₹6,000 -> breach).
    # If BOTH dining AND subscription cut by ₹1,000: cash = ₹6,500 (>= ₹6,000 reserve -> FEASIBLE!).
    snapshot = FinancialSnapshot(
        opening_cash_paise=1_000_000,
        balance_as_of=date(2026, 11, 1),
        reserve_floor_paise=600_000,
        income_rules=(
            {
                "id": "inc-salary",
                "category": "salary",
                "amount_paise": 2_000_000,
                "due_date": "2026-11-10",
                "frequency": "monthly",
                "timing": "known",
            },
        ),
        expense_rules=(
            {
                "id": "exp-dining",
                "category": "discretionary",
                "amount_paise": 300_000,
                "due_date": "2026-11-02",
                "frequency": "monthly",
                "timing": "known",
            },
            {
                "id": "exp-subscriptions",
                "category": "discretionary",
                "amount_paise": 250_000,
                "due_date": "2026-11-03",
                "frequency": "monthly",
                "timing": "known",
            },
        ),
        obligations=(),
        goals=(),
        data_version=1,
    )

    scenario = ScenarioInput(
        expense_amount_paise=500_000,
        expense_date=date(2026, 11, 1),
        need_cash=False,
        allowed_savings_paise=0,
        horizon_days=60,
        offers=(
            {
                "offer_id": "bnpl-plan",
                "offer_type": "bnpl",
                "principal_paise": 500_000,
                "term_months": 2,
                "schedule": [
                    {"due_date": "2026-11-20", "amount_paise": 250_000},
                    {"due_date": "2026-12-20", "amount_paise": 250_000},
                ],
            },
        ),
    )

    bounds = {
        "min_savings_paise": 0,
        "max_savings_paise": 0,
        "discretionary_expense_reductions": [
            {"rule_id": "exp-dining", "max_reduction_paise": 100_000},
            {"rule_id": "exp-subscriptions", "max_reduction_paise": 100_000},
        ],
    }

    res = search_changes(snapshot, scenario, bounds)
    assert len(res.feasible) > 0
    chosen = res.feasible[0]
    # Feasible plan must combine both reductions
    assert "discretionary_reductions" in chosen.changes
    cuts = chosen.changes["discretionary_reductions"]
    assert "exp-dining" in cuts
    assert "exp-subscriptions" in cuts
    assert chosen.user_changes_count >= 2


def test_lexicographic_ranking_and_top_three():
    """
    Feasible alternatives must be ranked:
    1. Fewest user changes.
    2. Lower full financing cost.
    3. Higher minimum cash.
    At most 3 alternatives returned.
    """
    snapshot, scenario = _create_sample_environment(opening_cash=5_000_000)

    bounds = {
        "min_savings_paise": 100_000,
        "max_savings_paise": 1_000_000,
        "confirmed_alternate_offers": [
            {
                "offer_id": "alt-zero-cost",
                "offer_type": "bnpl",
                "principal_paise": 1_000_000,
                "term_months": 2,
                "schedule": [
                    {"due_date": "2026-11-01", "amount_paise": 500_000},
                    {"due_date": "2026-12-01", "amount_paise": 500_000},
                ],
            },
        ],
    }

    res = search_changes(snapshot, scenario, bounds)
    assert len(res.feasible) <= 3

    for i in range(len(res.feasible) - 1):
        a1 = res.feasible[i]
        a2 = res.feasible[i + 1]

        # Lexicographic check
        if a1.user_changes_count != a2.user_changes_count:
            assert a1.user_changes_count < a2.user_changes_count
        elif a1.full_financing_cost_paise != a2.full_financing_cost_paise:
            assert a1.full_financing_cost_paise < a2.full_financing_cost_paise
        else:
            assert a1.min_cash_paise >= a2.min_cash_paise


def test_no_feasible_plan_and_binding_causes():
    """
    When reserve floor or funding constraints cannot be met by any candidate,
    engine returns no_feasible_plan=True with binding causes including provider contact.
    """
    snapshot = FinancialSnapshot(
        opening_cash_paise=100_000,
        balance_as_of=date(2026, 11, 1),
        reserve_floor_paise=1_000_000,
        income_rules=(),
        expense_rules=(
            {"id": "exp-rent", "amount_paise": 2_000_000, "due_date": "2026-11-02", "frequency": "once"},
        ),
        obligations=(),
        goals=(),
        data_version=1,
    )
    _, scenario = _create_sample_environment(opening_cash=100_000, reserve=1_000_000)

    res = search_changes(snapshot, scenario, bounds={"min_savings_paise": 0, "max_savings_paise": 100_000})
    assert res.no_feasible_plan is True
    assert len(res.feasible) == 0
    assert len(res.binding_causes) > 0
    # Must instruct contacting provider rather than assuming unconfirmed holiday
    assert any("provider" in cause.lower() for cause in res.binding_causes)


def test_goal_impact_analysis():
    """Goal target-date funding gap is calculated without inventing delay months."""
    snapshot, scenario = _create_sample_environment(opening_cash=5_000_000)

    res = search_changes(snapshot, scenario)
    if res.feasible:
        alt = res.feasible[0]
        assert len(alt.goal_impacts) == 1
        g_imp = alt.goal_impacts[0]
        assert g_imp.goal_id == "goal-laptop"
        assert g_imp.target_amount_paise == 5_000_000
        assert g_imp.protected is True
        assert g_imp.target_funding_gap_paise >= 0


def test_goal_impact_with_rule_expansion():
    """Goal impact must evaluate actual rule expansion occurrences up to target date."""
    snapshot = FinancialSnapshot(
        opening_cash_paise=5_000_000,
        balance_as_of=date(2026, 11, 1),
        reserve_floor_paise=500_000,
        income_rules=(),
        expense_rules=(
            {
                "id": "exp-goal-contrib",
                "category": "savings_transfer",
                "amount_paise": 200_000,  # ₹2,000 monthly
                "due_date": "2026-11-20",  # 20th of each month
                "frequency": "monthly",
                "timing": "known",
            },
        ),
        obligations=(),
        goals=(
            {
                "id": "goal-emergency-fund",
                "label": "Emergency Fund",
                "target_amount_paise": 1_000_000,  # ₹10,000 target
                "target_date": "2026-11-10",  # Due Nov 10 (BEFORE first contribution on Nov 20)
                "protected": False,
                "contribution_rule_id": "exp-goal-contrib",
            },
        ),
        data_version=1,
    )
    _, scenario = _create_sample_environment(opening_cash=5_000_000)

    res = search_changes(snapshot, scenario)
    assert len(res.feasible) > 0
    alt = res.feasible[0]
    g_imp = [g for g in alt.goal_impacts if g.goal_id == "goal-emergency-fund"][0]
    # Because target date 2026-11-10 precedes rule date 2026-11-20, exactly 0 contributions have cleared
    assert g_imp.baseline_contribution_paise == 0
    assert g_imp.candidate_contribution_paise == 0
    assert g_imp.target_funding_gap_paise == 1_000_000
    assert g_imp.status == "shortfall"


def test_deterministic_repeated_results():
    """search_changes must produce identical results across repeated invocations."""
    snapshot, scenario = _create_sample_environment(opening_cash=3_000_000)
    bounds = {"min_savings_paise": 0, "max_savings_paise": 500_000}

    res1 = search_changes(snapshot, scenario, bounds)
    res2 = search_changes(snapshot, scenario, bounds)

    assert res1.tested_count == res2.tested_count
    assert len(res1.feasible) == len(res2.feasible)
    for a1, a2 in zip(res1.feasible, res2.feasible):
        assert a1.user_changes_count == a2.user_changes_count
        assert a1.full_financing_cost_paise == a2.full_financing_cost_paise
        assert a1.min_cash_paise == a2.min_cash_paise
        assert a1.changes == a2.changes


def test_snapshot_immutability_after_search():
    """Original snapshot must remain unchanged after search_changes()."""
    snapshot, scenario = _create_sample_environment()
    orig_expense_rules = deepcopy(snapshot.expense_rules)

    bounds = {
        "discretionary_expense_reductions": [
            {"rule_id": "exp-dining", "max_reduction_paise": 100_000},
        ],
    }

    _ = search_changes(snapshot, scenario, bounds)
    assert snapshot.expense_rules == orig_expense_rules
