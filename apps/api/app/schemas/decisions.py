import uuid
import datetime as dt_module
from datetime import date, datetime
from typing import Any
from pydantic import BaseModel

class OfferIn(BaseModel):
    offer_type: str
    principal_paise: int
    fees_paise: int = 0
    rate_annual_pct: str = "0.00"
    term_months: int | None = None
    availability_deadline: date | None = None
    eligibility_evidence: str | None = None
    schedule_json: str | None = None

class ScenarioIn(BaseModel):
    expense_amount_paise: int
    expense_date: date
    merchant: str | None = None
    category: str | None = None
    need_cash: bool = False
    allowed_savings_paise: int = 0
    horizon_days: int
    offers: list[OfferIn] = []

class ScenarioOut(BaseModel):
    id: uuid.UUID
    expense_amount_paise: int
    expense_date: date
    need_cash: bool
    allowed_savings_paise: int
    horizon_days: int
    version: int
    created_at: datetime

    model_config = {"from_attributes": True}

class AnalyzeRequest(BaseModel):
    scenario_version: int
    expected_data_version: int
    stress_cases: list[str] = []

class AnalysisOut(BaseModel):
    id: uuid.UUID
    scenario_id: uuid.UUID
    result_json: str
    model_version: str
    source_data_version: int
    calculated_at: datetime
    stale: bool = False
    snapshot_hash: str | None = None

    model_config = {"from_attributes": True}

class CounterfactualRequest(BaseModel):
    analysis_id: uuid.UUID
    allowed_changes: list[str]
    bounds: dict

class GoalImpactOut(BaseModel):
    goal_id: str
    label: str
    target_amount_paise: int
    target_date: date | None = None
    protected: bool = False
    baseline_contribution_paise: int = 0
    candidate_contribution_paise: int = 0
    target_funding_gap_paise: int = 0
    status: str = "on_track"

    model_config = {"from_attributes": True}

class ReasonEvidenceOut(BaseModel):
    code: str
    date: dt_module.date | None = None
    event_ids: list[str] = []
    before_paise: int | None = None
    after_paise: int | None = None
    threshold_paise: int | None = None
    message_key: str = ""
    assumptions: list[str] = []

    model_config = {"from_attributes": True}

class AlternativeOut(BaseModel):
    description: str
    changes: dict[str, Any] = {}
    assumptions: list[str] = []
    financing_cost_diff_paise: int = 0
    min_cash_diff_paise: int = 0
    tradeoffs: list[str] = []
    approval_dependencies: list[str] = []
    goal_impacts: list[GoalImpactOut] = []
    user_changes_count: int = 0
    full_financing_cost_paise: int = 0
    min_cash_paise: int = 0

    model_config = {"from_attributes": True}

class CounterfactualOut(BaseModel):
    feasible: list[AlternativeOut] = []
    no_feasible_plan: bool = False
    binding_causes: list[str] = []
    tested_count: int = 0
    bounds: dict[str, Any] = {}
    truncated: bool = False
    insufficient_data: bool = False
    missing_fields: list[str] = []
    evidence: list[ReasonEvidenceOut] = []

    model_config = {"from_attributes": True}

AlternativesOut = CounterfactualOut

class ReceiptIn(BaseModel):
    analysis_id: uuid.UUID
    chosen_option: str
    reflection_answers: dict | None = None

class ReceiptOut(BaseModel):
    id: uuid.UUID
    analysis_id: uuid.UUID
    chosen_option: str
    created_at: datetime

    model_config = {"from_attributes": True}

class AlertOut(BaseModel):
    id: uuid.UUID
    alert_type: str
    due_date: date | None
    message: str
    dismissed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
