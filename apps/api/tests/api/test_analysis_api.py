from datetime import date, datetime, timezone
import json
import uuid
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.dependencies import get_current_user
from app.core.security import generate_csrf_token, generate_session_token, hash_token, token_expiry
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.decisions import Analysis, Offer, Scenario
from app.models.finance import CashflowRule, Profile
from app.models.identity import Session, User
from app.schemas.decisions import AnalysisOut


@pytest_asyncio.fixture
async def api_env():
    """Sets up an isolated SQLite in-memory database and wires FastAPI dependency overrides."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db

    yield session_factory

    app.dependency_overrides.clear()
    await engine.dispose()


async def _create_user_with_session(
    session_factory: async_sessionmaker,
) -> tuple[User, dict[str, str], dict[str, str]]:
    raw_session = generate_session_token()
    raw_csrf = generate_csrf_token()
    uid = uuid.uuid4()

    async with session_factory() as session:
        user = User(
            id=uid,
            email_normalized=f"user_{uid.hex[:8]}@example.com",
            password_hash="argon2_fake_hash",
        )
        sess = Session(
            id=uuid.uuid4(),
            user_id=uid,
            token_hash=hash_token(raw_session),
            csrf_hash=hash_token(raw_csrf),
            expires_at=token_expiry(3600),
        )
        session.add_all([user, sess])
        await session.commit()

    cookies = {"bb_session": raw_session}
    headers = {"X-CSRF-Token": raw_csrf}
    return user, cookies, headers


async def _setup_profile_and_rules(
    session_factory: async_sessionmaker,
    user_id: uuid.UUID,
    data_version: int = 1,
) -> Profile:
    async with session_factory() as session:
        profile = Profile(
            id=uuid.uuid4(),
            owner_id=user_id,
            opening_cash_paise=2400000,
            balance_as_of=date(2026, 11, 1),
            reserve_floor_paise=500000,
            data_version=data_version,
        )
        rule = CashflowRule(
            id=uuid.uuid4(),
            owner_id=user_id,
            direction="income",
            category="salary",
            amount_paise=3000000,
            due_date=date(2026, 11, 7),
            frequency="monthly",
            timing="known",
        )
        session.add_all([profile, rule])
        await session.commit()
    return profile


async def _setup_scenario(
    session_factory: async_sessionmaker,
    owner_id: uuid.UUID,
    version: int = 1,
    with_offer: bool = True,
    invalid_offer: bool = False,
) -> Scenario:
    scen_id = uuid.uuid4()
    async with session_factory() as session:
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
        session.add(scenario)

        if with_offer:
            offer = Offer(
                id=uuid.uuid4(),
                scenario_id=scen_id,
                offer_type="bnpl",
                principal_paise=-1000 if invalid_offer else 800000,
                fees_paise=0,
                rate_annual_pct="0.00",
                term_months=2,
                availability_deadline=date(2026, 11, 20),
            )
            session.add(offer)

        await session.commit()
    return scenario


@pytest.mark.asyncio
async def test_successful_analysis_request(api_env):
    """1. POST /scenarios/{id}/analyze returns 200 and valid AnalysisOut."""
    user, cookies, headers = await _create_user_with_session(api_env)
    await _setup_profile_and_rules(api_env, user.id, data_version=1)
    scenario = await _setup_scenario(api_env, user.id, version=1)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/scenarios/{scenario.id}/analyze",
            json={"scenario_version": 1, "expected_data_version": 1, "stress_cases": []},
            cookies=cookies,
            headers=headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["scenario_id"] == str(scenario.id)
    assert data["model_version"] == "rules-v1"
    assert data["source_data_version"] == 1
    assert data["stale"] is False
    assert "baseline" in data["result_json"]
    assert "snapshot_hash" in data
    assert data["snapshot_hash"] is not None
    assert len(data["snapshot_hash"]) == 64


@pytest.mark.asyncio
async def test_unauthenticated_requests_rejected(api_env):
    """2. Endpoints reject unauthenticated requests with 401."""
    fake_id = uuid.uuid4()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # POST analyze without auth
        resp1 = await client.post(
            f"/api/v1/scenarios/{fake_id}/analyze",
            json={"scenario_version": 1, "expected_data_version": 1},
        )
        assert resp1.status_code == 401

        # GET analysis without auth
        resp2 = await client.get(f"/api/v1/analyses/{fake_id}")
        assert resp2.status_code == 401

        # POST counterfactuals without auth
        resp3 = await client.post(
            f"/api/v1/scenarios/{fake_id}/counterfactuals",
            json={"analysis_id": str(fake_id), "allowed_changes": ["savings"], "bounds": {}},
        )
        assert resp3.status_code == 401


@pytest.mark.asyncio
async def test_csrf_failure_on_mutation_rejected(api_env):
    """3. POST mutations require valid X-CSRF-Token and reject with 403 on mismatch."""
    user, cookies, _ = await _create_user_with_session(api_env)
    fake_id = uuid.uuid4()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Missing CSRF header
        resp1 = await client.post(
            f"/api/v1/scenarios/{fake_id}/analyze",
            json={"scenario_version": 1, "expected_data_version": 1},
            cookies=cookies,
        )
        assert resp1.status_code == 403

        # Invalid CSRF header
        resp2 = await client.post(
            f"/api/v1/scenarios/{fake_id}/analyze",
            json={"scenario_version": 1, "expected_data_version": 1},
            cookies=cookies,
            headers={"X-CSRF-Token": "tampered_csrf_token"},
        )
        assert resp2.status_code == 403


@pytest.mark.asyncio
async def test_foreign_owned_scenario_returns_404(api_env):
    """4. Requesting analysis on another user's scenario returns 404 (no leakage)."""
    user1, _, _ = await _create_user_with_session(api_env)
    user2, cookies2, headers2 = await _create_user_with_session(api_env)
    await _setup_profile_and_rules(api_env, user1.id, data_version=1)
    await _setup_profile_and_rules(api_env, user2.id, data_version=1)
    scenario_u1 = await _setup_scenario(api_env, user1.id, version=1)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/scenarios/{scenario_u1.id}/analyze",
            json={"scenario_version": 1, "expected_data_version": 1},
            cookies=cookies2,
            headers=headers2,
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_scenario_version_conflict_returns_409(api_env):
    """5. Outdated scenario_version returns 409 Conflict."""
    user, cookies, headers = await _create_user_with_session(api_env)
    await _setup_profile_and_rules(api_env, user.id, data_version=1)
    scenario = await _setup_scenario(api_env, user.id, version=2)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/scenarios/{scenario.id}/analyze",
            json={"scenario_version": 1, "expected_data_version": 1},
            cookies=cookies,
            headers=headers,
        )

    assert resp.status_code == 409
    body = resp.json()
    assert "version mismatch" in body["error"]["message"].lower()


