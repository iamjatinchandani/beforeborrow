import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.schemas.decisions import (
    AnalyzeRequest,
    AnalysisOut,
    CounterfactualRequest,
    ScenarioIn,
    ScenarioOut,
)
from app.services.scenario_service import ScenarioService
from app.services.analysis_service import AnalysisService

router = APIRouter()

@router.get("/scenarios/setup-status")
async def get_financial_setup_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ScenarioService.check_financial_setup(db, current_user.id)

@router.get("/scenarios", response_model=list[ScenarioOut])
async def list_scenarios(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ScenarioService.list_scenarios(db, current_user.id)

@router.post("/scenarios", response_model=ScenarioOut, status_code=status.HTTP_201_CREATED)
async def create_scenario(
    body: ScenarioIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ScenarioService.create_scenario(db, current_user.id, body)

@router.get("/scenarios/{scenario_id}", response_model=ScenarioOut)
async def get_scenario(
    scenario_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ScenarioService.get_scenario(db, scenario_id, current_user.id)

@router.put("/scenarios/{scenario_id}", response_model=ScenarioOut)
async def update_scenario(
    scenario_id: uuid.UUID,
    body: ScenarioIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ScenarioService.update_scenario(db, scenario_id, current_user.id, body)

@router.delete("/scenarios/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scenario(
    scenario_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ScenarioService.delete_scenario(db, scenario_id, current_user.id)

@router.post("/scenarios/{scenario_id}/analyze", response_model=AnalysisOut)
async def analyze_scenario(
    scenario_id: uuid.UUID,
    body: AnalyzeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await AnalysisService.analyze_scenario(db, scenario_id, current_user.id, body)

@router.post("/scenarios/{scenario_id}/counterfactuals")
async def counterfactuals(
    scenario_id: uuid.UUID,
    body: CounterfactualRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await AnalysisService.counterfactuals(db, scenario_id, current_user.id, body)
