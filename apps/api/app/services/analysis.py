from datetime import datetime, timezone
import json
from typing import Any, Sequence
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.engine.analyze import analyze
from app.engine.counterfactuals import search_changes
from app.engine.policy import DEFAULT_POLICY
from app.engine.serialization import hash_snapshot, to_canonical_json
from app.engine.types import ScenarioInput
from app.models.decisions import Analysis, Offer, Scenario
from app.models.finance import Profile
from app.schemas.decisions import (
    AnalysisOut,
    AnalyzeRequest,
    CounterfactualOut,
    CounterfactualRequest,
)
from app.services.snapshot import (
    InvalidFinancialDataError,
    MissingProfileError,
    load_financial_snapshot,
)


class AnalysisServiceError(Exception):
    """Base exception for analysis service errors."""
    pass


class ScenarioNotFoundError(AnalysisServiceError):
    """Raised when a scenario is not found or not owned by the current user."""
    pass


class AnalysisNotFoundError(AnalysisServiceError):
    """Raised when an analysis record is not found or not owned by the current user."""
    pass


class AnalysisMismatchError(AnalysisServiceError):
    """Raised when an analysis record does not match the requested scenario."""
    pass


class VersionConflictError(AnalysisServiceError):
    """Raised when a scenario or financial data version conflict occurs."""
    pass


class StaleAnalysisError(AnalysisServiceError):
    """Raised when counterfactual analysis is attempted on an outdated analysis."""
    pass


class InvalidOfferError(AnalysisServiceError):
    """Raised when an offer contains invalid or malformed data."""
    pass


def map_offer_to_dict(offer: Offer) -> dict[str, Any]:
    """
    Validates and maps an Offer ORM model into a dictionary suitable for engine normalization.
    Preserves exact paise, rate string, term, dates, and schedule JSON without loss.
    """
    if offer.principal_paise < 0:
        raise InvalidOfferError(f"Offer {offer.id} principal cannot be negative: {offer.principal_paise}")
    if offer.fees_paise < 0:
        raise InvalidOfferError(f"Offer {offer.id} fees cannot be negative: {offer.fees_paise}")

    schedule_data = None
    if offer.schedule_json:
        try:
            schedule_data = json.loads(offer.schedule_json)
            if not isinstance(schedule_data, list):
                raise ValueError("Schedule JSON must be a list of payment objects")
        except Exception as e:
            raise InvalidOfferError(f"Offer {offer.id} has invalid schedule_json: {e}")

    return {
        "id": str(offer.id),
        "offer_id": str(offer.id),
        "offer_type": str(offer.offer_type).lower().strip(),
        "principal_paise": int(offer.principal_paise),
        "fees_paise": int(offer.fees_paise or 0),
        "rate_annual_pct": str(offer.rate_annual_pct or "0.00").strip(),
        "term_months": int(offer.term_months) if offer.term_months is not None else None,
        "availability_deadline": offer.availability_deadline,
        "eligibility_evidence": offer.eligibility_evidence,
        "schedule_json": offer.schedule_json,
        "schedule": schedule_data,
    }


def build_scenario_input(
    scenario: Scenario,
    offers: Sequence[Offer] | None = None,
) -> ScenarioInput:
    """
    Converts a Scenario ORM record and its related Offer records into an immutable ScenarioInput.
    """
    if scenario.expense_amount_paise <= 0:
        raise InvalidOfferError(f"expense_amount_paise must be positive: {scenario.expense_amount_paise}")
    if scenario.expense_date is None:
        raise InvalidOfferError("expense_date is required")

    offer_records = offers if offers is not None else getattr(scenario, "offers", ()) or ()
    mapped_offers = tuple(map_offer_to_dict(o) for o in offer_records)

    return ScenarioInput(
        expense_amount_paise=int(scenario.expense_amount_paise),
        expense_date=scenario.expense_date,
        need_cash=bool(scenario.need_cash),
        allowed_savings_paise=int(scenario.allowed_savings_paise or 0),
        horizon_days=int(scenario.horizon_days) if scenario.horizon_days > 0 else DEFAULT_POLICY.default_horizon_days,
        offers=mapped_offers,
    )


