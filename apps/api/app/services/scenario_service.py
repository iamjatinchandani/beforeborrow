import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.models.decisions import Scenario
from app.models.finance import Profile, Obligation
from app.repositories.scenarios import ScenarioRepository
from app.schemas.decisions import ScenarioIn, ScenarioOut

class ScenarioService:
    @staticmethod
    async def create_scenario(
        db: AsyncSession,
        owner_id: uuid.UUID,
        data: ScenarioIn,
    ) -> Scenario:
        if len(data.offers) > 3:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Maximum of 3 funding offers allowed",
            )
        return await ScenarioRepository.create(db, owner_id, data)

    @staticmethod
    async def get_scenario(
        db: AsyncSession,
        scenario_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> Scenario:
        scenario = await ScenarioRepository.get_by_id(db, scenario_id, owner_id)
        if not scenario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scenario not found",
            )
        return scenario

    @staticmethod
    async def list_scenarios(
        db: AsyncSession,
        owner_id: uuid.UUID,
    ) -> list[Scenario]:
        return await ScenarioRepository.list_by_owner(db, owner_id)

    @staticmethod
    async def update_scenario(
        db: AsyncSession,
        scenario_id: uuid.UUID,
        owner_id: uuid.UUID,
        data: ScenarioIn,
    ) -> Scenario:
        scenario = await ScenarioService.get_scenario(db, scenario_id, owner_id)
        if len(data.offers) > 3:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Maximum of 3 funding offers allowed",
            )
        return await ScenarioRepository.update(db, scenario, data)

    @staticmethod
    async def delete_scenario(
        db: AsyncSession,
        scenario_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> None:
        scenario = await ScenarioService.get_scenario(db, scenario_id, owner_id)
        await ScenarioRepository.delete(db, scenario)

    @staticmethod
    async def check_financial_setup(
        db: AsyncSession,
        owner_id: uuid.UUID,
    ) -> dict:
        profile_stmt = select(Profile).where(Profile.owner_id == owner_id)
        profile_res = await db.execute(profile_stmt)
        profile = profile_res.scalar_one_or_none()

        ob_stmt = select(Obligation).where(Obligation.owner_id == owner_id)
        ob_res = await db.execute(ob_stmt)
        obligations = list(ob_res.scalars().all())

        missing = []
        if not profile:
            missing.append("profile")
            missing.append("opening_cash")
            missing.append("reserve_floor")
        else:
            if profile.opening_cash_paise is None or profile.opening_cash_paise < 0:
                missing.append("opening_cash")
            if profile.reserve_floor_paise is None:
                missing.append("reserve_floor")

        return {
            "is_complete": len(missing) == 0,
            "missing_fields": missing,
            "has_profile": profile is not None,
            "profile_data_version": profile.data_version if profile else 0,
            "obligations_count": len(obligations),
        }
