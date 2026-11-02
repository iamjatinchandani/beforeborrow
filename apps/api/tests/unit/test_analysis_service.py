from datetime import date, datetime, timezone
import json
from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models.decisions import Analysis, Offer, Scenario
from app.models.finance import CashflowRule, Profile
from app.models.identity import User
from app.schemas.decisions import (
    AnalyzeRequest,
    AnalysisOut,
    CounterfactualOut,
    CounterfactualRequest,
)
from app.services.analysis import (
    AnalysisNotFoundError,
    AnalysisMismatchError,
    InvalidOfferError,
    ScenarioNotFoundError,
    StaleAnalysisError,
    VersionConflictError,
    get_analysis,
    run_counterfactual_analysis,
    run_scenario_analysis,
)
from app.services.snapshot import MissingProfileError


@pytest_asyncio.fixture
async def db_session():
    """Sets up an in-memory SQLite database and yields an AsyncSession."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


async def _create_test_user_and_profile(
    db: AsyncSession,
    user_id: uuid.UUID | None = None,
    data_version: int = 1,
) -> tuple[User, Profile]:
    uid = user_id or uuid.uuid4()
    user = User(
        id=uid,
        email_normalized=f"user_{uid.hex[:8]}@example.com",
        password_hash="fake_hash",
    )
    profile = Profile(
        id=uuid.uuid4(),
        owner_id=uid,
        opening_cash_paise=2400000,
        balance_as_of=date(2026, 11, 1),
        reserve_floor_paise=500000,
        data_version=data_version,
    )
    income_rule = CashflowRule(
        id=uuid.uuid4(),
        owner_id=uid,
        direction="income",
        category="salary",
        amount_paise=3000000,
        due_date=date(2026, 11, 7),
        frequency="monthly",
        timing="known",
    )
    db.add_all([user, profile, income_rule])
    await db.commit()
    return user, profile


async def _create_test_scenario(
    db: AsyncSession,
    owner_id: uuid.UUID,
    version: int = 1,
    with_offer: bool = True,
) -> Scenario:
    scen_id = uuid.uuid4()
    scenario = Scenario(
        id=scen_id,
        owner_id=owner_id,
        expense_amount_paise=1000000,
        expense_date=date(2026, 11, 20),
        need_cash=False,
        allowed_savings_paise=200000,
        horizon_days=90,
        version=version,
    )
    db.add(scenario)

    if with_offer:
        offer = Offer(
            id=uuid.uuid4(),
            scenario_id=scen_id,
            offer_type="bnpl",
            principal_paise=800000,
            fees_paise=0,
            rate_annual_pct="0.00",
            term_months=2,
            availability_deadline=date(2026, 11, 20),
        )
        db.add(offer)

    await db.commit()
    return scenario


@pytest.mark.asyncio
async def test_successful_analysis_creation_and_persisted_fields(db_session: AsyncSession):
    """1. Validates successful analysis execution and persisted DB record fields."""
    user, profile = await _create_test_user_and_profile(db_session)
    scenario = await _create_test_scenario(db_session, user.id, version=1)

    req = AnalyzeRequest(scenario_version=1, expected_data_version=1, stress_cases=[])
    out = await run_scenario_analysis(db_session, scenario.id, user.id, req)

    assert isinstance(out, AnalysisOut)
    assert out.scenario_id == scenario.id
    assert out.model_version == "rules-v1"
    assert out.source_data_version == 1
    assert out.stale is False

    # Check database persistence
    stmt = select(Analysis).where(Analysis.id == out.id)
    persisted = (await db_session.execute(stmt)).scalar_one_or_none()
    assert persisted is not None
    assert persisted.scenario_id == scenario.id
    assert persisted.owner_id == user.id
    assert len(persisted.snapshot_hash) == 64
    assert persisted.scenario_version == 1
    assert persisted.source_data_version == 1
    assert "baseline" in persisted.result_json
    assert out.snapshot_hash is not None
    assert len(out.snapshot_hash) == 64
    assert out.snapshot_hash == persisted.snapshot_hash


@pytest.mark.asyncio
async def test_scenario_not_found(db_session: AsyncSession):
    """2. Requesting analysis for an absent scenario raises ScenarioNotFoundError."""
    user, _ = await _create_test_user_and_profile(db_session)
    req = AnalyzeRequest(scenario_version=1, expected_data_version=1)

    with pytest.raises(ScenarioNotFoundError, match="not found"):
        await run_scenario_analysis(db_session, uuid.uuid4(), user.id, req)


@pytest.mark.asyncio
async def test_foreign_owned_scenario_returns_not_found(db_session: AsyncSession):
    """3. Requesting analysis on another user's scenario raises ScenarioNotFoundError (no leakage)."""
    user1, _ = await _create_test_user_and_profile(db_session)
    user2, _ = await _create_test_user_and_profile(db_session)
    scenario_user1 = await _create_test_scenario(db_session, user1.id)

    req = AnalyzeRequest(scenario_version=1, expected_data_version=1)
    with pytest.raises(ScenarioNotFoundError):
        await run_scenario_analysis(db_session, scenario_user1.id, user2.id, req)