async def run_scenario_analysis(
    db: AsyncSession,
    scenario_id: uuid.UUID,
    user_id: uuid.UUID,
    request: AnalyzeRequest,
    commit: bool = True,
) -> AnalysisOut:
    """
    Executes scenario analysis and persists an immutable Analysis record.

    Behavior:
    1. Loads scenario scoped to owner_id. Raises ScenarioNotFoundError if absent or foreign-owned.
    2. Compares request.scenario_version with Scenario.version. Raises VersionConflictError on mismatch.
    3. Loads user FinancialSnapshot. Compares request.expected_data_version with snapshot.data_version.
    4. Converts ORM models to engine inputs.
    5. Calls pure analyze() function.
    6. Produces canonical JSON and SHA-256 snapshot hash.
    7. Atomically persists a new Analysis row (never updates old rows).
    """
    owner_id = user_id if isinstance(user_id, uuid.UUID) else user_id.id

    stmt = (
        select(Scenario)
        .where(Scenario.id == scenario_id, Scenario.owner_id == owner_id)
        .options(selectinload(Scenario.offers))
    )
    res = await db.execute(stmt)
    scenario = res.scalar_one_or_none()

    if not scenario:
        raise ScenarioNotFoundError(f"Scenario {scenario_id} not found for user {owner_id}")

    if request.scenario_version != scenario.version:
        raise VersionConflictError(
            f"Scenario version mismatch: requested {request.scenario_version}, current {scenario.version}"
        )

    snapshot = await load_financial_snapshot(db, owner_id)

    if request.expected_data_version != snapshot.data_version:
        raise VersionConflictError(
            f"Financial data version mismatch: expected {request.expected_data_version}, current {snapshot.data_version}"
        )

    scenario_input = build_scenario_input(scenario, scenario.offers)

    # Pure calculation
    result = analyze(snapshot, scenario_input, DEFAULT_POLICY)

    # Canonical serialization
    input_payload = {
        "scenario": scenario_input,
        "snapshot": snapshot,
        "stress_cases": request.stress_cases,
    }
    input_json = to_canonical_json(input_payload)
    result_json = to_canonical_json(result)
    snap_hash = hash_snapshot(snapshot)

    analysis_id = uuid.uuid4()
    analysis = Analysis(
        id=analysis_id,
        scenario_id=scenario.id,
        owner_id=owner_id,
        input_json=input_json,
        result_json=result_json,
        snapshot_hash=snap_hash,
        model_version=DEFAULT_POLICY.model_version,
        source_data_version=snapshot.data_version,
        scenario_version=scenario.version,
        calculated_at=datetime.now(timezone.utc),
    )

    try:
        db.add(analysis)
        if commit:
            await db.commit()
            await db.refresh(analysis)
        else:
            await db.flush()
    except Exception:
        if commit:
            await db.rollback()
        raise

    return AnalysisOut(
        id=analysis.id,
        scenario_id=analysis.scenario_id,
        result_json=analysis.result_json,
        model_version=analysis.model_version,
        source_data_version=analysis.source_data_version,
        calculated_at=analysis.calculated_at,
        stale=False,
        snapshot_hash=analysis.snapshot_hash,
    )