@pytest.mark.asyncio
async def test_financial_data_version_conflict_returns_409(api_env):
    """6. Outdated expected_data_version returns 409 Conflict."""
    user, cookies, headers = await _create_user_with_session(api_env)
    await _setup_profile_and_rules(api_env, user.id, data_version=3)
    scenario = await _setup_scenario(api_env, user.id, version=1)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/scenarios/{scenario.id}/analyze",
            json={"scenario_version": 1, "expected_data_version": 2},
            cookies=cookies,
            headers=headers,
        )

    assert resp.status_code == 409
    body = resp.json()
    assert "version mismatch" in body["error"]["message"].lower()


@pytest.mark.asyncio
async def test_successful_analysis_retrieval(api_env):
    """7. GET /analyses/{id} retrieves the saved analysis and dynamic stale flag."""
    user, cookies, headers = await _create_user_with_session(api_env)
    await _setup_profile_and_rules(api_env, user.id, data_version=1)
    scenario = await _setup_scenario(api_env, user.id, version=1)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Run analysis first
        post_resp = await client.post(
            f"/api/v1/scenarios/{scenario.id}/analyze",
            json={"scenario_version": 1, "expected_data_version": 1},
            cookies=cookies,
            headers=headers,
        )
        assert post_resp.status_code == 200
        analysis_id = post_resp.json()["id"]

        # Fetch analysis via GET
        get_resp = await client.get(
            f"/api/v1/analyses/{analysis_id}",
            cookies=cookies,
        )
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["id"] == analysis_id
        assert data["stale"] is False
        assert "baseline" in data["result_json"]
        assert "snapshot_hash" in data
        assert data["snapshot_hash"] == post_resp.json()["snapshot_hash"]
        assert len(data["snapshot_hash"]) == 64


