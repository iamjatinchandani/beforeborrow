from datetime import date, datetime, timezone
import uuid
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.engine.analyze import analyze, check_blocking_data_gaps
from app.engine.policy import DEFAULT_POLICY
from app.engine.schedules import expand_rules
from app.engine.types import FinancialSnapshot, ScenarioInput
from app.models.finance import (
    CashflowRule,
    Goal,
    Obligation,
    ObligationPayment,
    Profile,
)
from app.models.identity import User
from app.services.snapshot import (
    InvalidFinancialDataError,
    MissingProfileError,
    build_financial_snapshot,
    load_financial_snapshot,
)


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


@pytest.mark.asyncio
async def test_correct_mapping_populated_profile_and_all_records(db_session: AsyncSession):
    """Verifies that all finance models map to the exact FinancialSnapshot structure."""
    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        email_normalized="tester@example.com",
        password_hash="argon2_fake_hash",
    )
    db_session.add(user)

    profile = Profile(
        id=uuid.uuid4(),
        owner_id=user_id,
        currency="INR",
        timezone="Asia/Kolkata",
        opening_cash_paise=2400000,
        balance_as_of=date(2026, 11, 1),
        reserve_floor_paise=500000,
        data_version=3,
    )
    db_session.add(profile)

    income_rule = CashflowRule(
        id=uuid.uuid4(),
        owner_id=user_id,
        direction="income",
        category="salary",
        amount_paise=3000000,
        due_date=date(2026, 11, 7),
        frequency="monthly",
        timing="known",
        source="manual",
    )
    expense_rule = CashflowRule(
        id=uuid.uuid4(),
        owner_id=user_id,
        direction="expense",
        category="rent",
        amount_paise=800000,
        due_date=date(2026, 11, 3),
        frequency="monthly",
        timing="known",
        source="manual",
    )
    db_session.add_all([income_rule, expense_rule])

    ob_id = uuid.uuid4()
    obligation = Obligation(
        id=ob_id,
        owner_id=user_id,
        provider_alias="Bank Loan",
        kind="term_loan",
        principal_remaining_paise=4800000,
        status="active",
        source="manual",
        version=1,
    )
    db_session.add(obligation)

    p1 = ObligationPayment(
        id=uuid.uuid4(),
        obligation_id=ob_id,
        due_date=date(2026, 11, 5),
        amount_paise=400000,
        interest_paise=50000,
        fee_paise=0,
        payment_status="scheduled",
    )
    p2 = ObligationPayment(
        id=uuid.uuid4(),
        obligation_id=ob_id,
        due_date=date(2026, 10, 5),
        amount_paise=400000,
        interest_paise=50000,
        fee_paise=0,
        payment_status="paid",
        actual_paid_date=date(2026, 10, 5),
    )
    db_session.add_all([p1, p2])

    goal = Goal(
        id=uuid.uuid4(),
        owner_id=user_id,
        label="Emergency Fund Goal",
        target_amount_paise=10000000,
        target_date=date(2027, 5, 1),
        protected=True,
    )
    db_session.add(goal)
    await db_session.commit()

    # Load snapshot
    snapshot = await load_financial_snapshot(db_session, user_id)

    assert isinstance(snapshot, FinancialSnapshot)
    assert snapshot.opening_cash_paise == 2400000
    assert snapshot.balance_as_of == date(2026, 11, 1)
    assert snapshot.reserve_floor_paise == 500000
    assert snapshot.data_version == 3

    # Cashflow rules partitioned by direction
    assert len(snapshot.income_rules) == 1
    assert snapshot.income_rules[0]["category"] == "salary"
    assert snapshot.income_rules[0]["amount_paise"] == 3000000
    assert snapshot.income_rules[0]["due_date"] == date(2026, 11, 7)
    assert snapshot.income_rules[0]["timing"] == "known"

    assert len(snapshot.expense_rules) == 1
    assert snapshot.expense_rules[0]["category"] == "rent"
    assert snapshot.expense_rules[0]["amount_paise"] == 800000

    # Obligations and payments
    assert len(snapshot.obligations) == 1
    assert snapshot.obligations[0]["provider_alias"] == "Bank Loan"
    assert snapshot.obligations[0]["kind"] == "term_loan"
    assert len(snapshot.obligations[0]["payments"]) == 2
    statuses = {p["payment_status"] for p in snapshot.obligations[0]["payments"]}
    assert statuses == {"scheduled", "paid"}

    # Goals
    assert len(snapshot.goals) == 1
    assert snapshot.goals[0]["label"] == "Emergency Fund Goal"
    assert snapshot.goals[0]["protected"] is True