@pytest.mark.asyncio
async def test_scenario_version_mismatch(db_session: AsyncSession):
    """4. Stale scenario version in AnalyzeRequest triggers VersionConflictError."""
    user, _ = await _create_test_user_and_profile(db_session)
    scenario = await _create_test_scenario(db_session, user.id, version=2)

    req = AnalyzeRequest(scenario_version=1, expected_data_version=1)
    with pytest.raises(VersionConflictError, match="Scenario version mismatch"):
        await run_scenario_analysis(db_session, scenario.id, user.id, req)


@pytest.mark.asyncio
async def test_snapshot_data_version_mismatch(db_session: AsyncSession):
    """5. Stale expected_data_version in AnalyzeRequest triggers VersionConflictError."""
    user, _ = await _create_test_user_and_profile(db_session, data_version=5)
    scenario = await _create_test_scenario(db_session, user.id, version=1)

    req = AnalyzeRequest(scenario_version=1, expected_data_version=4)
    with pytest.raises(VersionConflictError, match="Financial data version mismatch"):
        await run_scenario_analysis(db_session, scenario.id, user.id, req)


@pytest.mark.asyncio
async def test_missing_profile(db_session: AsyncSession):
    """6. Attempting to analyze when profile is missing raises MissingProfileError."""
    user_id = uuid.uuid4()
    db_session.add(User(id=user_id, email_normalized="noprof@example.com", password_hash="hash"))
    await db_session.commit()

    scenario = await _create_test_scenario(db_session, user_id, version=1)
    req = AnalyzeRequest(scenario_version=1, expected_data_version=1)

    with pytest.raises(MissingProfileError):
        await run_scenario_analysis(db_session, scenario.id, user_id, req)


@pytest.mark.asyncio
async def test_invalid_offer_mapping(db_session: AsyncSession):
    """7. Malformed offer data raises InvalidOfferError."""
    user, _ = await _create_test_user_and_profile(db_session)
    scen = await _create_test_scenario(db_session, user.id, with_offer=False)

    # Bad offer with negative principal
    bad_offer = Offer(
        id=uuid.uuid4(),
        scenario_id=scen.id,
        offer_type="term_loan",
        principal_paise=-500,
        rate_annual_pct="12.00",
    )
    db_session.add(bad_offer)
    await db_session.commit()

    req = AnalyzeRequest(scenario_version=1, expected_data_version=1)
    with pytest.raises(InvalidOfferError, match="principal cannot be negative"):
        await run_scenario_analysis(db_session, scen.id, user.id, req)


@pytest.mark.asyncio
async def test_canonical_input_result_json_and_64char_sha256(db_session: AsyncSession):
    """8. Verifies canonical JSON serialization and exactly 64-character SHA-256 hash."""
    user, _ = await _create_test_user_and_profile(db_session)
    scenario = await _create_test_scenario(db_session, user.id)

    req = AnalyzeRequest(scenario_version=1, expected_data_version=1)
    out = await run_scenario_analysis(db_session, scenario.id, user.id, req)

    stmt = select(Analysis).where(Analysis.id == out.id)
    persisted = (await db_session.execute(stmt)).scalar_one()

    # Hash verification
    assert len(persisted.snapshot_hash) == 64
    assert all(c in "0123456789abcdef" for c in persisted.snapshot_hash)

    # Canonical JSON verification
    assert ": " not in persisted.result_json
    assert ", " not in persisted.result_json
    parsed_res = json.loads(persisted.result_json)
    assert parsed_res["model_version"] == "rules-v1"

    parsed_in = json.loads(persisted.input_json)
    assert "scenario" in parsed_in
    assert "snapshot" in parsed_in


