import pytest
import uuid
from datetime import date, datetime, timedelta, timezone
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.security import generate_session_token, generate_csrf_token, hash_token, token_expiry
from app.db.session import AsyncSessionLocal
from app.models.identity import User, Session
from app.models.finance import Profile, Obligation, ObligationPayment
from app.models.decisions import Scenario, Offer, Analysis

@pytest.fixture
async def db_session():
    async with AsyncSessionLocal() as session:
        yield session

@pytest.fixture
async def test_users(db_session):
    # Create User A
    user_a = User(email_normalized=f"user_a_{uuid.uuid4().hex[:8]}@example.com", password_hash="dummy")
    user_b = User(email_normalized=f"user_b_{uuid.uuid4().hex[:8]}@example.com", password_hash="dummy")
    db_session.add_all([user_a, user_b])
    await db_session.flush()

    # Session for User A
    token_a = generate_session_token()
    csrf_a = generate_csrf_token()
    sess_a = Session(
        user_id=user_a.id,
        token_hash=hash_token(token_a),
        csrf_hash=hash_token(csrf_a),
        expires_at=token_expiry(3600),
    )

    # Session for User B
    token_b = generate_session_token()
    csrf_b = generate_csrf_token()
    sess_b = Session(
        user_id=user_b.id,
        token_hash=hash_token(token_b),
        csrf_hash=hash_token(csrf_b),
        expires_at=token_expiry(3600),
    )

    # Profile for User A
    prof_a = Profile(
        owner_id=user_a.id,
        currency="INR",
        timezone="Asia/Kolkata",
        opening_cash_paise=800_000,
        balance_as_of=date(2026, 11, 1),
        reserve_floor_paise=500_000,
        data_version=1,
    )

    db_session.add_all([sess_a, sess_b, prof_a])
    await db_session.commit()

    return {
        "user_a": user_a,
        "token_a": token_a,
        "csrf_a": csrf_a,
        "user_b": user_b,
        "token_b": token_b,
        "csrf_b": csrf_b,
        "profile_a": prof_a,
    }

@pytest.mark.asyncio
async def test_scenario_crud_and_validation(test_users):
    u = test_users
    headers_a = {"X-CSRF-Token": u["csrf_a"]}
    cookies_a = {"bb_session": u["token_a"]}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Validation: negative amount should fail
        bad_payload = {
            "expense_amount_paise": -5000,
            "expense_date": "2026-11-08",
            "horizon_days": 90,
            "offers": [],
        }
        res = await client.post("/api/v1/scenarios", json=bad_payload, headers=headers_a, cookies=cookies_a)
        assert res.status_code == 422

        # 2. Validation: more than 3 offers should fail
        too_many_offers = {
            "expense_amount_paise": 2_000_000,
            "expense_date": "2026-11-08",
            "horizon_days": 90,
            "offers": [
                {"offer_type": "personal_loan", "principal_paise": 100000},
                {"offer_type": "personal_loan", "principal_paise": 200000},
                {"offer_type": "personal_loan", "principal_paise": 300000},
                {"offer_type": "personal_loan", "principal_paise": 400000},
            ],
        }
        res = await client.post("/api/v1/scenarios", json=too_many_offers, headers=headers_a, cookies=cookies_a)
        assert res.status_code == 422

        # 3. Create valid scenario
        valid_payload = {
            "expense_amount_paise": 2_000_000,
            "expense_date": "2026-11-08",
            "category": "Medical emergency",
            "need_cash": True,
            "allowed_savings_paise": 500_000,
            "horizon_days": 90,
            "offers": [
                {
                    "offer_name": "Demo Personal Loan",
                    "provider": "Demo Bank",
                    "offer_type": "personal_loan",
                    "principal_paise": 1_500_000,
                    "fees_paise": 50_000,
                    "rate_annual_pct": "14.00",
                    "term_months": 6,
                }
            ],
        }
        res = await client.post("/api/v1/scenarios", json=valid_payload, headers=headers_a, cookies=cookies_a)
        assert res.status_code == 201
        scen = res.json()
        assert scen["expense_amount_paise"] == 2_000_000
        assert len(scen["offers"]) == 1
        scenario_id = scen["id"]

        # 4. Get scenario
        res = await client.get(f"/api/v1/scenarios/{scenario_id}", cookies=cookies_a)
        assert res.status_code == 200
        assert res.json()["id"] == scenario_id

        # 5. Update scenario
        update_payload = dict(valid_payload)
        update_payload["expense_amount_paise"] = 2_500_000
        res = await client.put(f"/api/v1/scenarios/{scenario_id}", json=update_payload, headers=headers_a, cookies=cookies_a)
        assert res.status_code == 200
        assert res.json()["expense_amount_paise"] == 2_500_000
        assert res.json()["version"] == 2

