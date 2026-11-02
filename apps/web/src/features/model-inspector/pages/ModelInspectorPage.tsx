import { useMemo, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { AlertTriangle, ChevronDown, ChevronUp, RefreshCw, Search } from 'lucide-react'

import { useMe } from '@/features/auth/hooks'
import { useAnalysis, useCounterfactualMutation } from '../hooks'
import { AnalysisMetric } from '../components/AnalysisMetric'
import { ReasonList } from '../components/ReasonList'
import {
  AnalysisResult,
  CounterfactualOut,
  OfferResult,
  OUTCOME_BAND_DETAILS,
  OutcomeBand,
} from '../types'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorPanel } from '@/components/ui/ErrorPanel'
import { Money } from '@/components/ui/Money'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { formatFinancialDate, formatTimestamp } from '@/lib/dates'

const STRESS_DESCRIPTIONS: Record<string, { label: string; assumption: string }> = {
  income_delay_7d: {
    label: 'Salary Delayed by 7 Days',
    assumption: 'Shifts all recurring salary credits 7 calendar days into the future.',
  },
  income_drop_20pct_next_2: {
    label: '20% Income Reduction (Next 2 Events)',
    assumption: 'Applies a 20% haircut to the next two scheduled income arrivals.',
  },
  expense_spike_5000_30d: {
    label: '₹5,000 Unplanned Expense (+30 Days)',
    assumption: 'Injects an unplanned ₹5,000 emergency outflow exactly 30 days after balance date.',
  },
}

