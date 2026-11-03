import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.schemas.decisions import AlertOut
from app.services.alert_service import AlertService

router = APIRouter()

@router.get("/alerts", response_model=list[AlertOut])
async def list_alerts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await AlertService.evaluate_and_list_alerts(db, current_user.id)

@router.patch("/alerts/{alert_id}", response_model=AlertOut)
async def dismiss_alert(
    alert_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await AlertService.dismiss_alert(db, alert_id, current_user.id)