@pytest.mark.asyncio
async def test_foreign_owned_analysis_returns_404(api_env):
    """8. Foreign user cannot retrieve another user's analysis record via GET."""
    user1, cookies1, headers1 = await _create_user_with_session(api_env)
    user2, cookies2, _ = await _create_user_with_session(api_env)
    await _setup_profile_and_rules(api_env, user1.id, data_version=1)
    await _setup_profile_and_rules(api_env, user2.id, data_version=1)
    scenario = await _setup_scenario(api_env, user1.id, version=1)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        post_resp = await client.post(
            f"/api/v1/scenarios/{scenario.id}/analyze",
            json={"scenario_version": 1, "expected_data_version": 1},
            cookies=cookies1,
            headers=headers1,
        )
        analysis_id = post_resp.json()["id"]

        # User 2 tries to GET User 1's analysis
        get_resp = await client.get(
            f"/api/v1/analyses/{analysis_id}",
            cookies=cookies2,
        )
        assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_counterfactual_request_succeeds(api_env):
    """9. POST /scenarios/{id}/counterfactuals succeeds and returns CounterfactualOut."""
    user, cookies, headers = await _create_user_with_session(api_env)
    await _setup_profile_and_rules(api_env, user.id, data_version=1)
    scenario = await _setup_scenario(api_env, user.id, version=1)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create analysis first
        post_resp = await client.post(
            f"/api/v1/scenarios/{scenario.id}/analyze",
            json={"scenario_version": 1, "expected_data_version": 1},
            cookies=cookies,
            headers=headers,
        )
        analysis_id = post_resp.json()["id"]

        # Run counterfactual search
        cf_resp = await client.post(
            f"/api/v1/scenarios/{scenario.id}/counterfactuals",
            json={
                "analysis_id": analysis_id,
                "allowed_changes": ["savings"],
                "bounds": {"max_savings_paise": 500000, "min_savings_paise": 0},
            },
            cookies=cookies,
            headers=headers,
        )

        assert cf_resp.status_code == 200
        cf_data = cf_resp.json()
        assert "feasible" in cf_data
        assert "no_feasible_plan" in cf_data
        assert cf_data["tested_count"] > 0


@pytest.mark.asyncio
async def test_stale_analysis_counterfactual_request_returns_409(api_env):
    """10. POST /scenarios/{id}/counterfactuals on stale analysis returns 409."""
    user, cookies, headers = await _create_user_with_session(api_env)
    profile = await _setup_profile_and_rules(api_env, user.id, data_version=1)
    scenario = await _setup_scenario(api_env, user.id, version=1)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        post_resp = await client.post(
            f"/api/v1/scenarios/{scenario.id}/analyze",
            json={"scenario_version": 1, "expected_data_version": 1},
            cookies=cookies,
            headers=headers,
        )
        analysis_id = post_resp.json()["id"]

        # Simulate scenario update (bumping version to 2)
        async with api_env() as session:
            scen_obj = await session.get(Scenario, scenario.id)
            scen_obj.version = 2
            await session.commit()

        cf_resp = await client.post(
            f"/api/v1/scenarios/{scenario.id}/counterfactuals",
            json={
                "analysis_id": analysis_id,
                "allowed_changes": ["savings"],
                "bounds": {"max_savings_paise": 500000},
            },
            cookies=cookies,
            headers=headers,
        )
        assert cf_resp.status_code == 409


