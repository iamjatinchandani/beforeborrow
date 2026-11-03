import { useState } from 'react'
import { Card } from '../../../components/ui/Card'
import { Button } from '../../../components/ui/Button'
import { Money } from '../../../components/ui/Money'
import { AnalysisPayload, OfferAnalysisResult } from '../types'
import { CashflowChart } from './CashflowChart'
import { AccessibleLedger } from './AccessibleLedger'
import { SqueezeCauses } from './SqueezeCauses'
import { StressOutcomePanel } from './StressOutcomePanel'
import { CounterfactualAlternatives } from './CounterfactualAlternatives'
import { SaveReceiptModal } from './SaveReceiptModal'
import { ArrowUpDown, FileCheck } from 'lucide-react'

interface Props {
  scenarioId: string
  analysisId: string
  analysis: AnalysisPayload
  onRerun: () => void
}

type SortPriority = 'cost' | 'cash_now' | 'trough' | 'breach_date'

export function ComparisonDashboard({
  scenarioId,
  analysisId,
  analysis,
  onRerun,
}: Props) {
  const [priority, setPriority] = useState<SortPriority>('cost')
  const [selectedOfferIdx, setSelectedOfferIdx] = useState(0)
  const [activeTab, setActiveTab] = useState<'chart' | 'ledger' | 'causes' | 'stress'>('chart')
  const [isReceiptModalOpen, setIsReceiptModalOpen] = useState(false)

  const rawOffers = analysis.offers || []

  // Filter and sort offers
  const sortedOffers = [...rawOffers].sort((a, b) => {
    if (priority === 'cost') {
      return a.financing_cost_paise - b.financing_cost_paise
    }
    if (priority === 'cash_now') {
      return a.cash_required_now_paise - b.cash_required_now_paise
    }
    if (priority === 'trough') {
      return b.trough_paise - a.trough_paise // Higher trough is safer
    }
    if (priority === 'breach_date') {
      // Offers without breach come first
      if (!a.first_reserve_breach && b.first_reserve_breach) return -1
      if (a.first_reserve_breach && !b.first_reserve_breach) return 1
      return 0
    }
    return 0
  })

  const currentOffer: OfferAnalysisResult | undefined = sortedOffers[selectedOfferIdx]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
      {/* Top Controls: Priority Sorting & Actions */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 12,
          background: 'var(--color-bg)',
          padding: '12px 16px',
          borderRadius: 'var(--radius)',
          border: '1px solid var(--color-border)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: '#475569', display: 'flex', alignItems: 'center', gap: 4 }}>
            <ArrowUpDown size={14} /> Sort By Priority:
          </span>
          <select
            value={priority}
            onChange={(e) => setPriority(e.target.value as SortPriority)}
            aria-label="Sort comparison priority"
            style={{
              padding: '6px 10px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--color-border)',
              fontSize: 13,
              background: '#ffffff',
            }}
          >
            <option value="cost">Lowest Total Credit Cost</option>
            <option value="cash_now">Lowest Immediate Cash Required</option>
            <option value="trough">Safest Cash Trough (Least Squeeze)</option>
            <option value="breach_date">Fewest Reserve Breaches</option>
          </select>
          <span style={{ fontSize: 11, color: '#64748b' }}>
            * Showing actual dates & consequences. Never ranking with arbitrary scores.
          </span>
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <Button variant="secondary" size="sm" onClick={onRerun}>
            Refresh Analysis
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => setIsReceiptModalOpen(true)}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
          >
            <FileCheck size={14} /> Save Decision Receipt
          </Button>
        </div>
      </div>

      {/* Side-by-Side Comparison Cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: `repeat(auto-fit, minmax(280px, 1fr))`,
          gap: 12,
        }}
      >
        {sortedOffers.map((off, idx) => {
          const isSelected = selectedOfferIdx === idx
          const isBreach = Boolean(off.first_reserve_breach)
          const isNegative = Boolean(off.first_negative)

          return (
            <div
              key={off.offer_id || idx}
              onClick={() => setSelectedOfferIdx(idx)}
              style={{
                cursor: 'pointer',
                borderRadius: 'var(--radius)',
                border: isSelected ? '2px solid var(--color-primary)' : '1px solid var(--color-border)',
                background: isSelected ? '#ffffff' : 'var(--color-bg-muted)',
                padding: 'var(--space-2)',
                boxShadow: isSelected ? '0 4px 12px -2px rgba(13, 148, 136, 0.15)' : 'none',
                transition: 'all 0.15s ease',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                <div>
                  <span
                    style={{
                      fontSize: 10,
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      padding: '2px 6px',
                      borderRadius: 4,
                      background: isSelected ? 'var(--color-primary)' : '#e2e8f0',
                      color: isSelected ? '#ffffff' : '#475569',
                    }}
                  >
                    Option {idx + 1}
                  </span>
                  <h4 style={{ margin: '4px 0 2px', fontSize: 16, fontWeight: 600 }}>
                    {off.offer_name}
                  </h4>
                  <span style={{ fontSize: 12, color: '#64748b' }}>{off.provider}</span>
                </div>

                {off.is_demo && (
                  <span style={{ fontSize: 10, background: '#fef3c7', color: '#92400e', padding: '2px 5px', borderRadius: 3 }}>
                    Demo offer
                  </span>
                )}
              </div>

              {/* Consequence Metrics Grid */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 13, marginTop: 10 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px dashed #e2e8f0', paddingBottom: 4 }}>
                  <span style={{ color: '#64748b' }}>Total Credit Cost:</span>
                  <strong style={{ color: 'var(--color-shortfall)' }}><Money paise={off.financing_cost_paise} /></strong>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px dashed #e2e8f0', paddingBottom: 4 }}>
                  <span style={{ color: '#64748b' }}>Total Repayment:</span>
                  <strong><Money paise={off.total_repayment_paise} /></strong>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px dashed #e2e8f0', paddingBottom: 4 }}>
                  <span style={{ color: '#64748b' }}>Monthly EMI:</span>
                  <span><Money paise={off.monthly_installment_paise} /> × {off.term_months} mo</span>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px dashed #e2e8f0', paddingBottom: 4 }}>
                  <span style={{ color: '#64748b' }}>Cash Required Now:</span>
                  <span><Money paise={off.cash_required_now_paise} /></span>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px dashed #e2e8f0', paddingBottom: 4 }}>
                  <span style={{ color: '#64748b' }}>Lowest Cash Trough:</span>
                  <strong style={{ color: off.trough_paise < 0 ? 'var(--color-shortfall)' : 'inherit' }}>
                    <Money paise={off.trough_paise} shortfall={off.trough_paise < 0} />
                  </strong>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', paddingTop: 2 }}>
                  <span style={{ color: '#64748b' }}>First Pressure Date:</span>
                  <span style={{ fontWeight: 600, color: isNegative ? 'var(--color-shortfall)' : isBreach ? 'var(--color-caution)' : 'var(--color-primary)' }}>
                    {isNegative ? `Negative on ${off.first_negative}` : isBreach ? `Breach on ${off.first_reserve_breach}` : 'No breach'}
                  </span>
                </div>
              </div>

              <div style={{ marginTop: 12, textAlign: 'center' }}>
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: isSelected ? 'var(--color-primary)' : '#64748b',
                  }}
                >
                  {isSelected ? '● Currently Inspecting' : 'Click to inspect timeline'}
                </span>
              </div>
            </div>
          )
        })}
      </div>

      {/* Detailed Offer Inspection Tabs */}
      {currentOffer && (
        <Card
          style={{
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius)',
            padding: 'var(--space-3)',
            background: '#ffffff',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              borderBottom: '1px solid var(--color-border)',
              paddingBottom: 12,
              marginBottom: 16,
            }}
          >
            <div>
              <h3 style={{ margin: '0 0 2px', fontSize: 18, fontWeight: 700 }}>
                Consequence Analysis: {currentOffer.offer_name}
              </h3>
              <p style={{ margin: 0, fontSize: 13, color: '#64748b' }}>
                {currentOffer.first_reserve_breach
                  ? `Lower total cost; reserve breach on ${currentOffer.first_reserve_breach}.`
                  : 'Maintains required cash reserve throughout comparison horizon.'}
              </p>
            </div>

            {/* Tab Buttons */}
            <div style={{ display: 'flex', gap: 6 }}>
              <button
                type="button"
                onClick={() => setActiveTab('chart')}
                style={{
                  padding: '6px 12px',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: 13,
                  fontWeight: 600,
                  border: 'none',
                  background: activeTab === 'chart' ? '#f0fdfa' : 'transparent',
                  color: activeTab === 'chart' ? 'var(--color-primary)' : '#64748b',
                  cursor: 'pointer',
                }}
              >
                Cash-Flow Chart
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('ledger')}
                style={{
                  padding: '6px 12px',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: 13,
                  fontWeight: 600,
                  border: 'none',
                  background: activeTab === 'ledger' ? '#f0fdfa' : 'transparent',
                  color: activeTab === 'ledger' ? 'var(--color-primary)' : '#64748b',
                  cursor: 'pointer',
                }}
              >
                Accessible Ledger
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('causes')}
                style={{
                  padding: '6px 12px',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: 13,
                  fontWeight: 600,
                  border: 'none',
                  background: activeTab === 'causes' ? '#f0fdfa' : 'transparent',
                  color: activeTab === 'causes' ? 'var(--color-primary)' : '#64748b',
                  cursor: 'pointer',
                }}
              >
                Cause List ({currentOffer.causes?.length || 0})
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('stress')}
                style={{
                  padding: '6px 12px',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: 13,
                  fontWeight: 600,
                  border: 'none',
                  background: activeTab === 'stress' ? '#f0fdfa' : 'transparent',
                  color: activeTab === 'stress' ? 'var(--color-primary)' : '#64748b',
                  cursor: 'pointer',
                }}
              >
                Stress Testing
              </button>
            </div>
          </div>

          {/* Active Tab Panel */}
          {activeTab === 'chart' && (
            <CashflowChart
              points={currentOffer.chart_points || []}
              reserveFloorPaise={analysis.reserve_floor_paise}
            />
          )}

          {activeTab === 'ledger' && (
            <AccessibleLedger
              events={currentOffer.ledger || []}
              reserveFloorPaise={analysis.reserve_floor_paise}
            />
          )}

          {activeTab === 'causes' && (
            <SqueezeCauses
              causes={currentOffer.causes || []}
              reasonCodes={currentOffer.reason_codes || []}
            />
          )}

          {activeTab === 'stress' && (
            <StressOutcomePanel stressResults={analysis.stress_results || {}} />
          )}
        </Card>
      )}

      {/* Module D5: Counterfactuals & Feasible Alternatives */}
      <Card
        style={{
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius)',
          padding: 'var(--space-3)',
          background: '#ffffff',
        }}
      >
        <CounterfactualAlternatives scenarioId={scenarioId} analysisId={analysisId} />
      </Card>

      {/* Receipt Modal */}
      {isReceiptModalOpen && (
        <SaveReceiptModal
          isOpen={isReceiptModalOpen}
          onClose={() => setIsReceiptModalOpen(false)}
          analysisId={analysisId}
          offers={sortedOffers}
        />
      )}
    </div>
  )
}