@pytest.mark.asyncio
async def test_owner_isolation(test_users):
    u = test_users
    headers_a = {"X-CSRF-Token": u["csrf_a"]}
    cookies_a = {"bb_session": u["token_a"]}
    headers_b = {"X-CSRF-Token": u["csrf_b"]}
    cookies_b = {"bb_session": u["token_b"]}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # User A creates scenario
        res = await client.post(
            "/api/v1/scenarios",
            json={"expense_amount_paise": 1_000_000, "expense_date": "2026-11-10", "horizon_days": 90, "offers": []},
            headers=headers_a,
            cookies=cookies_a,
        )
        assert res.status_code == 201
        scen_id = res.json()["id"]

        # User B cannot access User A's scenario
        res_b = await client.get(f"/api/v1/scenarios/{scen_id}", cookies=cookies_b)
        assert res_b.status_code == 404

        # User B cannot update User A's scenario
        res_b_up = await client.put(
            f"/api/v1/scenarios/{scen_id}",
            json={"expense_amount_paise": 999, "expense_date": "2026-11-10", "horizon_days": 90, "offers": []},
            headers=headers_b,
            cookies=cookies_b,
        )
        assert res_b_up.status_code == 404

@pytest.mark.asyncio
async def test_analyze_version_conflict_and_simulation(test_users, db_session):
    u = test_users
    headers_a = {"X-CSRF-Token": u["csrf_a"]}
    cookies_a = {"bb_session": u["token_a"]}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create scenario with a Demo offer
        res = await client.post(
            "/api/v1/scenarios",
            json={
                "expense_amount_paise": 2_000_000,
                "expense_date": "2026-11-08",
                "horizon_days": 90,
                "offers": [
                    {
                        "offer_name": "Demo 3-Month BNPL",
                        "provider": "Demo BNPL",
                        "offer_type": "bnpl",
                        "principal_paise": 2_000_000,
                        "fees_paise": 50_000,
                        "rate_annual_pct": "0.00",
                        "term_months": 3,
                    }
                ],
            },
            headers=headers_a,
            cookies=cookies_a,
        )
        scen_id = res.json()["id"]

        # HTTP 409 test: expected_data_version mismatch
        res_conflict = await client.post(
            f"/api/v1/scenarios/{scen_id}/analyze",
            json={"scenario_version": 1, "expected_data_version": 999, "stress_cases": []},
            headers=headers_a,
            cookies=cookies_a,
        )
        assert res_conflict.status_code == 409

        # Successful analysis with matching data version (1)
        res_analyze = await client.post(
            f"/api/v1/scenarios/{scen_id}/analyze",
            json={"scenario_version": 1, "expected_data_version": 1, "stress_cases": ["income_delay_30d"]},
            headers=headers_a,
            cookies=cookies_a,
        )
        assert res_analyze.status_code == 200
        analysis_data = res_analyze.json()
        assert "result_json" in analysis_data
        analysis_id = analysis_data["id"]

        # Fetch analysis via Person C endpoint (returns 501 until Person C merges feat/c-engine, or 200 once integrated)
        res_get_an = await client.get(f"/api/v1/analyses/{analysis_id}", cookies=cookies_a)
        assert res_get_an.status_code in (200, 501)
        if res_get_an.status_code == 200:
            assert res_get_an.json()["stale"] is False