@pytest.mark.asyncio
async def test_owner_isolation(db_session: AsyncSession):
    """Verifies that user data is strictly isolated; no cross-user records appear."""
    user1_id = uuid.uuid4()
    user2_id = uuid.uuid4()

    db_session.add_all([
        User(id=user1_id, email_normalized="user1@example.com", password_hash="hash1"),
        User(id=user2_id, email_normalized="user2@example.com", password_hash="hash2"),
        Profile(
            id=uuid.uuid4(),
            owner_id=user1_id,
            opening_cash_paise=1000000,
            balance_as_of=date(2026, 11, 1),
            reserve_floor_paise=200000,
            data_version=1,
        ),
        Profile(
            id=uuid.uuid4(),
            owner_id=user2_id,
            opening_cash_paise=9000000,
            balance_as_of=date(2026, 11, 1),
            reserve_floor_paise=800000,
            data_version=5,
        ),
        CashflowRule(
            id=uuid.uuid4(),
            owner_id=user1_id,
            direction="income",
            category="user1_income",
            amount_paise=500000,
            due_date=date(2026, 11, 10),
        ),
        CashflowRule(
            id=uuid.uuid4(),
            owner_id=user2_id,
            direction="income",
            category="user2_income",
            amount_paise=700000,
            due_date=date(2026, 11, 10),
        ),
    ])
    await db_session.commit()

    snap1 = await load_financial_snapshot(db_session, user1_id)
    snap2 = await load_financial_snapshot(db_session, user2_id)

    assert snap1.opening_cash_paise == 1000000
    assert snap1.data_version == 1
    assert len(snap1.income_rules) == 1
    assert snap1.income_rules[0]["category"] == "user1_income"

    assert snap2.opening_cash_paise == 9000000
    assert snap2.data_version == 5
    assert len(snap2.income_rules) == 1
    assert snap2.income_rules[0]["category"] == "user2_income"


@pytest.mark.asyncio
async def test_empty_collections(db_session: AsyncSession):
    """A profile with no rules, obligations, or goals yields empty tuples."""
    user_id = uuid.uuid4()
    db_session.add(User(id=user_id, email_normalized="empty@example.com", password_hash="hash"))
    db_session.add(Profile(
        id=uuid.uuid4(),
        owner_id=user_id,
        opening_cash_paise=500000,
        balance_as_of=date(2026, 11, 1),
        reserve_floor_paise=100000,
        data_version=1,
    ))
    await db_session.commit()

    snapshot = await load_financial_snapshot(db_session, user_id)
    assert snapshot.income_rules == ()
    assert snapshot.expense_rules == ()
    assert snapshot.obligations == ()
    assert snapshot.goals == ()
    assert snapshot.opening_cash_paise == 500000


@pytest.mark.asyncio
async def test_missing_profile_raises_error(db_session: AsyncSession):
    """Querying snapshot for an uninitialized user raises MissingProfileError."""
    unknown_user = uuid.uuid4()
    with pytest.raises(MissingProfileError, match="No financial profile found"):
        await load_financial_snapshot(db_session, unknown_user)


@pytest.mark.asyncio
async def test_missing_or_estimated_timing_preserved(db_session: AsyncSession):
    """Estimated timing is preserved and recognized as blocking by check_blocking_data_gaps."""
    user_id = uuid.uuid4()
    db_session.add(User(id=user_id, email_normalized="est@example.com", password_hash="hash"))
    db_session.add(Profile(
        id=uuid.uuid4(),
        owner_id=user_id,
        opening_cash_paise=500000,
        balance_as_of=date(2026, 11, 1),
        reserve_floor_paise=100000,
        data_version=1,
    ))
    db_session.add(CashflowRule(
        id=uuid.uuid4(),
        owner_id=user_id,
        direction="income",
        category="freelance",
        amount_paise=1000000,
        due_date=None,
        timing="estimated",
    ))
    await db_session.commit()

    snapshot = await load_financial_snapshot(db_session, user_id)
    assert snapshot.income_rules[0]["timing"] == "estimated"

    # Engine must detect blocking gap
    has_gap, fields = check_blocking_data_gaps(snapshot)
    assert has_gap is True
    assert "income_timing" in fields


