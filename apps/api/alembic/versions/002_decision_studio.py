"""002_decision_studio

Revision ID: 002_decision_studio
Revises: 001_identity
Create Date: 2026-11-03 17:15:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002_decision_studio"
down_revision: Union[str, None] = "001_identity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Scenarios table (Person D owned)
    op.create_table(
        "scenarios",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("expense_amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("merchant", sa.String(length=128), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("need_cash", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("allowed_savings_paise", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scenarios_owner_id", "scenarios", ["owner_id"])

    # 2. Offers table (Person D owned)
    op.create_table(
        "offers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scenario_id", sa.Uuid(), nullable=False),
        sa.Column("offer_name", sa.String(length=128), nullable=True),
        sa.Column("provider", sa.String(length=128), nullable=True),
        sa.Column("offer_type", sa.String(length=32), nullable=False),
        sa.Column("principal_paise", sa.BigInteger(), nullable=False),
        sa.Column("fees_paise", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("rate_annual_pct", sa.String(length=16), server_default=sa.text("'0.00'"), nullable=False),
        sa.Column("term_months", sa.Integer(), nullable=True),
        sa.Column("availability_deadline", sa.Date(), nullable=True),
        sa.Column("eligibility_evidence", sa.Text(), nullable=True),
        sa.Column("schedule_json", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["scenario_id"], ["scenarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_offers_scenario_id", "offers", ["scenario_id"])

    # 3. Decision Receipts table (Person D owned)
    op.create_table(
        "decision_receipts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("chosen_option", sa.String(length=64), nullable=False),
        sa.Column("reflection_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("analysis_id"),
    )
    op.create_index("ix_decision_receipts_owner_id", "decision_receipts", ["owner_id"])

    # 4. Alerts table (Person D owned)
    op.create_table(
        "alerts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("alert_key", sa.String(length=256), nullable=True),
        sa.Column("alert_type", sa.String(length=64), nullable=False),
        sa.Column("source_event_id", sa.String(length=128), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("alert_key"),
    )
    op.create_index("ix_alerts_owner_id", "alerts", ["owner_id"])


def downgrade() -> None:
    op.drop_table("alerts")
    op.drop_table("decision_receipts")
    op.drop_table("offers")
    op.drop_table("scenarios")