@pytest.mark.asyncio
async def test_new_analysis_on_each_valid_run_prior_unchanged(db_session: AsyncSession):
    """9. Successive runs create new immutable Analysis rows without overwriting prior records."""
    user, _ = await _create_test_user_and_profile(db_session)
    scenario = await _create_test_scenario(db_session, user.id)

    req = AnalyzeRequest(scenario_version=1, expected_data_version=1)
    out1 = await run_scenario_analysis(db_session, scenario.id, user.id, req)
    out2 = await run_scenario_analysis(db_session, scenario.id, user.id, req)

    assert out1.id != out2.id

    stmt = select(Analysis).where(Analysis.scenario_id == scenario.id)
    all_analyses = (await db_session.execute(stmt)).scalars().all()
    assert len(all_analyses) == 2
    ids = {a.id for a in all_analyses}
    assert out1.id in ids
    assert out2.id in ids


@pytest.mark.asyncio
async def test_get_analysis_ownership_isolation(db_session: AsyncSession):
    """10. Foreign user cannot retrieve another user's analysis record."""
    user1, _ = await _create_test_user_and_profile(db_session)
    user2, _ = await _create_test_user_and_profile(db_session)
    scenario = await _create_test_scenario(db_session, user1.id)

    req = AnalyzeRequest(scenario_version=1, expected_data_version=1)
    out = await run_scenario_analysis(db_session, scenario.id, user1.id, req)

    # User 1 succeeds
    fetched = await get_analysis(db_session, out.id, user1.id)
    assert fetched.id == out.id
    assert fetched.snapshot_hash == out.snapshot_hash
    assert len(fetched.snapshot_hash) == 64

    # User 2 fails with AnalysisNotFoundError (no leakage)
    with pytest.raises(AnalysisNotFoundError):
        await get_analysis(db_session, out.id, user2.id)


@pytest.mark.asyncio
async def test_get_analysis_returns_stale_true_after_scenario_version_changes(db_session: AsyncSession):
    """11. When scenario version increments, GET analysis dynamically reflects stale=True."""
    user, _ = await _create_test_user_and_profile(db_session)
    scenario = await _create_test_scenario(db_session, user.id, version=1)

    req = AnalyzeRequest(scenario_version=1, expected_data_version=1)
    out = await run_scenario_analysis(db_session, scenario.id, user.id, req)
    assert out.stale is False

    # Simulate scenario edit
    scenario.version = 2
    await db_session.commit()

    fetched = await get_analysis(db_session, out.id, user.id)
    assert fetched.stale is True


@pytest.mark.asyncio
async def test_get_analysis_returns_stale_true_after_profile_data_version_changes(db_session: AsyncSession):
    """12. When profile data_version increments, GET analysis dynamically reflects stale=True."""
    user, profile = await _create_test_user_and_profile(db_session, data_version=1)
    scenario = await _create_test_scenario(db_session, user.id, version=1)

    req = AnalyzeRequest(scenario_version=1, expected_data_version=1)
    out = await run_scenario_analysis(db_session, scenario.id, user.id, req)
    assert out.stale is False

    # Simulate financial mutation
    profile.data_version = 2
    await db_session.commit()

    fetched = await get_analysis(db_session, out.id, user.id)
    assert fetched.stale is True


@pytest.mark.asyncio
async def test_counterfactual_analysis_id_must_belong_to_same_scenario_and_owner(db_session: AsyncSession):
    """13. Counterfactual rejects analysis_id belonging to a different scenario."""
    user, _ = await _create_test_user_and_profile(db_session)
    scen1 = await _create_test_scenario(db_session, user.id)
    scen2 = await _create_test_scenario(db_session, user.id)

    req = AnalyzeRequest(scenario_version=1, expected_data_version=1)
    out1 = await run_scenario_analysis(db_session, scen1.id, user.id, req)

    # Attempt to request counterfactual for scen2 using analysis of scen1
    cf_req = CounterfactualRequest(
        analysis_id=out1.id,
        allowed_changes=["savings"],
        bounds={"max_savings_paise": 500000},
    )
    with pytest.raises(AnalysisMismatchError, match="does not belong to scenario"):
        await run_counterfactual_analysis(db_session, scen2.id, user.id, cf_req)