async def get_analysis(
    db: AsyncSession,
    analysis_id: uuid.UUID,
    user_id: uuid.UUID,
) -> AnalysisOut:
    """
    Retrieves a stored Analysis record by ID, enforcing strict owner isolation.
    Dynamically checks whether the analysis is stale by comparing stored versions
    against the current Scenario and Profile states.
    Never mutates or recomputes the immutable database row.
    """
    owner_id = user_id if isinstance(user_id, uuid.UUID) else user_id.id

    stmt = select(Analysis).where(Analysis.id == analysis_id, Analysis.owner_id == owner_id)
    res = await db.execute(stmt)
    analysis = res.scalar_one_or_none()

    if not analysis:
        raise AnalysisNotFoundError(f"Analysis {analysis_id} not found for user {owner_id}")

    # Check current scenario version
    stmt_scen = select(Scenario.version).where(Scenario.id == analysis.scenario_id)
    scen_res = await db.execute(stmt_scen)
    current_scen_version = scen_res.scalar_one_or_none()

    # Check current profile data_version
    stmt_prof = select(Profile.data_version).where(Profile.owner_id == owner_id)
    prof_res = await db.execute(stmt_prof)
    current_data_version = prof_res.scalar_one_or_none()

    is_stale = False
    if current_scen_version is None or current_scen_version != analysis.scenario_version:
        is_stale = True
    if current_data_version is None or current_data_version != analysis.source_data_version:
        is_stale = True

    return AnalysisOut(
        id=analysis.id,
        scenario_id=analysis.scenario_id,
        result_json=analysis.result_json,
        model_version=analysis.model_version,
        source_data_version=analysis.source_data_version,
        calculated_at=analysis.calculated_at,
        stale=is_stale,
        snapshot_hash=analysis.snapshot_hash,
    )


async def run_counterfactual_analysis(
    db: AsyncSession,
    scenario_id: uuid.UUID,
    user_id: uuid.UUID,
    request: CounterfactualRequest,
) -> CounterfactualOut:
    """
    Executes bounded counterfactual search for a scenario and validated analysis.

    Enforces:
    - Strict scenario and analysis ownership.
    - Matching scenario_id between path and request.analysis_id.
    - Rejection of stale analyses.
    - Delegation to engine search_changes() without mutating database records.
    """
    owner_id = user_id if isinstance(user_id, uuid.UUID) else user_id.id

    # 1. Load scenario
    stmt_scen = (
        select(Scenario)
        .where(Scenario.id == scenario_id, Scenario.owner_id == owner_id)
        .options(selectinload(Scenario.offers))
    )
    scen_res = await db.execute(stmt_scen)
    scenario = scen_res.scalar_one_or_none()
    if not scenario:
        raise ScenarioNotFoundError(f"Scenario {scenario_id} not found for user {owner_id}")

    # 2. Load analysis
    stmt_an = select(Analysis).where(Analysis.id == request.analysis_id, Analysis.owner_id == owner_id)
    an_res = await db.execute(stmt_an)
    analysis = an_res.scalar_one_or_none()
    if not analysis:
        raise AnalysisNotFoundError(f"Analysis {request.analysis_id} not found for user {owner_id}")

    if analysis.scenario_id != scenario.id:
        raise AnalysisMismatchError(
            f"Analysis {request.analysis_id} does not belong to scenario {scenario.id}"
        )

    # 3. Load snapshot
    snapshot = await load_financial_snapshot(db, owner_id)

    # 4. Check staleness
    if analysis.scenario_version != scenario.version:
        raise StaleAnalysisError(
            f"Analysis scenario_version {analysis.scenario_version} != current scenario version {scenario.version}"
        )
    if analysis.source_data_version != snapshot.data_version:
        raise StaleAnalysisError(
            f"Analysis source_data_version {analysis.source_data_version} != current data version {snapshot.data_version}"
        )

    # 5. Build scenario input and bounds
    scenario_input = build_scenario_input(scenario, scenario.offers)
    bounds = dict(request.bounds or {})
    if request.allowed_changes:
        bounds["allowed_changes"] = list(request.allowed_changes)

    # 6. Execute engine search
    alternatives = search_changes(snapshot, scenario_input, bounds=bounds)

    # 7. Validate and return schema
    return CounterfactualOut.model_validate(alternatives)
