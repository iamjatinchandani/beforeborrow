import uuid
from typing import Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.engine.types import FinancialSnapshot
from app.models.finance import CashflowRule, Goal, Obligation, ObligationPayment, Profile


class SnapshotServiceError(Exception):
    """Base exception for snapshot service errors."""
    pass


class MissingProfileError(SnapshotServiceError):
    """Raised when a user does not have a financial profile."""
    pass


class InvalidFinancialDataError(SnapshotServiceError):
    """Raised when financial data is malformed or invalid."""
    pass


def build_financial_snapshot(
    profile: Profile,
    cashflow_rules: Sequence[CashflowRule] = (),
    obligations: Sequence[Obligation] = (),
    goals: Sequence[Goal] = (),
) -> FinancialSnapshot:
    """
    Pure adapter function mapping ORM records to an immutable engine FinancialSnapshot.
    
    Guarantees:
    - Preserves integer paise exactly without float conversion.
    - Preserves dates, timing labels, recurrence frequencies, and source identifiers.
    - Partitions CashflowRule records into income_rules and expense_rules by direction.
    - Preserves obligation payment status, due dates, and paid history.
    - Sets data_version strictly from Profile.data_version.
    - Leaves ORM records and engine objects unmutated.
    """
    if profile is None:
        raise MissingProfileError("Profile is required to construct a FinancialSnapshot")

    if profile.balance_as_of is None:
        raise InvalidFinancialDataError("Profile balance_as_of is required")

    if profile.opening_cash_paise < 0:
        raise InvalidFinancialDataError(f"opening_cash_paise cannot be negative: {profile.opening_cash_paise}")

    if profile.reserve_floor_paise < 0:
        raise InvalidFinancialDataError(f"reserve_floor_paise cannot be negative: {profile.reserve_floor_paise}")

    income_rules_list: list[dict] = []
    expense_rules_list: list[dict] = []

    for rule in cashflow_rules or ():
        dir_val = str(rule.direction).lower().strip()
        rule_dict = {
            "id": str(rule.id),
            "owner_id": str(rule.owner_id),
            "direction": dir_val,
            "category": str(rule.category),
            "amount_paise": int(rule.amount_paise),
            "due_date": rule.due_date,
            "start_date": rule.start_date,
            "frequency": str(rule.frequency).lower().strip() if rule.frequency else "once",
            "end_date": rule.end_date,
            "timing": str(rule.timing).lower().strip() if rule.timing else "known",
            "source": str(rule.source).strip() if rule.source else "manual",
            "confirmed_at": rule.confirmed_at,
        }

        if dir_val == "income":
            income_rules_list.append(rule_dict)
        elif dir_val == "expense":
            expense_rules_list.append(rule_dict)
        else:
            raise InvalidFinancialDataError(f"Invalid cashflow rule direction '{rule.direction}' for rule {rule.id}")

    obligations_list: list[dict] = []
    for ob in obligations or ():
        payments_list: list[dict] = []
        for p in getattr(ob, "payments", None) or ():
            payments_list.append({
                "id": str(p.id),
                "obligation_id": str(p.obligation_id),
                "due_date": p.due_date,
                "amount_paise": int(p.amount_paise),
                "interest_paise": int(p.interest_paise or 0),
                "fee_paise": int(p.fee_paise or 0),
                "payment_status": str(p.payment_status).lower().strip() if p.payment_status else "scheduled",
                "actual_paid_date": p.actual_paid_date,
            })

        obligations_list.append({
            "id": str(ob.id),
            "owner_id": str(ob.owner_id),
            "provider_alias": str(ob.provider_alias),
            "kind": str(ob.kind).lower().strip() if ob.kind else "other",
            "principal_remaining_paise": int(ob.principal_remaining_paise),
            "status": str(ob.status).lower().strip() if ob.status else "active",
            "source": str(ob.source).strip() if ob.source else "manual",
            "source_ref": ob.source_ref,
            "source_as_of": ob.source_as_of,
            "confirmed_at": ob.confirmed_at,
            "version": int(ob.version),
            "payments": payments_list,
        })

    goals_list: list[dict] = []
    for g in goals or ():
        goals_list.append({
            "id": str(g.id),
            "owner_id": str(g.owner_id),
            "label": str(g.label),
            "target_amount_paise": int(g.target_amount_paise),
            "target_date": g.target_date,
            "protected": bool(g.protected),
            "contribution_rule_id": str(g.contribution_rule_id) if g.contribution_rule_id else None,
        })

    return FinancialSnapshot(
        opening_cash_paise=int(profile.opening_cash_paise),
        balance_as_of=profile.balance_as_of,
        reserve_floor_paise=int(profile.reserve_floor_paise),
        income_rules=tuple(income_rules_list),
        expense_rules=tuple(expense_rules_list),
        obligations=tuple(obligations_list),
        goals=tuple(goals_list),
        data_version=int(profile.data_version),
    )


async def load_financial_snapshot(
    db: AsyncSession,
    owner_id: uuid.UUID,
) -> FinancialSnapshot:
    """
    Asynchronously queries the database for all financial records belonging to owner_id
    and builds an engine FinancialSnapshot.
    
    Guarantees:
    - Scopes all queries strictly to owner_id.
    - Prevents cross-user data leakage.
    - Raises MissingProfileError if the user has not established a financial profile.
    - Eagerly loads obligation payments within the session context.
    """
    stmt_profile = select(Profile).where(Profile.owner_id == owner_id)
    res_profile = await db.execute(stmt_profile)
    profile = res_profile.scalar_one_or_none()

    if not profile:
        raise MissingProfileError(f"No financial profile found for user {owner_id}")

    stmt_rules = (
        select(CashflowRule)
        .where(CashflowRule.owner_id == owner_id)
        .order_by(CashflowRule.created_at)
    )
    res_rules = await db.execute(stmt_rules)
    cashflow_rules = res_rules.scalars().all()

    stmt_obs = (
        select(Obligation)
        .where(Obligation.owner_id == owner_id)
        .options(selectinload(Obligation.payments))
        .order_by(Obligation.created_at)
    )
    res_obs = await db.execute(stmt_obs)
    obligations = res_obs.scalars().all()

    stmt_goals = (
        select(Goal)
        .where(Goal.owner_id == owner_id)
        .order_by(Goal.created_at)
    )
    res_goals = await db.execute(stmt_goals)
    goals = res_goals.scalars().all()

    return build_financial_snapshot(
        profile=profile,
        cashflow_rules=cashflow_rules,
        obligations=obligations,
        goals=goals,
    )