export default function ModelInspectorPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const queryAnalysisId = searchParams.get('analysis_id') || searchParams.get('id') || ''
  const queryScenarioId = searchParams.get('scenario_id') || ''

  const [inputAnalysisId, setInputAnalysisId] = useState(queryAnalysisId)
  const [selectedOfferIndex, setSelectedOfferIndex] = useState(0)
  const [showTable, setShowTable] = useState(false)
  const [counterfactualResult, setCounterfactualResult] = useState<CounterfactualOut | null>(null)

  const { data: currentUser } = useMe()
  const userId = currentUser?.id ?? ''

  const {
    data: analysisData,
    isLoading,
    isError,
    error,
    refetch,
  } = useAnalysis(userId, queryAnalysisId)

  const counterfactualMutation = useCounterfactualMutation()

  // Parse result_json safely
  const parsedResult: AnalysisResult | null = useMemo(() => {
    if (!analysisData?.result_json) return null
    try {
      return JSON.parse(analysisData.result_json) as AnalysisResult
    } catch {
      return null
    }
  }, [analysisData?.result_json])

  const selectedOffer: OfferResult | undefined = parsedResult?.offers?.[selectedOfferIndex]

  // Prepare chart data combining baseline and candidate cash paths
  const chartData = useMemo(() => {
    if (!parsedResult) return []
    const baseDates = parsedResult.baseline.dates
    const baseBalances = parsedResult.baseline.balances_paise
    const candBalances = selectedOffer?.cash_path?.balances_paise ?? []

    return baseDates.map((d, i) => ({
      date: formatFinancialDate(d),
      rawDate: d,
      baselineRupees: Math.round((baseBalances[i] ?? 0) / 100),
      candidateRupees:
        candBalances[i] !== undefined ? Math.round(candBalances[i] / 100) : null,
      zero: 0,
    }))
  }, [parsedResult, selectedOffer])

  const handleSearchSubmit = (e: FormEvent) => {
    e.preventDefault()
    const trimmed = inputAnalysisId.trim()
    if (trimmed) {
      setSearchParams({ analysis_id: trimmed, ...(queryScenarioId ? { scenario_id: queryScenarioId } : {}) })
      setCounterfactualResult(null)
    }
  }

  const handleRunCounterfactuals = async () => {
    const scenarioId = analysisData?.scenario_id || queryScenarioId
    if (!scenarioId || !queryAnalysisId) return

    try {
      const res = await counterfactualMutation.mutateAsync({
        scenarioId,
        body: {
          analysis_id: queryAnalysisId,
          allowed_changes: ['savings', 'discretionary_expenses', 'loan_tenure'],
          bounds: {
            max_savings_paise: 5000000,
            min_savings_paise: 0,
            savings_step_paise: 50000,
          },
        },
      })
      setCounterfactualResult(res)
    } catch {
      // Error handled by mutation state
    }
  }

  // 1. Initial State: No Analysis ID entered
  if (!queryAnalysisId) {
    return (
      <div style={{ maxWidth: '900px', margin: '0 auto', padding: '32px 16px' }}>
        <h1 style={{ fontSize: '26px', fontWeight: 700, color: 'var(--color-text, #0f172a)', marginBottom: '8px' }}>
          Model Inspector
        </h1>
        <p style={{ color: 'var(--color-muted, #64748b)', marginBottom: '24px' }}>
          Inspect deterministic cashflow rehearsals, stress testing sensitivities, and bounded counterfactuals.
        </p>

        <Card padding="lg">
          <form onSubmit={handleSearchSubmit} style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            <div style={{ flex: '1 1 300px' }}>
              <label
                htmlFor="analysis-id-input"
                style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}
              >
                Enter Analysis ID (UUID)
              </label>
              <input
                id="analysis-id-input"
                type="text"
                value={inputAnalysisId}
                onChange={(e) => setInputAnalysisId(e.target.value)}
                placeholder="e.g. 550e8400-e29b-41d4-a716-446655440000"
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  borderRadius: 'var(--radius-sm, 8px)',
                  border: '1px solid var(--color-border, #cbd5e1)',
                  fontSize: '14px',
                  fontFamily: 'var(--font-mono, monospace)',
                }}
              />
            </div>
            <div style={{ alignSelf: 'flex-end' }}>
              <Button type="submit" variant="primary" disabled={!inputAnalysisId.trim()}>
                <Search size={16} /> Load Analysis
              </Button>
            </div>
          </form>

          <EmptyState
            title="No Analysis Selected"
            description="Provide an authorized analysis ID above or open this inspector directly from a scenario rehearsal to review the calculation ledger."
          />
        </Card>
      </div>
    )
  }

  // 2. Loading State
  if (isLoading) {
    return (
      <div style={{ maxWidth: '900px', margin: '0 auto', padding: '48px 16px', textAlign: 'center' }}>
        <div style={{ display: 'inline-block', animation: 'spin 1s linear infinite', marginBottom: '16px' }}>
          <RefreshCw size={32} color="var(--color-primary, #0d9488)" />
        </div>
        <h2 style={{ fontSize: '20px', fontWeight: 600, color: 'var(--color-text, #0f172a)' }}>
          Loading Analysis Record...
        </h2>
        <p style={{ color: 'var(--color-muted, #64748b)' }}>Retrieving immutable engine output from server.</p>
      </div>
    )
  }

  // 3. Error State
  if (isError || !analysisData) {
    const errorMsg =
      (error as { error?: { message?: string } })?.error?.message ??
      (error as Error)?.message ??
      'Failed to load analysis record.'

    return (
      <div style={{ maxWidth: '900px', margin: '0 auto', padding: '32px 16px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 700, marginBottom: '16px' }}>Model Inspector</h1>
        <ErrorPanel
          message={`Unable to load analysis: ${errorMsg}`}
          onRetry={() => refetch()}
        />
        <div style={{ marginTop: '16px' }}>
          <Button variant="secondary" onClick={() => setSearchParams({})}>
            Back to Search
          </Button>
        </div>
      </div>
    )
  }

  // Band details
  const currentBandKey = (selectedOffer?.band || selectedOffer?.status || 'insufficient_data') as OutcomeBand
  const bandInfo = OUTCOME_BAND_DETAILS[currentBandKey] ?? OUTCOME_BAND_DETAILS.insufficient_data

  return (
    <div style={{ maxWidth: '1100px', margin: '0 auto', padding: '32px 16px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header & Meta Bar */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-primary, #0d9488)', textTransform: 'uppercase' }}>
              Decision Engine Audit
            </span>
            <h1 style={{ fontSize: '26px', fontWeight: 800, color: 'var(--color-text, #0f172a)', margin: '4px 0' }}>
              Model Inspector
            </h1>
          </div>

          <form onSubmit={handleSearchSubmit} style={{ display: 'flex', gap: '8px' }}>
            <input
              type="text"
              value={inputAnalysisId}
              onChange={(e) => setInputAnalysisId(e.target.value)}
              placeholder="Analysis ID"
              style={{
                padding: '6px 12px',
                fontSize: '13px',
                fontFamily: 'monospace',
                borderRadius: '6px',
                border: '1px solid #cbd5e1',
                width: '260px',
              }}
            />
            <Button type="submit" size="sm" variant="secondary">
              Inspect
            </Button>
          </form>
        </div>

        {/* Staleness Banner */}
        {analysisData.stale && (
          <div
            role="alert"
            style={{
              background: '#fffbeb',
              border: '1px solid #fef3c7',
              borderRadius: '8px',
              padding: '12px 16px',
              marginTop: '16px',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              color: '#92400e',
            }}
          >
            <AlertTriangle size={20} color="#b45309" />
            <div style={{ fontSize: '14px' }}>
              <strong>Stale Analysis:</strong> Underlying scenario or financial profile data has incremented since this
              calculation was executed. Re-rehearsal will yield a new immutable version.
            </div>
          </div>
        )}
      </div>

      {/* 1. Analysis Summary Card */}
      <Card padding="md">
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '16px',
            alignItems: 'center',
          }}
        >
          <div>
            <span style={{ fontSize: '12px', color: 'var(--color-muted, #64748b)', display: 'block' }}>
              Outcome Verdict
            </span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
              <StatusBadge status={bandInfo.status} label={bandInfo.label} />
              {analysisData.stale && <StatusBadge status="caution" label="STALE" />}
            </div>
            <p style={{ fontSize: '12px', color: 'var(--color-muted, #64748b)', margin: '4px 0 0 0' }}>
              {bandInfo.description}
            </p>
          </div>

          <div>
            <span style={{ fontSize: '12px', color: 'var(--color-muted, #64748b)', display: 'block' }}>
              Engine Version
            </span>
            <span style={{ fontFamily: 'monospace', fontWeight: 600, fontSize: '14px' }}>
              {analysisData.model_version || 'rules-v1'}
            </span>
          </div>

          <div>
            <span style={{ fontSize: '12px', color: 'var(--color-muted, #64748b)', display: 'block' }}>
              Calculated At (Asia/Kolkata)
            </span>
            <span style={{ fontSize: '14px', fontWeight: 500 }}>
              {analysisData.calculated_at ? formatTimestamp(analysisData.calculated_at) : 'Not available'}
            </span>
          </div>

          <div>
            <span style={{ fontSize: '12px', color: 'var(--color-muted, #64748b)', display: 'block' }}>
              Snapshot Hash (SHA-256)
            </span>
            <span
              style={{
                fontFamily: 'monospace',
                fontSize: '11px',
                color: '#475569',
                wordBreak: 'break-all',
              }}
              title={analysisData.snapshot_hash || 'Snapshot hash not available'}
            >
              {analysisData.snapshot_hash
                ? `${analysisData.snapshot_hash.slice(0, 16)}...${analysisData.snapshot_hash.slice(-8)}`
                : 'Not available'}
            </span>
          </div>
        </div>
      </Card>

      {/* Offer Selection Tabs (if multiple offers evaluated) */}
      {parsedResult && parsedResult.offers && parsedResult.offers.length > 1 && (
        <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid #e2e8f0', paddingBottom: '8px' }}>
          {parsedResult.offers.map((offer, idx) => (
            <Button
              key={offer.offer_id || idx}
              size="sm"
              variant={selectedOfferIndex === idx ? 'primary' : 'secondary'}
              onClick={() => setSelectedOfferIndex(idx)}
            >
              Option {idx + 1}: {offer.offer_id}
            </Button>
          ))}
        </div>
      )}

      {/* 2. Financial Metrics Grid */}
      <div>
        <h2 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--color-text, #0f172a)', marginBottom: '12px' }}>
          Financial Metrics & Commitments
        </h2>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '16px',
          }}
        >
          <AnalysisMetric
            label="Total Repayment"
            value={selectedOffer?.total_repayment_paise}
            type="paise"
            description="Contractual outflow across all scheduled installments."
          />

          <AnalysisMetric
            label="Full Financing Cost"
            value={selectedOffer?.financing_cost_paise}
            type="paise"
            shortfall={false}
            description="Mandatory borrowing cost beyond the net credit benefit."
          />

          <AnalysisMetric
            label="Upfront Cash Required"
            value={selectedOffer?.cash_required_now_paise}
            type="paise"
            description="Cash needed today (down-payment, upfront fees, immediate due)."
          />

          <AnalysisMetric
            label="Minimum Cash (Trough)"
            value={selectedOffer?.trough_paise ?? selectedOffer?.cash_path?.trough_paise}
            type="paise"
            shortfall={
              (selectedOffer?.trough_paise ?? selectedOffer?.cash_path?.trough_paise ?? 0) < 0
            }
            subtext={
              selectedOffer?.trough_date || selectedOffer?.cash_path?.trough_date
                ? `Trough on ${formatFinancialDate(selectedOffer.trough_date || selectedOffer.cash_path.trough_date!)}`
                : undefined
            }
            description="Lowest intraday cash balance projected through the horizon."
          />

          <AnalysisMetric
            label="First Reserve Breach"
            value={
              selectedOffer?.first_reserve_breach ||
              selectedOffer?.cash_path?.first_reserve_breach ||
              'None'
            }
            type={
              selectedOffer?.first_reserve_breach || selectedOffer?.cash_path?.first_reserve_breach
                ? 'date'
                : 'text'
            }
            description="First date where bank balance dips below user reserve floor."
          />

          <AnalysisMetric
            label="Debt Beyond Horizon"
            value={selectedOffer?.remaining_balance_paise}
            type="paise"
            description="Principal remaining beyond horizon so long tenures cannot hide cost."
          />
        </div>
      </div>

      {/* 3. Cash Path Visualization */}
      <Card padding="md">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
          <div>
            <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0 }}>Cash Path Simulation</h2>
            <p style={{ fontSize: '13px', color: 'var(--color-muted, #64748b)', margin: '2px 0 0 0' }}>
              Baseline commitments vs candidate rehearsal through 180-day modeled horizon.
            </p>
          </div>

          <Button size="sm" variant="secondary" onClick={() => setShowTable(!showTable)}>
            {showTable ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            {showTable ? 'Hide Data Table' : 'Show Data Table'}
          </Button>
        </div>

        <div style={{ width: '100%', height: '320px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis
                tick={{ fontSize: 11 }}
                tickFormatter={(val: number) => `₹${val.toLocaleString('en-IN')}`}
              />
              <Tooltip
                formatter={(val: number) => [`₹${Number(val).toLocaleString('en-IN')}`, '']}
                labelStyle={{ fontWeight: 600 }}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <ReferenceLine y={0} stroke="#ef4444" strokeDasharray="4 4" label="Deficit (₹0)" />
              <Line
                type="monotone"
                dataKey="baselineRupees"
                name="Baseline Cash (₹)"
                stroke="#64748b"
                dot={false}
                strokeWidth={2}
              />
              <Line
                type="monotone"
                dataKey="candidateRupees"
                name="Candidate Cash (₹)"
                stroke="#0d9488"
                dot={{ r: 2 }}
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Tabular Equivalent for Accessibility */}
        {showTable && (
          <div style={{ marginTop: '20px', overflowX: 'auto' }}>
            <table
              style={{
                width: '100%',
                borderCollapse: 'collapse',
                fontSize: '13px',
                textAlign: 'left',
              }}
              aria-label="Simulation Cash Path Table"
            >
              <thead>
                <tr style={{ background: '#f8fafc', borderBottom: '2px solid #cbd5e1' }}>
                  <th style={{ padding: '8px 12px' }}>Date</th>
                  <th style={{ padding: '8px 12px' }}>Baseline Balance</th>
                  <th style={{ padding: '8px 12px' }}>Candidate Balance</th>
                  <th style={{ padding: '8px 12px' }}>Modeled Net Effect</th>
                </tr>
              </thead>
              <tbody>
                {chartData.map((row, idx) => {
                  const netDiff =
                    row.candidateRupees !== null ? row.candidateRupees - row.baselineRupees : null
                  return (
                    <tr
                      key={idx}
                      style={{
                        borderBottom: '1px solid #f1f5f9',
                        background: (row.candidateRupees ?? 0) < 0 ? '#fef2f2' : undefined,
                      }}
                    >
                      <td style={{ padding: '6px 12px', fontWeight: 500 }}>{row.date}</td>
                      <td style={{ padding: '6px 12px' }}>₹{row.baselineRupees.toLocaleString('en-IN')}</td>
                      <td style={{ padding: '6px 12px' }}>
                        {row.candidateRupees !== null
                          ? `₹${row.candidateRupees.toLocaleString('en-IN')}`
                          : '—'}
                      </td>
                      <td
                        style={{
                          padding: '6px 12px',
                          color: netDiff !== null && netDiff < 0 ? '#b91c1c' : '#15803d',
                          fontWeight: 500,
                        }}
                      >
                        {netDiff !== null
                          ? `${netDiff >= 0 ? '+' : ''}₹${netDiff.toLocaleString('en-IN')}`
                          : '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* 4. Stress Results */}
      <div>
        <h2 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--color-text, #0f172a)', marginBottom: '6px' }}>
          Sensitivity & Stress Tests
        </h2>
        <p style={{ fontSize: '13px', color: 'var(--color-muted, #64748b)', marginBottom: '16px' }}>
          Deterministic transformations test whether this choice survives real-world timing frictions. Stress pass
          counts represent sensitivity bounds, never credit approval scores or probabilities.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px' }}>
          {['income_delay_7d', 'income_drop_20pct_next_2', 'expense_spike_5000_30d'].map((caseName) => {
            const stressOfferList = parsedResult?.stress_results?.[caseName]
            const stressOffer = stressOfferList?.[selectedOfferIndex] ?? stressOfferList?.[0]
            const desc = STRESS_DESCRIPTIONS[caseName] ?? { label: caseName, assumption: 'Custom stress case' }

            const stressBand = (stressOffer?.band || stressOffer?.status || 'unknown') as OutcomeBand
            const stressBandInfo = OUTCOME_BAND_DETAILS[stressBand] ?? OUTCOME_BAND_DETAILS.insufficient_data

            return (
              <div
                key={caseName}
                style={{
                  background: '#ffffff',
                  border: '1px solid var(--color-border, #e2e8f0)',
                  borderRadius: 'var(--radius, 12px)',
                  padding: '16px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontWeight: 600, fontSize: '14px', color: '#0f172a' }}>{desc.label}</span>
                  <StatusBadge status={stressBandInfo.status} label={stressBandInfo.label} />
                </div>

                <p style={{ fontSize: '12px', color: '#64748b', margin: 0, minHeight: '32px' }}>
                  {desc.assumption}
                </p>

                <div
                  style={{
                    marginTop: '8px',
                    padding: '8px 12px',
                    background: '#f8fafc',
                    borderRadius: '8px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    fontSize: '12px',
                  }}
                >
                  <span>Stressed Trough:</span>
                  <strong>
                    {stressOffer?.trough_paise !== undefined && stressOffer.trough_paise !== null ? (
                      <Money paise={stressOffer.trough_paise} shortfall={stressOffer.trough_paise < 0} />
                    ) : (
                      '—'
                    )}
                  </strong>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* 5. Counterfactual Alternatives */}
      <Card padding="md">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px', marginBottom: '16px' }}>
          <div>
            <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0 }}>Feasible Alternatives (Counterfactuals)</h2>
            <p style={{ fontSize: '13px', color: 'var(--color-muted, #64748b)', margin: '2px 0 0 0' }}>
              Bounded search identifies concrete allowed changes that remove the modeled breach (₹500 savings steps, max 500 candidates).
            </p>
          </div>

          <Button
            size="sm"
            variant="primary"
            loading={counterfactualMutation.isPending}
            onClick={handleRunCounterfactuals}
          >
            Run Counterfactual Search
          </Button>
        </div>

        {counterfactualMutation.isError && (
          <div style={{ marginBottom: '16px' }}>
            <ErrorPanel message="Failed to execute counterfactual search. Check server connection." />
          </div>
        )}

        {counterfactualResult && (
          <div>
            {counterfactualResult.no_feasible_plan ? (
              <div
                style={{
                  background: '#fef2f2',
                  border: '1px solid #fecaca',
                  borderRadius: '8px',
                  padding: '16px',
                  color: '#991b1b',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 700, fontSize: '15px' }}>
                  <AlertTriangle size={18} /> No Feasible Plan Found Within Searched Bounds
                </div>
                <p style={{ fontSize: '13px', margin: '8px 0' }}>
                  Tested {counterfactualResult.tested_count} candidate combinations without satisfying base and stress reserve
                  constraints.
                </p>
                {counterfactualResult.binding_causes && counterfactualResult.binding_causes.length > 0 && (
                  <div style={{ fontSize: '12px', marginTop: '8px' }}>
                    <strong>Binding Causes:</strong>
                    <ul style={{ margin: '4px 0 0 0', paddingLeft: '20px' }}>
                      {counterfactualResult.binding_causes.map((cause, cIdx) => (
                        <li key={cIdx}>{cause}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div style={{ fontSize: '13px', color: '#64748b' }}>
                  Evaluated {counterfactualResult.tested_count} candidates. Returning top {counterfactualResult.feasible.length} feasible alternatives ranked lexicographically:
                </div>

                {counterfactualResult.feasible.map((alt, aIdx) => (
                  <div
                    key={aIdx}
                    style={{
                      background: '#f8fafc',
                      border: '1px solid #cbd5e1',
                      borderRadius: '8px',
                      padding: '14px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '8px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ fontWeight: 700, fontSize: '15px', color: '#0f172a' }}>
                        Alternative #{aIdx + 1}: {alt.description}
                      </span>
                      <StatusBadge status="ok" label="FEASIBLE" />
                    </div>

                    <div
                      style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                        gap: '12px',
                        fontSize: '13px',
                      }}
                    >
                      <div>
                        <span style={{ color: '#64748b', fontSize: '11px', display: 'block' }}>
                          Financing Cost Diff
                        </span>
                        <strong>
                          <Money paise={alt.financing_cost_diff_paise} />
                        </strong>
                      </div>

                      <div>
                        <span style={{ color: '#64748b', fontSize: '11px', display: 'block' }}>
                          Min Cash Improvement
                        </span>
                        <strong>
                          <Money paise={alt.min_cash_diff_paise} />
                        </strong>
                      </div>

                      <div>
                        <span style={{ color: '#64748b', fontSize: '11px', display: 'block' }}>
                          User Actions Count
                        </span>
                        <strong>{alt.user_changes_count} change(s)</strong>
                      </div>
                    </div>

                    {alt.tradeoffs && alt.tradeoffs.length > 0 && (
                      <div style={{ fontSize: '12px', color: '#475569' }}>
                        <strong>Tradeoffs:</strong> {alt.tradeoffs.join('; ')}
                      </div>
                    )}

                    {alt.approval_dependencies && alt.approval_dependencies.length > 0 && (
                      <div style={{ fontSize: '12px', color: '#b45309' }}>
                        <strong>Approval Dependencies:</strong> {alt.approval_dependencies.join('; ')}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {!counterfactualResult && (
          <p style={{ fontSize: '13px', color: '#64748b', margin: 0, fontStyle: 'italic' }}>
            Click &ldquo;Run Counterfactual Search&rdquo; to explore bounded allowed savings and term options without modifying the stored scenario.
          </p>
        )}
      </Card>

      {/* 6. Reason Evidence */}
      <div>
        <h2 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--color-text, #0f172a)', marginBottom: '12px' }}>
          Engine Reason Evidence
        </h2>
        <ReasonList evidence={selectedOffer?.evidence ?? []} />
      </div>
    </div>
  )
}
