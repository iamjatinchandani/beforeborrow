import uuid
from datetime import date, datetime
from pydantic import BaseModel, field_validator

class OfferIn(BaseModel):
    offer_name: str | None = None
    provider: str | None = None
    offer_type: str  # "personal_loan" | "credit_card" | "bnpl" | "other"
    principal_paise: int
    fees_paise: int = 0
    rate_annual_pct: str = "0.00"
    term_months: int | None = None
    availability_deadline: date | None = None
    eligibility_evidence: str | None = None
    schedule_json: str | None = None

    @field_validator("principal_paise", "fees_paise")
    @classmethod
    def non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Amount cannot be negative")
        return v

class OfferOut(BaseModel):
    id: uuid.UUID
    scenario_id: uuid.UUID
    offer_name: str | None = None
    provider: str | None = None
    offer_type: str
    principal_paise: int
    fees_paise: int
    rate_annual_pct: str
    term_months: int | None = None
    availability_deadline: date | None = None
    eligibility_evidence: str | None = None
    schedule_json: str | None = None

    model_config = {"from_attributes": True}

class ScenarioIn(BaseModel):
    expense_amount_paise: int
    expense_date: date
    merchant: str | None = None
    category: str | None = None
    need_cash: bool = False
    allowed_savings_paise: int = 0
    horizon_days: int = 180
    offers: list[OfferIn] = []

    @field_validator("expense_amount_paise", "allowed_savings_paise")
    @classmethod
    def non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Amount cannot be negative")
        return v

    @field_validator("horizon_days")
    @classmethod
    def valid_horizon(cls, v: int) -> int:
        if v <= 0 or v > 1825:
            raise ValueError("Horizon days must be between 1 and 1825")
        return v

    @field_validator("offers")
    @classmethod
    def max_three_offers(cls, v: list[OfferIn]) -> list[OfferIn]:
        if len(v) > 3:
            raise ValueError("A maximum of 3 comparable offers can be added to a scenario")
        return v

class ScenarioOut(BaseModel):
    id: uuid.UUID
    expense_amount_paise: int
    expense_date: date
    merchant: str | None = None
    category: str | None = None
    need_cash: bool
    allowed_savings_paise: int
    horizon_days: int
    version: int
    created_at: datetime
    offers: list[OfferOut] = []

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

    model_config = {"from_attributes": True}

class CounterfactualRequest(BaseModel):
    analysis_id: uuid.UUID
    allowed_changes: list[str] = []
    bounds: dict = {}

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

class ReceiptDetailOut(BaseModel):
    id: uuid.UUID
    analysis_id: uuid.UUID
    chosen_option: str
    reflection_answers: dict | None = None
    created_at: datetime
    stale: bool = False
    context: dict
    consequences: dict
    uncertainty: dict

    model_config = {"from_attributes": True}

class AlertOut(BaseModel):
    id: uuid.UUID
    alert_type: str
    due_date: date | None = None
    source_event_id: str | None = None
    message: str
    dismissed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
