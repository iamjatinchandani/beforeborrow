import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.decisions import DecisionReceipt, Analysis

class ReceiptRepository:
    @staticmethod
    async def create(
        db: AsyncSession,
        owner_id: uuid.UUID,
        analysis_id: uuid.UUID,
        chosen_option: str,
        reflection_json: str | None = None,
    ) -> DecisionReceipt:
        receipt = DecisionReceipt(
            owner_id=owner_id,
            analysis_id=analysis_id,
            chosen_option=chosen_option,
            reflection_json=reflection_json,
        )
        db.add(receipt)
        await db.commit()
        await db.refresh(receipt, ["analysis"])
        return receipt

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        receipt_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> DecisionReceipt | None:
        stmt = (
            select(DecisionReceipt)
            .where(DecisionReceipt.id == receipt_id, DecisionReceipt.owner_id == owner_id)
            .options(selectinload(DecisionReceipt.analysis))
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_analysis_id(
        db: AsyncSession,
        analysis_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> DecisionReceipt | None:
        stmt = (
            select(DecisionReceipt)
            .where(DecisionReceipt.analysis_id == analysis_id, DecisionReceipt.owner_id == owner_id)
            .options(selectinload(DecisionReceipt.analysis))
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_owner(db: AsyncSession, owner_id: uuid.UUID) -> list[DecisionReceipt]:
        stmt = (
            select(DecisionReceipt)
            .where(DecisionReceipt.owner_id == owner_id)
            .options(selectinload(DecisionReceipt.analysis))
            .order_by(DecisionReceipt.created_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())
