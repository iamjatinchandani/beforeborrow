import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.schemas.decisions import AnalysisOut
from app.services.analysis import AnalysisNotFoundError, get_analysis as get_analysis_record

router = APIRouter()


@router.get("/analyses/{analysis_id}", response_model=AnalysisOut)
async def get_analysis(
    analysis_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await get_analysis_record(
            db=db,
            analysis_id=analysis_id,
            user_id=current_user.id,
        )
    except AnalysisNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