@pytest.mark.asyncio
async def test_invalid_offer_maps_to_422(api_env):
    """11. An invalid offer (e.g. negative principal) maps to 422 Unprocessable Entity."""
    user, cookies, headers = await _create_user_with_session(api_env)
    await _setup_profile_and_rules(api_env, user.id, data_version=1)
    scenario = await _setup_scenario(api_env, user.id, version=1, invalid_offer=True)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/scenarios/{scenario.id}/analyze",
            json={"scenario_version": 1, "expected_data_version": 1},
            cookies=cookies,
            headers=headers,
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_missing_profile_maps_to_400(api_env):
    """12. Missing user profile maps to 400 Bad Request."""
    user, cookies, headers = await _create_user_with_session(api_env)
    scenario = await _setup_scenario(api_env, user.id, version=1)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/scenarios/{scenario.id}/analyze",
            json={"scenario_version": 1, "expected_data_version": 1},
            cookies=cookies,
            headers=headers,
        )
    assert resp.status_code == 400
    assert "profile" in resp.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_person_d_routes_remain_functional(api_env):
    """13. Existing Person D scenario creation/update routes remain intact and functional (501 stubs)."""
    user, cookies, headers = await _create_user_with_session(api_env)
    scen_id = uuid.uuid4()

    payload = {
        "expense_amount_paise": 1000000,
        "expense_date": "2026-11-20",
        "horizon_days": 90,
        "need_cash": False,
        "allowed_savings_paise": 0,
        "offers": [],
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # POST /scenarios
        resp_post = await client.post(
            "/api/v1/scenarios",
            json=payload,
            cookies=cookies,
            headers=headers,
        )
        assert resp_post.status_code == 501

        # PUT /scenarios/{id}
        resp_put = await client.put(
            f"/api/v1/scenarios/{scen_id}",
            json=payload,
            cookies=cookies,
            headers=headers,
        )
        assert resp_put.status_code == 501


@pytest.mark.asyncio
async def test_no_duplicate_route_registration():
    """14. OpenAPI schema inspection verifies each endpoint is registered exactly once."""
    paths = app.openapi()["paths"]

    # Endpoint A
    analyze_path = "/api/v1/scenarios/{scenario_id}/analyze"
    assert analyze_path in paths
    assert "post" in paths[analyze_path]
    assert len(paths[analyze_path]) == 1  # Only POST

    # Endpoint B
    get_analysis_path = "/api/v1/analyses/{analysis_id}"
    assert get_analysis_path in paths
    assert "get" in paths[get_analysis_path]
    assert len(paths[get_analysis_path]) == 1  # Only GET

    # Endpoint C
    counterfactuals_path = "/api/v1/scenarios/{scenario_id}/counterfactuals"
    assert counterfactuals_path in paths
    assert "post" in paths[counterfactuals_path]
    assert len(paths[counterfactuals_path]) == 1  # Only POST


@pytest.mark.asyncio
async def test_analysis_retrieval_handles_null_snapshot_hash(api_env, monkeypatch):
    """15. GET /analyses/{id} handles records where snapshot_hash is null/missing."""
    user, cookies, _ = await _create_user_with_session(api_env)
    analysis_id = uuid.uuid4()

    async def mock_get_analysis(*args, **kwargs):
        return AnalysisOut(
            id=analysis_id,
            scenario_id=uuid.uuid4(),
            result_json="{}",
            model_version="rules-v1",
            source_data_version=1,
            calculated_at=datetime.now(timezone.utc),
            stale=False,
            snapshot_hash=None,
        )

    monkeypatch.setattr("app.api.v1.analysis.get_analysis_record", mock_get_analysis)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        get_resp = await client.get(
            f"/api/v1/analyses/{analysis_id}",
            cookies=cookies,
        )
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["id"] == str(analysis_id)
        assert data["snapshot_hash"] is None
