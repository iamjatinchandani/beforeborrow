from datetime import date, datetime, timezone
from decimal import Decimal
import json
import re
import pytest

from app.engine.types import (
    CashEvent,
    CashPath,
    FinancialSnapshot,
    FundingAndPayments,
    OutcomeBand,
    ReasonEvidence,
    ScenarioInput,
)
from app.engine.counterfactuals import (
    Alternative,
    Alternatives,
    GoalImpact,
    search_changes,
)
from app.engine.analyze import analyze
from app.engine.policy import DEFAULT_POLICY
from app.engine.serialization import (
    from_canonical_json,
    hash_object,
    hash_snapshot,
    to_canonical_dict,
    to_canonical_json,
)
from app.schemas.decisions import (
    AlternativeOut,
    CounterfactualOut,
    GoalImpactOut,
    ReasonEvidenceOut,
)


def test_stable_serialization_across_dictionary_key_order():
    """Equivalent dictionaries with different insertion orders must produce identical JSON and hashes."""
    dict_a = {
        "z_last": 100,
        "a_first": 200,
        "nested": {
            "m_mid": 300,
            "b_low": 400,
            "x_high": {"sub_2": "val_2", "sub_1": "val_1"},
        },
    }
    dict_b = {
        "nested": {
            "x_high": {"sub_1": "val_1", "sub_2": "val_2"},
            "b_low": 400,
            "m_mid": 300,
        },
        "a_first": 200,
        "z_last": 100,
    }

    json_a = to_canonical_json(dict_a)
    json_b = to_canonical_json(dict_b)

    assert json_a == json_b
    assert hash_snapshot(dict_a) == hash_snapshot(dict_b)
    # Check compact format: no whitespace around ':' or ','
    assert ": " not in json_a
    assert ", " not in json_a
    # Check top-level sorted keys
    assert json_a.startswith('{"a_first":200,')


def test_repeatable_sha256_hash():
    """SHA-256 hash must be deterministic, 64 hex characters, and sensitive to alterations."""
    sample_snapshot = {
        "opening_cash_paise": 2400000,
        "balance_as_of": "2026-11-01",
        "reserve_floor_paise": 500000,
        "data_version": 1,
    }

    hash_1 = hash_snapshot(sample_snapshot)
    hash_2 = hash_snapshot(sample_snapshot)

    assert hash_1 == hash_2
    assert len(hash_1) == 64
    assert all(c in "0123456789abcdef" for c in hash_1)

    # Subtle difference produces entirely different hash
    altered_snapshot = dict(sample_snapshot, opening_cash_paise=2400001)
    assert hash_snapshot(altered_snapshot) != hash_1


def test_dataclass_and_nested_enum_date_serialization():
    """Engine dataclasses, enums, dates, and datetimes must serialize into standard ISO strings."""
    evidence = ReasonEvidence(
        code="RESERVE_BREACH",
        date=date(2026, 11, 3),
        event_ids=("evt_1", "evt_2"),
        before_paise=500000,
        after_paise=400000,
        threshold_paise=500000,
        message_key="reserve_breach",
        assumptions=("same_day_debit_first",),
    )

    ev_json = to_canonical_json(evidence)
    parsed = json.loads(ev_json)

    assert parsed["code"] == "RESERVE_BREACH"
    assert parsed["date"] == "2026-11-03"
    assert parsed["event_ids"] == ["evt_1", "evt_2"]
    assert parsed["before_paise"] == 500000
    assert parsed["after_paise"] == 400000
    assert parsed["threshold_paise"] == 500000

    # Test OutcomeBand enum
    band = OutcomeBand.WITHIN_STATED_ASSUMPTIONS
    assert to_canonical_dict(band) == "within_stated_assumptions"
    assert to_canonical_json({"band": band}) == '{"band":"within_stated_assumptions"}'

    # Test timezone-aware and naive datetimes
    dt_utc = datetime(2026, 11, 1, 10, 30, tzinfo=timezone.utc)
    assert to_canonical_dict(dt_utc) == "2026-11-01T10:30:00+00:00"

    dt_naive = datetime(2026, 11, 1, 10, 30)
    assert to_canonical_dict(dt_naive) == "2026-11-01T10:30:00"


def test_integer_paise_preserved_exact():
    """Integer paise values must never be converted to float or scientific notation."""
    large_paise = 100_000_000_000  # 100 crore in paise
    zero_paise = 0
    negative_paise = -45_000_000

    data = {
        "large_paise": large_paise,
        "zero_paise": zero_paise,
        "negative_paise": negative_paise,
    }

    serialized = to_canonical_json(data)
    assert '"large_paise":100000000000' in serialized
    assert '"zero_paise":0' in serialized
    assert '"negative_paise":-45000000' in serialized
    assert ".0" not in serialized
    # Check that numeric values in serialized JSON do not use scientific notation
    assert re.search(r':-?\d+[eE][+-]?\d+', serialized) is None

    deserialized = from_canonical_json(serialized)
    assert deserialized["large_paise"] == large_paise
    assert type(deserialized["large_paise"]) is int
    assert deserialized["negative_paise"] == negative_paise
    assert type(deserialized["negative_paise"]) is int
    assert deserialized["zero_paise"] == zero_paise
    assert type(deserialized["zero_paise"]) is int