@pytest.mark.asyncio
async def test_receipts_immutability_and_export(test_users):
    u = test_users
    headers_a = {"X-CSRF-Token": u["csrf_a"]}
    cookies_a = {"bb_session": u["token_a"]}
    headers_b = {"X-CSRF-Token": u["csrf_b"]}
    cookies_b = {"bb_session": u["token_b"]}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create scenario & analyze
        res_scen = await client.post(
            "/api/v1/scenarios",
            json={
                "expense_amount_paise": 2_000_000,
                "expense_date": "2026-11-08",
                "horizon_days": 90,
                "offers": [
                    {
                        "offer_name": "Demo Offer A",
                        "provider": "Demo Provider",
                        "offer_type": "personal_loan",
                        "principal_paise": 2_000_000,
                        "fees_paise": 100_000,
                        "rate_annual_pct": "12.00",
                        "term_months": 3,
                    }
                ],
            },
            headers=headers_a,
            cookies=cookies_a,
        )
        scen_id = res_scen.json()["id"]

        res_an = await client.post(
            f"/api/v1/scenarios/{scen_id}/analyze",
            json={"scenario_version": 1, "expected_data_version": 1, "stress_cases": []},
            headers=headers_a,
            cookies=cookies_a,
        )
        an_id = res_an.json()["id"]

        # Create Receipt
        res_rcp = await client.post(
            "/api/v1/receipts",
            json={
                "analysis_id": an_id,
                "chosen_option": "Demo Offer A",
                "reflection_answers": {"tight_date": "5 Nov", "key_assumption": "Salary on 30th"},
            },
            headers=headers_a,
            cookies=cookies_a,
        )
        assert res_rcp.status_code == 201
        rcp_id = res_rcp.json()["id"]

        # Verify receipt detail
        res_rcp_detail = await client.get(f"/api/v1/receipts/{rcp_id}", cookies=cookies_a)
        assert res_rcp_detail.status_code == 200
        detail = res_rcp_detail.json()
        assert detail["chosen_option"] == "Demo Offer A"
        assert "snapshot_hash" in detail["context"]
        assert "consequences" in detail

        # Export receipt
        res_export = await client.get(f"/api/v1/receipts/{rcp_id}/export", cookies=cookies_a)
        assert res_export.status_code == 200
        assert "verified_hash" in res_export.json()

        # User B cannot access User A's receipt or export
        res_b_rcp = await client.get(f"/api/v1/receipts/{rcp_id}", cookies=cookies_b)
        assert res_b_rcp.status_code == 404
        res_b_exp = await client.get(f"/api/v1/receipts/{rcp_id}/export", cookies=cookies_b)
        assert res_b_exp.status_code == 404

@pytest.mark.asyncio
async def test_alerts_deduplication_and_dismissal(test_users, db_session):
    u = test_users
    headers_a = {"X-CSRF-Token": u["csrf_a"]}
    cookies_a = {"bb_session": u["token_a"]}
    headers_b = {"X-CSRF-Token": u["csrf_b"]}
    cookies_b = {"bb_session": u["token_b"]}

    # Add an obligation payment due in 3 days
    ob = Obligation(
        owner_id=u["user_a"].id,
        provider_alias="Bajaj Finance",
        kind="term_loan",
        principal_remaining_paise=5_000_000,
    )
    db_session.add(ob)
    await db_session.flush()

    due_in_3d = (datetime.now().date()) + timedelta(days=3)
    payment = ObligationPayment(
        obligation_id=ob.id,
        due_date=due_in_3d,
        amount_paise=1_500_000,
        payment_status="scheduled",
    )
    db_session.add(payment)
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # First call evaluates and generates alert
        res1 = await client.get("/api/v1/alerts", cookies=cookies_a)
        assert res1.status_code == 200
        alerts1 = res1.json()
        count1 = len(alerts1)
        assert count1 >= 1

        # Second call: verifies deduplication (count does not increase)
        res2 = await client.get("/api/v1/alerts", cookies=cookies_a)
        assert res2.status_code == 200
        alerts2 = res2.json()
        assert len(alerts2) == count1

        # Dismiss alert
        alert_id = alerts1[0]["id"]
        res_dismiss = await client.patch(f"/api/v1/alerts/{alert_id}", headers=headers_a, cookies=cookies_a)
        assert res_dismiss.status_code == 200
        assert res_dismiss.json()["dismissed_at"] is not None

        # User B cannot dismiss User A's alert
        res_b_dismiss = await client.patch(f"/api/v1/alerts/{alert_id}", headers=headers_b, cookies=cookies_b)
        assert res_b_dismiss.status_code == 404
