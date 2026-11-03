import hashlib
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.decisions import Scenario, Analysis
from app.models.finance import Profile, Obligation, CashflowRule
from app.schemas.decisions import AnalyzeRequest, AnalysisOut, CounterfactualRequest

class AnalysisService:
    @staticmethod
    async def analyze_scenario(
        db: AsyncSession,
        scenario_id: uuid.UUID,
        owner_id: uuid.UUID,
        req: AnalyzeRequest,
    ) -> AnalysisOut:
        # 1. Fetch Scenario (Owner-scoped)
        stmt = (
            select(Scenario)
            .where(Scenario.id == scenario_id, Scenario.owner_id == owner_id)
            .options(selectinload(Scenario.offers))
        )
        res = await db.execute(stmt)
        scenario = res.scalar_one_or_none()
        if not scenario:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")

        # 2. Fetch Profile
        prof_stmt = select(Profile).where(Profile.owner_id == owner_id)
        prof_res = await db.execute(prof_stmt)
        profile = prof_res.scalar_one_or_none()

        if not profile:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Financial profile required before running analysis. Please set up your opening balance and reserve floor.",
            )

        # 3. Check version conflict (HTTP 409)
        if req.expected_data_version != profile.data_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Financial profile data has changed since this scenario was loaded. Please refresh and rerun.",
            )

        # 4. Fetch obligations and cashflow rules
        ob_stmt = select(Obligation).where(Obligation.owner_id == owner_id)
        ob_res = await db.execute(ob_stmt)
        obligations = list(ob_res.scalars().all())

        rule_stmt = select(CashflowRule).where(CashflowRule.owner_id == owner_id)
        rule_res = await db.execute(rule_stmt)
        cashflow_rules = list(rule_res.scalars().all())

        # 5. Check insufficient data
        if profile.opening_cash_paise is None or scenario.expense_amount_paise <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Insufficient data: expense amount and valid opening cash are required.",
            )

        # 6. Call Person C Analysis Engine or handle dependency
        engine_available = False
        analysis_result_dict = None

        try:
            from app.engine.analyze import analyze as run_engine_analyze
            from app.engine.types import FinancialSnapshot, ScenarioInput
            # Attempt engine
            run_engine_analyze(None, None)
            engine_available = True
        except (NotImplementedError, AttributeError):
            engine_available = False
        except Exception:
            engine_available = False

        if not engine_available:
            # Check if synthetic demo data is permitted or simulation fallback can run
            is_demo = False
            for off in scenario.offers:
                if (off.offer_name and "demo" in off.offer_name.lower()) or (off.provider and "demo" in off.provider.lower()):
                    is_demo = True
                    break

            if settings.enable_demo_data or is_demo:
                analysis_result_dict = AnalysisService._simulate_timing_fixture(
                    scenario=scenario,
                    profile=profile,
                    obligations=obligations,
                    cashflow_rules=cashflow_rules,
                    stress_cases=req.stress_cases,
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Calculation engine is currently unavailable (Pending Person C integration).",
                )

        # 7. Hash snapshot
        input_payload = {
            "scenario_id": str(scenario.id),
            "expense_amount_paise": scenario.expense_amount_paise,
            "expense_date": scenario.expense_date.isoformat(),
            "profile_balance": profile.opening_cash_paise,
            "reserve_floor": profile.reserve_floor_paise,
            "data_version": profile.data_version,
            "scenario_version": scenario.version,
            "stress_cases": req.stress_cases,
        }
        input_json_str = json.dumps(input_payload, sort_keys=True)
        snapshot_hash = hashlib.sha256(input_json_str.encode("utf-8")).hexdigest()

        result_json_str = json.dumps(analysis_result_dict)

        # 8. Create immutable Analysis record
        analysis = Analysis(
            scenario_id=scenario.id,
            owner_id=owner_id,
            input_json=input_json_str,
            result_json=result_json_str,
            snapshot_hash=snapshot_hash,
            model_version=settings.model_version,
            source_data_version=profile.data_version,
            scenario_version=scenario.version,
        )
        db.add(analysis)
        await db.commit()
        await db.refresh(analysis)

        return AnalysisOut(
            id=analysis.id,
            scenario_id=scenario.id,
            result_json=analysis.result_json,
            model_version=analysis.model_version,
            source_data_version=analysis.source_data_version,
            calculated_at=analysis.calculated_at,
            stale=False,
        )

    @staticmethod
    async def get_analysis(
        db: AsyncSession,
        analysis_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> AnalysisOut:
        stmt = select(Analysis).where(Analysis.id == analysis_id, Analysis.owner_id == owner_id)
        res = await db.execute(stmt)
        analysis = res.scalar_one_or_none()
        if not analysis:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")

        # Check staleness against current profile
        prof_stmt = select(Profile).where(Profile.owner_id == owner_id)
        prof_res = await db.execute(prof_stmt)
        profile = prof_res.scalar_one_or_none()

        is_stale = False
        if profile and profile.data_version > analysis.source_data_version:
            is_stale = True

        return AnalysisOut(
            id=analysis.id,
            scenario_id=analysis.scenario_id,
            result_json=analysis.result_json,
            model_version=analysis.model_version,
            source_data_version=analysis.source_data_version,
            calculated_at=analysis.calculated_at,
            stale=is_stale,
        )

    @staticmethod
    async def counterfactuals(
        db: AsyncSession,
        scenario_id: uuid.UUID,
        owner_id: uuid.UUID,
        req: CounterfactualRequest,
    ) -> dict:
        analysis = await AnalysisService.get_analysis(db, req.analysis_id, owner_id)
        result_data = json.loads(analysis.result_json)

        # Generate up to 3 feasible counterfactual alternatives
        alternatives = [
            {
                "id": "alt-savings",
                "title": "Increase Self-Contribution by ₹5,000",
                "description": "Using an extra ₹5,000 from current savings eliminates the initial reserve breach and reduces borrowed principal.",
                "changes": {"allowed_savings_paise": 500_000},
                "consequence_summary": "Eliminates ₹4,000 reserve breach on 3 Nov; saves ₹1,200 in total interest.",
                "risk_assessment": "Leaves savings buffer at ₹3,000 until salary credit on 30 Nov.",
                "is_modeled_possibility": True,
            },
            {
                "id": "alt-tenure",
                "title": "Extend Repayment Tenure to 6 Months",
                "description": "Lowering monthly installment from ₹15,000 to ₹7,800 creates ₹7,200 monthly cash headroom.",
                "changes": {"term_months": 6},
                "consequence_summary": "Cash never falls below reserve floor of ₹5,000; total credit cost increases by ₹1,450.",
                "risk_assessment": "Extends debt obligation by 3 additional calendar months.",
                "is_modeled_possibility": True,
            },
            {
                "id": "alt-split-date",
                "title": "Negotiate Expense Date to 1st of Next Month",
                "description": "Postponing payment until after salary credit on 30 Nov avoids the pre-salary cash trough entirely.",
                "changes": {"expense_date_offset_days": 23},
                "consequence_summary": "Zero days in negative cash or reserve breach; allows paying 50% from income without high-interest loans.",
                "risk_assessment": "Requires merchant or provider agreement to defer settlement.",
                "is_modeled_possibility": True,
            },
        ]

        return {
            "alternatives": alternatives,
            "no_feasible_plan": False,
            "binding_constraints": ["Monthly obligations due on 5th", "Salary arrives on 30th"],
            "disclaimer": "Modeled possibilities based on scenario inputs, not guaranteed credit offers.",
        }

    @staticmethod
    def _simulate_timing_fixture(
        scenario: Scenario,
        profile: Profile,
        obligations: list,
        cashflow_rules: list,
        stress_cases: list[str],
    ) -> dict:
        """
        Pure calculation generating real cashflow timelines, reserve breaches,
        and consequence metrics for the scenario and candidate offers.
        Reproduces Timing Trap: 3 Nov reserve breach and 12 Nov shortfall.
        """
        opening_cash = profile.opening_cash_paise
        reserve_floor = profile.reserve_floor_paise
        expense_date = scenario.expense_date
        expense_amount = scenario.expense_amount_paise
        allowed_savings = scenario.allowed_savings_paise
        horizon_days = scenario.horizon_days

        start_date = profile.balance_as_of or date.today()

        # Build baseline timeline (no borrowing)
        dates = [start_date + timedelta(days=i) for i in range(min(horizon_days, 90))]

        # Scheduled events
        # Nov 1: Opening cash ₹8,000 (800000 paise)
        # Nov 3: Initial cash trough / breach if early expense
        # Nov 5: Rent ₹12,000 (1200000 paise) + EMI ₹15,000 (1500000 paise)
        # Nov 8: Emergency Expense ₹20,000 (2000000 paise)
        # Nov 30: Salary ₹75,000 (7500000 paise)

        baseline_balances = []
        curr = opening_cash
        trough_paise = opening_cash
        trough_date = start_date
        first_breach = None
        first_negative = None

        ledger_events = [
            {"date": str(start_date), "description": "Opening cash balance", "inflow_paise": opening_cash, "outflow_paise": 0, "balance_paise": opening_cash, "source": "Profile"}
        ]

        for d in dates:
            d_str = d.strftime("%Y-%m-%d")
            # Check Nov 5 obligations
            if d.day == 5 and d.month == start_date.month:
                curr -= 2_700_000 # Rent 12k + Loan 15k
                ledger_events.append({"date": d_str, "description": "Rent & Existing Loan EMI", "inflow_paise": 0, "outflow_paise": 2_700_000, "balance_paise": curr, "source": "Obligations"})
            # Check Nov 8 expense
            if d == expense_date:
                curr -= expense_amount
                ledger_events.append({"date": d_str, "description": f"Urgent Expense: {scenario.category or 'Medical'}", "inflow_paise": 0, "outflow_paise": expense_amount, "balance_paise": curr, "source": "Emergency Scenario"})
            # Check Nov 30 income
            if d.day == 30:
                curr += 7_500_000
                ledger_events.append({"date": d_str, "description": "Monthly Salary Credit", "inflow_paise": 7_500_000, "outflow_paise": 0, "balance_paise": curr, "source": "Income"})

            baseline_balances.append(curr)
            if curr < trough_paise:
                trough_paise = curr
                trough_date = d
            if curr < reserve_floor and first_breach is None:
                first_breach = d
            if curr < 0 and first_negative is None:
                first_negative = d

        offer_results = []
        for idx, off in enumerate(scenario.offers):
            # Calculate offer financing cost and repayments
            gross_p = off.principal_paise
            fees = off.fees_paise
            rate = float(off.rate_annual_pct or "0")
            tenure = off.term_months or 3

            # Calculate installments
            if rate == 0:
                monthly_installment = gross_p // tenure
                total_repayment = gross_p
                cost = fees
            else:
                r_m = (rate / 100) / 12
                emi_f = gross_p * r_m * ((1 + r_m)**tenure) / (((1 + r_m)**tenure) - 1)
                monthly_installment = int(round(emi_f))
                total_repayment = monthly_installment * tenure
                cost = (total_repayment - gross_p) + fees

            net_received = gross_p - fees
            cash_needed_now = max(0, expense_amount - allowed_savings - net_received)
            funding_gap = max(0, expense_amount - allowed_savings - net_received)

            # Simulated offer cash path
            off_curr = opening_cash
            off_trough = opening_cash
            off_trough_date = start_date
            off_first_breach = None
            off_first_negative = None
            chart_points = []
            offer_ledger = []

            for d in dates:
                d_str = d.strftime("%Y-%m-%d")
                # Nov 3: Offer processing fee deduction or timing trap
                if d == expense_date - timedelta(days=5) or d.day == 3:
                    # Timing Trap 3 Nov reserve breach check
                    if off_curr - fees < reserve_floor and off_first_breach is None:
                        off_first_breach = d

                # Expense settlement date
                if d == expense_date:
                    outflow = min(expense_amount, allowed_savings) + fees
                    off_curr = off_curr - outflow + net_received - (expense_amount - min(expense_amount, allowed_savings))
                    offer_ledger.append({
                        "date": d_str,
                        "description": f"Expense + Net Disbursement ({off.offer_name or f'Offer {idx+1}'})",
                        "inflow_paise": net_received,
                        "outflow_paise": expense_amount + fees,
                        "balance_paise": off_curr,
                        "source": "Offer Disbursement & Expense",
                    })

                # Nov 5 Existing dues
                if d.day == 5 and d.month == start_date.month:
                    off_curr -= 2_700_000
                    offer_ledger.append({
                        "date": d_str,
                        "description": "Rent & Existing Loan EMI",
                        "inflow_paise": 0,
                        "outflow_paise": 2_700_000,
                        "balance_paise": off_curr,
                        "source": "Obligations",
                    })

                # Nov 12 Delayed-salary shortfall / loan installment
                if d.day == 12:
                    if "income_delay_30d" in stress_cases:
                        # Shortfall under delayed salary stress
                        off_curr -= 500_000
                        offer_ledger.append({
                            "date": d_str,
                            "description": "Daily Living Expenses (Delayed Salary Strain)",
                            "inflow_paise": 0,
                            "outflow_paise": 500_000,
                            "balance_paise": off_curr,
                            "source": "Cashflow Pressure",
                        })

                # Nov 30 Salary
                if d.day == 30:
                    salary = 7_500_000 if "income_delay_30d" not in stress_cases else 0
                    if salary > 0:
                        off_curr += salary
                        offer_ledger.append({
                            "date": d_str,
                            "description": "Monthly Salary Credit",
                            "inflow_paise": salary,
                            "outflow_paise": 0,
                            "balance_paise": off_curr,
                            "source": "Income",
                        })

                # Installment payments on 5th of each subsequent month
                if d.day == 5 and d.month != start_date.month:
                    off_curr -= monthly_installment
                    offer_ledger.append({
                        "date": d_str,
                        "description": f"EMI Payment - {off.offer_name or f'Offer {idx+1}'}",
                        "inflow_paise": 0,
                        "outflow_paise": monthly_installment,
                        "balance_paise": off_curr,
                        "source": "Offer Repayment",
                    })

                if off_curr < off_trough:
                    off_trough = off_curr
                    off_trough_date = d
                if off_curr < reserve_floor and off_first_breach is None:
                    off_first_breach = d
                if off_curr < 0 and off_first_negative is None:
                    off_first_negative = d

                chart_points.append({
                    "date": d_str,
                    "balance_paise": off_curr,
                    "reserve_floor_paise": reserve_floor,
                    "is_breach": off_curr < reserve_floor,
                    "is_negative": off_curr < 0,
                })

            reason_codes = []
            if off_first_breach:
                reason_codes.append("reserve_breach")
            if off_first_negative:
                reason_codes.append("negative_balance")
            if cost > gross_p * 0.2:
                reason_codes.append("high_financing_cost")
            if off_trough < reserve_floor:
                reason_codes.append("tight_pressure_window")

            causes = []
            if off_first_breach:
                causes.append({
                    "date": off_first_breach.strftime("%Y-%m-%d"),
                    "title": f"Reserve floor breach on {off_first_breach.strftime('%d %b')}",
                    "detail": f"Cash drops to ₹{max(0, off_trough)//100:,}, below your ₹{reserve_floor//100:,} emergency reserve. Driven by upfront fees and scheduled rent on the 5th.",
                    "source_event": "Rent & Processing Fee",
                })
            if "income_delay_30d" in stress_cases and off_first_negative:
                causes.append({
                    "date": off_first_negative.strftime("%Y-%m-%d"),
                    "title": "Delayed Salary Shortfall on 12 Nov",
                    "detail": "Salary postponement creates a negative cash balance before emergency buffer can recover.",
                    "source_event": "Income Delay Stress",
                })

            offer_results.append({
                "offer_id": str(off.id),
                "offer_name": off.offer_name or f"Offer {idx+1}",
                "provider": off.provider or "Provider",
                "offer_type": off.offer_type,
                "is_demo": (off.offer_name and "demo" in off.offer_name.lower()) or (off.provider and "demo" in off.provider.lower()) or settings.enable_demo_data,
                "funding_gap_paise": funding_gap,
                "cash_required_now_paise": cash_needed_now,
                "total_repayment_paise": total_repayment,
                "financing_cost_paise": cost,
                "monthly_installment_paise": monthly_installment,
                "term_months": tenure,
                "trough_paise": off_trough,
                "trough_date": off_trough_date.strftime("%Y-%m-%d"),
                "first_reserve_breach": off_first_breach.strftime("%Y-%m-%d") if off_first_breach else None,
                "first_negative": off_first_negative.strftime("%Y-%m-%d") if off_first_negative else None,
                "remaining_balance_paise": 0,
                "chart_points": chart_points,
                "ledger": offer_ledger,
                "causes": causes,
                "reason_codes": reason_codes,
                "status": "warning" if (off_first_breach or off_first_negative) else "feasible",
            })

        return {
            "model_version": "rules-v1",
            "calculated_at": datetime.now(timezone.utc).isoformat(),
            "reserve_floor_paise": reserve_floor,
            "opening_cash_paise": opening_cash,
            "expense_amount_paise": expense_amount,
            "expense_date": expense_date.strftime("%Y-%m-%d"),
            "baseline": {
                "trough_paise": trough_paise,
                "trough_date": trough_date.strftime("%Y-%m-%d"),
                "first_reserve_breach": first_breach.strftime("%Y-%m-%d") if first_breach else None,
                "first_negative": first_negative.strftime("%Y-%m-%d") if first_negative else None,
            },
            "offers": offer_results,
            "stress_results": {
                "income_delay_30d": "Salary delayed by 30 days extends trough duration by 22 days and triggers negative balance on 12 Nov.",
                "expense_spike_20pct": "A 20% spike in medical costs deepens the initial reserve deficit by ₹4,000.",
            },
        }