@pytest.mark.asyncio
async def test_integer_paise_preservation(db_session: AsyncSession):
    """Monetary values must remain exact integer types."""
    user_id = uuid.uuid4()
    db_session.add(User(id=user_id, email_normalized="paise@example.com", password_hash="hash"))
    db_session.add(Profile(
        id=uuid.uuid4(),
        owner_id=user_id,
        opening_cash_paise=123_456_789,
        balance_as_of=date(2026, 11, 1),
        reserve_floor_paise=98_765_432,
        data_version=1,
    ))
    db_session.add(CashflowRule(
        id=uuid.uuid4(),
        owner_id=user_id,
        direction="income",
        category="contract",
        amount_paise=50_000_000,
        due_date=date(2026, 11, 15),
    ))
    await db_session.commit()

    snapshot = await load_financial_snapshot(db_session, user_id)
    assert type(snapshot.opening_cash_paise) is int
    assert snapshot.opening_cash_paise == 123_456_789
    assert type(snapshot.reserve_floor_paise) is int
    assert snapshot.reserve_floor_paise == 98_765_432
    assert type(snapshot.income_rules[0]["amount_paise"]) is int
    assert snapshot.income_rules[0]["amount_paise"] == 50_000_000


@pytest.mark.asyncio
async def test_snapshot_data_version_matches_profile(db_session: AsyncSession):
    """Snapshot data_version must match Profile.data_version."""
    user_id = uuid.uuid4()
    db_session.add(User(id=user_id, email_normalized="v@example.com", password_hash="hash"))
    db_session.add(Profile(
        id=uuid.uuid4(),
        owner_id=user_id,
        opening_cash_paise=100000,
        balance_as_of=date(2026, 11, 1),
        reserve_floor_paise=50000,
        data_version=7,
    ))
    await db_session.commit()

    snapshot = await load_financial_snapshot(db_session, user_id)
    assert snapshot.data_version == 7


@pytest.mark.asyncio
async def test_snapshot_construction_does_not_mutate_db_records(db_session: AsyncSession):
    """Loading a snapshot must not modify any ORM fields or mark objects dirty."""
    user_id = uuid.uuid4()
    db_session.add(User(id=user_id, email_normalized="mut@example.com", password_hash="hash"))
    p = Profile(
        id=uuid.uuid4(),
        owner_id=user_id,
        opening_cash_paise=200000,
        balance_as_of=date(2026, 11, 1),
        reserve_floor_paise=50000,
        data_version=2,
    )
    db_session.add(p)
    await db_session.commit()

    assert not db_session.dirty
    snapshot = await load_financial_snapshot(db_session, user_id)

    # Session remains clean with no dirty or mutated models
    assert not db_session.dirty
    assert p.opening_cash_paise == 200000
    assert p.data_version == 2


@pytest.mark.asyncio
async def test_snapshot_integrates_seamlessly_with_engine(db_session: AsyncSession):
    """The constructed FinancialSnapshot can be consumed directly by analyze() and expand_rules()."""
    user_id = uuid.uuid4()
    db_session.add(User(id=user_id, email_normalized="engine_test@example.com", password_hash="hash"))
    db_session.add(Profile(
        id=uuid.uuid4(),
        owner_id=user_id,
        opening_cash_paise=2400000,
        balance_as_of=date(2026, 11, 1),
        reserve_floor_paise=500000,
        data_version=1,
    ))
    db_session.add(CashflowRule(
        id=uuid.uuid4(),
        owner_id=user_id,
        direction="income",
        category="salary",
        amount_paise=3000000,
        due_date=date(2026, 11, 7),
        frequency="monthly",
        timing="known",
    ))
    db_session.add(CashflowRule(
        id=uuid.uuid4(),
        owner_id=user_id,
        direction="expense",
        category="rent",
        amount_paise=800000,
        due_date=date(2026, 11, 3),
        frequency="monthly",
    ))
    await db_session.commit()

    snapshot = await load_financial_snapshot(db_session, user_id)

    # 1. Expand rules
    events = expand_rules(snapshot, date(2026, 11, 1), date(2026, 11, 30))
    assert len(events) == 2

    # 2. Analyze
    scenario = ScenarioInput(
        expense_amount_paise=1000000,
        expense_date=date(2026, 11, 15),
        need_cash=False,
        allowed_savings_paise=200000,
        horizon_days=30,
        offers=(),
    )
    result = analyze(snapshot, scenario, DEFAULT_POLICY)
    assert result.model_version == "rules-v1"
    assert len(result.baseline.dates) > 0
