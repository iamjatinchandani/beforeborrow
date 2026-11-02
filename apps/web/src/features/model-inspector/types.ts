export interface CashPath {
  dates: string[]
  balances_paise: number[]
  headrooms_paise: number[]
  first_reserve_breach?: string | null
  first_negative?: string | null
  trough_paise?: number | null
  trough_date?: string | null
}

export interface ReasonEvidence {
  code: string
  date?: string | null
  event_ids?: string[]
  before_paise?: number | null
  after_paise?: number | null
  threshold_paise?: number | null
  message_key?: string
  assumptions?: string[]
}

export interface OfferResult {
  offer_id: string
  funding_gap_paise: number
  cash_required_now_paise: number
  total_repayment_paise: number
  financing_cost_paise: number
  remaining_balance_paise: number
  shortfall_paise: number
  cash_path: CashPath
  pressure_windows: [string, string][]
  reason_codes: string[]
  excluded_obligations: string[]
  status: string
  band: string
  payoff_date?: string | null
  evidence?: ReasonEvidence[]
  trough_paise?: number | null
  trough_date?: string | null
  first_negative?: string | null
  first_reserve_breach?: string | null
  is_long_term_cost_unavailable?: boolean
}

export interface AnalysisResult {
  baseline: CashPath
  offers: OfferResult[]
  model_version: string
  stress_results?: Record<string, OfferResult[]>
}

export interface AnalysisOut {
  id: string
  scenario_id: string
  result_json: string
  model_version: string
  source_data_version: number
  calculated_at: string
  stale: boolean
  snapshot_hash?: string | null
}

export interface GoalImpactOut {
  goal_id: string
  label: string
  target_amount_paise: number
  target_date?: string | null
  protected: boolean
  baseline_contribution_paise: number
  candidate_contribution_paise: number
  target_funding_gap_paise: number
  status: string
}

export interface AlternativeOut {
  description: string
  changes: Record<string, unknown>
  assumptions: string[]
  financing_cost_diff_paise: number
  min_cash_diff_paise: number
  tradeoffs: string[]
  approval_dependencies: string[]
  goal_impacts: GoalImpactOut[]
  user_changes_count: number
  full_financing_cost_paise: number
  min_cash_paise: number
}

export interface CounterfactualRequest {
  analysis_id: string
  allowed_changes: string[]
  bounds: Record<string, unknown>
}

export interface CounterfactualOut {
  feasible: AlternativeOut[]
  no_feasible_plan: boolean
  binding_causes: string[]
  tested_count: number
  bounds: Record<string, unknown>
  truncated: boolean
  insufficient_data: boolean
  missing_fields: string[]
  evidence: ReasonEvidence[]
}

export type OutcomeBand =
  | 'within_stated_assumptions'
  | 'stress_sensitive'
  | 'buffer_breach'
  | 'shortfall'
  | 'funding_gap'
  | 'insufficient_data'

export const OUTCOME_BAND_DETAILS: Record<
  OutcomeBand,
  { label: string; status: 'ok' | 'caution' | 'shortfall' | 'unknown'; description: string }
> = {
  within_stated_assumptions: {
    label: 'Within Stated Assumptions',
    status: 'ok',
    description: 'Cash remains at or above the reserve floor in the baseline and all selected stress cases.',
  },
  stress_sensitive: {
    label: 'Stress Sensitive',
    status: 'caution',
    description: 'Baseline maintains reserve, but cash drops below reserve floor in at least one simulated stress scenario.',
  },
  buffer_breach: {
    label: 'Buffer Breach',
    status: 'caution',
    description: 'Balance drops below the emergency reserve floor, but does not fall below zero.',
  },
  shortfall: {
    label: 'Liquidity Shortfall',
    status: 'shortfall',
    description: 'Cash drops below zero on one or more dates. Projected cash deficit.',
  },
  funding_gap: {
    label: 'Funding Gap',
    status: 'shortfall',
    description: 'Usable credit and allowed savings are insufficient to cover the expense.',
  },
  insufficient_data: {
    label: 'Insufficient Data',
    status: 'unknown',
    description: 'Required financial inputs or repayment terms are missing or estimated.',
  },
}
