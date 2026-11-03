import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.decisions import Scenario, Offer
from app.schemas.decisions import ScenarioIn

class ScenarioRepository:
    @staticmethod
    async def create(db: AsyncSession, owner_id: uuid.UUID, data: ScenarioIn) -> Scenario:
        scenario = Scenario(
            owner_id=owner_id,
            expense_amount_paise=data.expense_amount_paise,
            expense_date=data.expense_date,
            merchant=data.merchant,
            category=data.category,
            need_cash=data.need_cash,
            allowed_savings_paise=data.allowed_savings_paise,
            horizon_days=data.horizon_days,
            version=1,
        )
        for off_in in data.offers:
            offer = Offer(
                offer_name=off_in.offer_name,
                provider=off_in.provider,
                offer_type=off_in.offer_type,
                principal_paise=off_in.principal_paise,
                fees_paise=off_in.fees_paise,
                rate_annual_pct=off_in.rate_annual_pct,
                term_months=off_in.term_months,
                availability_deadline=off_in.availability_deadline,
                eligibility_evidence=off_in.eligibility_evidence,
                schedule_json=off_in.schedule_json,
            )
            scenario.offers.append(offer)

        db.add(scenario)
        await db.commit()
        await db.refresh(scenario, ["offers"])
        return scenario

    @staticmethod
    async def get_by_id(db: AsyncSession, scenario_id: uuid.UUID, owner_id: uuid.UUID) -> Scenario | None:
        stmt = (
            select(Scenario)
            .where(Scenario.id == scenario_id, Scenario.owner_id == owner_id)
            .options(selectinload(Scenario.offers))
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_owner(db: AsyncSession, owner_id: uuid.UUID) -> list[Scenario]:
        stmt = (
            select(Scenario)
            .where(Scenario.owner_id == owner_id)
            .options(selectinload(Scenario.offers))
            .order_by(Scenario.created_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def update(db: AsyncSession, scenario: Scenario, data: ScenarioIn) -> Scenario:
        scenario.expense_amount_paise = data.expense_amount_paise
        scenario.expense_date = data.expense_date
        scenario.merchant = data.merchant
        scenario.category = data.category
        scenario.need_cash = data.need_cash
        scenario.allowed_savings_paise = data.allowed_savings_paise
        scenario.horizon_days = data.horizon_days
        scenario.version += 1

        # Replace offers
        scenario.offers.clear()
        for off_in in data.offers:
            offer = Offer(
                offer_name=off_in.offer_name,
                provider=off_in.provider,
                offer_type=off_in.offer_type,
                principal_paise=off_in.principal_paise,
                fees_paise=off_in.fees_paise,
                rate_annual_pct=off_in.rate_annual_pct,
                term_months=off_in.term_months,
                availability_deadline=off_in.availability_deadline,
                eligibility_evidence=off_in.eligibility_evidence,
                schedule_json=off_in.schedule_json,
            )
            scenario.offers.append(offer)

        await db.commit()
        await db.refresh(scenario, ["offers"])
        return scenario

    @staticmethod
    async def delete(db: AsyncSession, scenario: Scenario) -> None:
        await db.delete(scenario)
        await db.commit()
