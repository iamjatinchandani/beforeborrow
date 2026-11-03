export interface OfferItem {
  id?: string
  scenario_id?: string
  offer_name?: string
  provider?: string
  offer_type: 'personal_loan' | 'credit_card' | 'bnpl' | 'other'
  principal_paise: number
  fees_paise: number
  rate_annual_pct: string
  term_months?: number
  availability_deadline?: string
  eligibility_evidence?: string
  schedule_json?: string
  is_demo?: boolean
}

export interface ScenarioData {
  id?: string
  expense_amount_paise: number
  expense_date: string
  merchant?: string
  category?: string
  need_cash: boolean
  allowed_savings_paise: number
  horizon_days: number
  version?: number
  created_at?: string
  offers: OfferItem[]
}

export interface SetupStatus {
  is_complete: boolean
  missing_fields: string[]
  has_profile: boolean
  profile_data_version: number
  obligations_count: number
}

export interface ChartPoint {
  date: string
  balance_paise: number
  reserve_floor_paise: number
  is_breach: boolean
  is_negative: boolean
}

export interface LedgerEvent {
  date: string
  description: string
  inflow_paise: number
  outflow_paise: number
  balance_paise: number
  source: string
}

export interface CauseItem {
  date: string
  title: string
  detail: string
  source_event: string
}

export interface OfferAnalysisResult {
  offer_id: string
  offer_name: string
  provider: string
  offer_type: string
  is_demo: boolean
  funding_gap_paise: number
  cash_required_now_paise: number
  total_repayment_paise: number
  financing_cost_paise: number
  monthly_installment_paise: number
  term_months: number
  trough_paise: number
  trough_date: string
  first_reserve_breach?: string | null
  first_negative?: string | null
  remaining_balance_paise: number
  chart_points: ChartPoint[]
  ledger: LedgerEvent[]
  causes: CauseItem[]
  reason_codes: string[]
  status: 'feasible' | 'warning' | 'infeasible'
}

export interface AnalysisPayload {
  model_version: string
  calculated_at: string
  reserve_floor_paise: number
  opening_cash_paise: number
  expense_amount_paise: number
  expense_date: string
  baseline: {
    trough_paise: number
    trough_date: string
    first_reserve_breach?: string | null
    first_negative?: string | null
  }
  offers: OfferAnalysisResult[]
  stress_results: Record<string, string>
}

export interface AnalysisResponse {
  id: string
  scenario_id: string
  result_json: string
  model_version: string
  source_data_version: number
  calculated_at: string
  stale: boolean
}

export interface CounterfactualAlternative {
  id: string
  title: string
  description: string
  changes: Record<string, unknown>
  consequence_summary: string
  risk_assessment: string
  is_modeled_possibility: boolean
}

export interface CounterfactualResponse {
  alternatives: CounterfactualAlternative[]
  no_feasible_plan: boolean
  binding_constraints: string[]
  disclaimer: string
}
