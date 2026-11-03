import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.schemas.decisions import ReceiptIn, ReceiptOut, ReceiptDetailOut
from app.services.receipt_service import ReceiptService

router = APIRouter()

@router.post("/receipts", response_model=ReceiptOut, status_code=status.HTTP_201_CREATED)
async def create_receipt(
    body: ReceiptIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ReceiptService.create_receipt(db, current_user.id, body)

@router.get("/receipts/{receipt_id}", response_model=ReceiptDetailOut)
async def get_receipt(
    receipt_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ReceiptService.get_receipt(db, receipt_id, current_user.id)

@router.get("/receipts/{receipt_id}/export")
async def export_receipt(
    receipt_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ReceiptService.export_receipt(db, receipt_id, current_user.id)
