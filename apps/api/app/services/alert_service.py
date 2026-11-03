import uuid
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models.decisions import Alert, Scenario, Analysis
from app.models.finance import Profile, Obligation, ObligationPayment
from app.repositories.alerts import AlertRepository
from app.schemas.decisions import AlertOut

KOLKATA_TZ = ZoneInfo("Asia/Kolkata")

class AlertService:
    @staticmethod
    async def evaluate_and_list_alerts(
        db: AsyncSession,
        owner_id: uuid.UUID,
        include_dismissed: bool = False,
    ) -> list[AlertOut]:
        today_kolkata = datetime.now(KOLKATA_TZ).date()

        # 1. Upcoming dues (T-3 days and T-1 day) from obligation payments
        pay_stmt = (
            select(ObligationPayment, Obligation)
            .join(Obligation, ObligationPayment.obligation_id == Obligation.id)
            .where(Obligation.owner_id == owner_id, ObligationPayment.payment_status == "scheduled")
        )
        pay_res = await db.execute(pay_stmt)
        for payment, obligation in pay_res.all():
            due = payment.due_date
            diff_days = (due - today_kolkata).days

            if diff_days == 3:
                alert_key = f"{owner_id}:due_t3:{payment.id}:{due}"
                message = f"Upcoming payment due in 3 days: ₹{payment.amount_paise // 100:,} for {obligation.provider_alias} on {due.strftime('%d %b')}."
                await AlertRepository.upsert_alert(
                    db=db,
                    owner_id=owner_id,
                    alert_key=alert_key,
                    alert_type="due_reminder_t3",
                    message=message,
                    due_date=due,
                    source_event_id=str(payment.id),
                )
            elif diff_days == 1:
                alert_key = f"{owner_id}:due_t1:{payment.id}:{due}"
                message = f"Immediate due tomorrow: ₹{payment.amount_paise // 100:,} for {obligation.provider_alias} on {due.strftime('%d %b')}."
                await AlertRepository.upsert_alert(
                    db=db,
                    owner_id=owner_id,
                    alert_key=alert_key,
                    alert_type="due_reminder_t1",
                    message=message,
                    due_date=due,
                    source_event_id=str(payment.id),
                )

        # 2. Stale financial data
        prof_stmt = select(Profile).where(Profile.owner_id == owner_id)
        prof_res = await db.execute(prof_stmt)
        profile = prof_res.scalar_one_or_none()

        if profile and profile.updated_at:
            days_since_update = (datetime.now(timezone.utc) - profile.updated_at).days
            if days_since_update > 30:
                alert_key = f"{owner_id}:stale_profile:{today_kolkata.strftime('%Y-%m')}"
                message = "Your financial profile has not been updated in over 30 days. Re-verify cash balance and recurring expenses for accurate rehearsal."
                await AlertRepository.upsert_alert(
                    db=db,
                    owner_id=owner_id,
                    alert_key=alert_key,
                    alert_type="stale_data",
                    message=message,
                    due_date=today_kolkata,
                    source_event_id="profile",
                )

        # 3. Incomplete repayment schedules
        ob_stmt = select(Obligation).where(Obligation.owner_id == owner_id, Obligation.status == "active")
        ob_res = await db.execute(ob_stmt)
        for ob in ob_res.scalars().all():
            p_stmt = select(ObligationPayment).where(ObligationPayment.obligation_id == ob.id)
            p_res = await db.execute(p_stmt)
            has_payments = p_res.first() is not None
            if not has_payments and ob.principal_remaining_paise > 0:
                alert_key = f"{owner_id}:incomplete_schedule:{ob.id}"
                message = f"Incomplete schedule: {ob.provider_alias} has remaining principal of ₹{ob.principal_remaining_paise // 100:,} but no payment dates registered."
                await AlertRepository.upsert_alert(
                    db=db,
                    owner_id=owner_id,
                    alert_key=alert_key,
                    alert_type="incomplete_schedule",
                    message=message,
                    due_date=today_kolkata,
                    source_event_id=str(ob.id),
                )

        # 4. First modeled financial pressure date from recent scenarios
        scen_stmt = (
            select(Scenario)
            .where(Scenario.owner_id == owner_id)
            .order_by(Scenario.created_at.desc())
            .limit(1)
        )
        scen_res = await db.execute(scen_stmt)
        recent_scenario = scen_res.scalar_one_or_none()

        if recent_scenario:
            pressure_date = recent_scenario.expense_date
            alert_key = f"{owner_id}:pressure_date:{recent_scenario.id}:{pressure_date}"
            message = f"Upcoming modeled pressure date on {pressure_date.strftime('%d %b')}: ₹{recent_scenario.expense_amount_paise // 100:,} urgent expense scheduled."
            await AlertRepository.upsert_alert(
                db=db,
                owner_id=owner_id,
                alert_key=alert_key,
                alert_type="modeled_pressure_date",
                message=message,
                due_date=pressure_date,
                source_event_id=str(recent_scenario.id),
            )

        # Retrieve and return
        alerts = await AlertRepository.list_by_owner(db, owner_id, include_dismissed=include_dismissed)
        return [
            AlertOut(
                id=a.id,
                alert_type=a.alert_type,
                due_date=a.due_date,
                source_event_id=a.source_event_id,
                message=a.message,
                dismissed_at=a.dismissed_at,
                created_at=a.created_at,
            )
            for a in alerts
        ]

    @staticmethod
    async def dismiss_alert(
        db: AsyncSession,
        alert_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> AlertOut:
        alert = await AlertRepository.dismiss_alert(db, alert_id, owner_id)
        if not alert:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
        return AlertOut(
            id=alert.id,
            alert_type=alert.alert_type,
            due_date=alert.due_date,
            source_event_id=alert.source_event_id,
            message=alert.message,
            dismissed_at=alert.dismissed_at,
            created_at=alert.created_at,
        )