@pytest.mark.asyncio
async def test_counterfactual_rejects_stale_analysis(db_session: AsyncSession):
    """14. Counterfactual request on stale analysis raises StaleAnalysisError."""
    user, profile = await _create_test_user_and_profile(db_session, data_version=1)
    scenario = await _create_test_scenario(db_session, user.id, version=1)

    req = AnalyzeRequest(scenario_version=1, expected_data_version=1)
    out = await run_scenario_analysis(db_session, scenario.id, user.id, req)

    # Bump scenario version
    scenario.version = 2
    await db_session.commit()

    cf_req = CounterfactualRequest(
        analysis_id=out.id,
        allowed_changes=["savings"],
        bounds={"max_savings_paise": 500000},
    )
    with pytest.raises(StaleAnalysisError):
        await run_counterfactual_analysis(db_session, scenario.id, user.id, cf_req)


@pytest.mark.asyncio
async def test_counterfactual_response_validates_against_counterfactual_out(db_session: AsyncSession):
    """15. run_counterfactual_analysis returns a fully validated CounterfactualOut."""
    user, _ = await _create_test_user_and_profile(db_session)
    scenario = await _create_test_scenario(db_session, user.id)

    req = AnalyzeRequest(scenario_version=1, expected_data_version=1)
    out = await run_scenario_analysis(db_session, scenario.id, user.id, req)

    cf_req = CounterfactualRequest(
        analysis_id=out.id,
        allowed_changes=["savings"],
        bounds={"max_savings_paise": 500000, "min_savings_paise": 0},
    )
    cf_res = await run_counterfactual_analysis(db_session, scenario.id, user.id, cf_req)

    assert isinstance(cf_res, CounterfactualOut)
    assert cf_res.tested_count > 0
    assert isinstance(cf_res.feasible, list)


@pytest.mark.asyncio
async def test_failed_analysis_does_not_persist_partial_record(db_session: AsyncSession):
    """16. A failed analysis does not persist any partial row in the database."""
    user, _ = await _create_test_user_and_profile(db_session)
    scenario = await _create_test_scenario(db_session, user.id, version=1)

    # Pass mismatched version to trigger exception inside service
    req = AnalyzeRequest(scenario_version=999, expected_data_version=1)
    with pytest.raises(VersionConflictError):
        await run_scenario_analysis(db_session, scenario.id, user.id, req)

    # Verify no analyses exist
    stmt = select(Analysis).where(Analysis.scenario_id == scenario.id)
    records = (await db_session.execute(stmt)).scalars().all()
    assert len(records) == 0


@pytest.mark.asyncio
async def test_get_analysis_handles_null_snapshot_hash():
    """17. If an Analysis record has a null snapshot_hash, get_analysis returns None without error."""
    mock_analysis = MagicMock()
    mock_analysis.id = uuid.uuid4()
    mock_analysis.scenario_id = uuid.uuid4()
    mock_analysis.result_json = "{}"
    mock_analysis.model_version = "rules-v1"
    mock_analysis.source_data_version = 1
    mock_analysis.scenario_version = 1
    mock_analysis.calculated_at = datetime.now(timezone.utc)
    mock_analysis.snapshot_hash = None

    mock_db = MagicMock(spec=AsyncSession)
    res_analysis = MagicMock()
    res_analysis.scalar_one_or_none.return_value = mock_analysis

    res_scen = MagicMock()
    res_scen.scalar_one_or_none.return_value = 1

    res_prof = MagicMock()
    res_prof.scalar_one_or_none.return_value = 1

    mock_db.execute = AsyncMock(side_effect=[res_analysis, res_scen, res_prof])

    owner_id = uuid.uuid4()
    out = await get_analysis(mock_db, mock_analysis.id, owner_id)
    assert out.id == mock_analysis.id
    assert out.snapshot_hash is None
