import uuid
from datetime import date, datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.decisions import Alert

class AlertRepository:
    @staticmethod
    async def list_by_owner(
        db: AsyncSession,
        owner_id: uuid.UUID,
        include_dismissed: bool = False,
    ) -> list[Alert]:
        stmt = select(Alert).where(Alert.owner_id == owner_id)
        if not include_dismissed:
            stmt = stmt.where(Alert.dismissed_at.is_(None))
        stmt = stmt.order_by(Alert.due_date.asc().nulls_last(), Alert.created_at.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        alert_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> Alert | None:
        stmt = select(Alert).where(Alert.id == alert_id, Alert.owner_id == owner_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def upsert_alert(
        db: AsyncSession,
        owner_id: uuid.UUID,
        alert_key: str,
        alert_type: str,
        message: str,
        due_date: date | None = None,
        source_event_id: str | None = None,
    ) -> Alert:
        stmt = select(Alert).where(Alert.alert_key == alert_key)
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # If not dismissed, update message
            if existing.dismissed_at is None:
                existing.message = message
                await db.commit()
                await db.refresh(existing)
            return existing

        alert = Alert(
            owner_id=owner_id,
            alert_key=alert_key,
            alert_type=alert_type,
            message=message,
            due_date=due_date,
            source_event_id=source_event_id,
        )
        db.add(alert)
        await db.commit()
        await db.refresh(alert)
        return alert

    @staticmethod
    async def dismiss_alert(
        db: AsyncSession,
        alert_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> Alert | None:
        alert = await AlertRepository.get_by_id(db, alert_id, owner_id)
        if not alert:
            return None
        alert.dismissed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(alert)
        return alert