def test_unsupported_and_nonfinite_values_rejected():
    """Non-finite numbers and unsupported objects must be rejected, not silently formatted."""
    # NaN float
    with pytest.raises(ValueError, match="Non-finite float"):
        to_canonical_dict(float("nan"))
    with pytest.raises(ValueError):
        to_canonical_json({"bad": float("nan")})

    # Infinity float
    with pytest.raises(ValueError, match="Non-finite float"):
        to_canonical_dict(float("inf"))
    with pytest.raises(ValueError):
        to_canonical_dict(float("-inf"))

    # Non-finite Decimal
    with pytest.raises(ValueError, match="Non-finite Decimal"):
        to_canonical_dict(Decimal("NaN"))
    with pytest.raises(ValueError):
        to_canonical_dict(Decimal("Infinity"))

    # Unsupported types
    class RandomCustomClass:
        pass

    with pytest.raises(TypeError, match="Unsupported type"):
        to_canonical_dict(RandomCustomClass())

    with pytest.raises(TypeError, match="Unsupported type"):
        to_canonical_dict(lambda x: x)


def test_financial_snapshot_and_analysis_result_serialization():
    """Full FinancialSnapshot and AnalysisResult structures must serialize cleanly and reproducibly."""
    snapshot = FinancialSnapshot(
        opening_cash_paise=2400000,
        balance_as_of=date(2026, 11, 1),
        reserve_floor_paise=500000,
        income_rules=(
            {
                "amount_paise": 3000000,
                "due_date": date(2026, 11, 7),
                "frequency": "monthly",
                "timing": "known",
                "category": "salary",
            },
        ),
        expense_rules=(
            {
                "amount_paise": 800000,
                "due_date": date(2026, 11, 3),
                "frequency": "monthly",
                "category": "rent",
            },
        ),
        obligations=(),
        goals=(),
        data_version=1,
    )

    h = hash_snapshot(snapshot)
    assert len(h) == 64

    scenario = ScenarioInput(
        expense_amount_paise=3000000,
        expense_date=date(2026, 11, 1),
        need_cash=False,
        allowed_savings_paise=600000,
        horizon_days=30,
        offers=(),
    )

    result = analyze(snapshot, scenario, DEFAULT_POLICY)
    result_json = to_canonical_json(result)

    assert '"model_version":"rules-v1"' in result_json
    assert '"balances_paise":' in result_json

    # Deserializes into valid structure
    parsed = from_canonical_json(result_json)
    assert parsed["model_version"] == "rules-v1"
    assert "baseline" in parsed
    assert isinstance(parsed["baseline"]["balances_paise"], list)


def test_counterfactual_schema_validates_actual_search_changes_result():
    """CounterfactualOut Pydantic schema must validate actual search_changes() Alternatives results."""
    snapshot = FinancialSnapshot(
        opening_cash_paise=2400000,
        balance_as_of=date(2026, 11, 1),
        reserve_floor_paise=500000,
        income_rules=(
            {
                "amount_paise": 3000000,
                "due_date": date(2026, 11, 7),
                "frequency": "monthly",
                "timing": "known",
                "category": "salary",
            },
        ),
        expense_rules=(
            {
                "amount_paise": 800000,
                "due_date": date(2026, 11, 3),
                "frequency": "monthly",
                "category": "rent",
            },
        ),
        obligations=(),
        goals=(),
        data_version=1,
    )

    scenario = ScenarioInput(
        expense_amount_paise=1000000,
        expense_date=date(2026, 11, 1),
        need_cash=False,
        allowed_savings_paise=0,
        horizon_days=30,
        offers=(
            {
                "offer_id": "bnpl-plan",
                "offer_type": "bnpl",
                "principal_paise": 1000000,
                "fees_paise": 0,
                "rate_annual_pct": "0.00",
                "term_months": 2,
            },
        ),
    )

    # 1. Feasible run with savings bounds
    cf_res = search_changes(
        snapshot,
        scenario,
        bounds={
            "max_savings_paise": 1000000,
            "min_savings_paise": 0,
        },
    )

    validated = CounterfactualOut.model_validate(cf_res)
    assert validated.tested_count > 0
    assert validated.insufficient_data is False
    assert isinstance(validated.feasible, list)
    assert len(validated.feasible) <= 3

    if validated.feasible:
        top = validated.feasible[0]
        assert isinstance(top.description, str)
        assert isinstance(top.changes, dict)
        assert isinstance(top.user_changes_count, int)
        assert isinstance(top.goal_impacts, list)

    # 2. Canonical serialization of CounterfactualOut
    dumped_json = to_canonical_json(validated)
    assert '"tested_count":' in dumped_json
    assert '"no_feasible_plan":' in dumped_json

    # 3. Insufficient data run
    bad_snapshot = FinancialSnapshot(
        opening_cash_paise=1000000,
        balance_as_of=date(2026, 11, 1),
        reserve_floor_paise=200000,
        income_rules=(
            {
                "amount_paise": 2000000,
                "due_date": None,
                "timing": "estimated",
            },
        ),
        expense_rules=(),
        obligations=(),
        goals=(),
        data_version=1,
    )

    bad_cf_res = search_changes(bad_snapshot, scenario, bounds={})
    bad_validated = CounterfactualOut.model_validate(bad_cf_res)
    assert bad_validated.insufficient_data is True
    assert bad_validated.no_feasible_plan is True
    assert len(bad_validated.missing_fields) > 0
    assert len(bad_validated.evidence) > 0
    assert bad_validated.evidence[0].code == "INSUFFICIENT_DATA"
