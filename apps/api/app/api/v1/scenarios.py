import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.schemas.decisions import (
    AnalysisOut,
    AnalyzeRequest,
    CounterfactualOut,
    CounterfactualRequest,
    ScenarioIn,
    ScenarioOut,
)
from app.services.analysis import (
    AnalysisMismatchError,
    AnalysisNotFoundError,
    InvalidOfferError,
    ScenarioNotFoundError,
    StaleAnalysisError,
    VersionConflictError,
    run_counterfactual_analysis,
    run_scenario_analysis,
)
from app.services.snapshot import (
    InvalidFinancialDataError,
    MissingProfileError,
)

router = APIRouter()


@router.post("/scenarios", response_model=ScenarioOut, status_code=201)
async def create_scenario(body: ScenarioIn, db: AsyncSession = Depends(get_db)):
    raise HTTPException(status_code=501, detail="Not implemented")


@router.put("/scenarios/{scenario_id}", response_model=ScenarioOut)
async def update_scenario(scenario_id: uuid.UUID, body: ScenarioIn, db: AsyncSession = Depends(get_db)):
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/scenarios/{scenario_id}/analyze", response_model=AnalysisOut)
async def analyze_scenario(
    scenario_id: uuid.UUID,
    body: AnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await run_scenario_analysis(
            db=db,
            scenario_id=scenario_id,
            user_id=current_user.id,
            request=body,
        )
    except ScenarioNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except VersionConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except MissingProfileError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except (InvalidOfferError, InvalidFinancialDataError) as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.post("/scenarios/{scenario_id}/counterfactuals", response_model=CounterfactualOut)
async def counterfactuals(
    scenario_id: uuid.UUID,
    body: CounterfactualRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await run_counterfactual_analysis(
            db=db,
            scenario_id=scenario_id,
            user_id=current_user.id,
            request=body,
        )
    except (ScenarioNotFoundError, AnalysisNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except StaleAnalysisError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except (InvalidOfferError, InvalidFinancialDataError, AnalysisMismatchError) as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except MissingProfileError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
