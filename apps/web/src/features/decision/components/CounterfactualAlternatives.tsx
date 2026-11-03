import { useState } from 'react'
import { Card } from '../../../components/ui/Card'
import { Button } from '../../../components/ui/Button'
import { useCounterfactuals } from '../hooks'
import { CounterfactualAlternative } from '../types'
import { Lightbulb, RefreshCw, AlertTriangle, CheckCircle } from 'lucide-react'

interface Props {
  scenarioId: string
  analysisId: string
}

export function CounterfactualAlternatives({ scenarioId, analysisId }: Props) {
  const counterfactualMutation = useCounterfactuals(scenarioId)
  const [alternatives, setAlternatives] = useState<CounterfactualAlternative[] | null>(null)
  const [noFeasiblePlan, setNoFeasiblePlan] = useState(false)
  const [constraints, setConstraints] = useState<string[]>([])

  const handleSearchAlternatives = () => {
    counterfactualMutation.mutate(
      {
        analysis_id: analysisId,
        allowed_changes: ['allowed_savings_paise', 'term_months', 'expense_date_offset_days'],
        bounds: { max_extra_savings_paise: 1_000_000, max_term_months: 12 },
      },
      {
        onSuccess: (data) => {
          setAlternatives(data.alternatives)
          setNoFeasiblePlan(data.no_feasible_plan)
          setConstraints(data.binding_constraints)
        },
      }
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h4 style={{ margin: '0 0 4px', fontSize: 15, fontWeight: 600 }}>
            Feasible Alternatives & Counterfactuals
          </h4>
          <p style={{ margin: 0, fontSize: 13, color: '#64748b' }}>
            Simulate adjusted timelines, tenures, or self-contributions to avoid reserve breaches.
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={handleSearchAlternatives}
          disabled={counterfactualMutation.isPending}
        >
          {counterfactualMutation.isPending ? (
            <>
              <RefreshCw size={14} className="spin" /> Searching...
            </>
          ) : (
            <>
              <Lightbulb size={14} /> Search Alternatives
            </>
          )}
        </Button>
      </div>

      {noFeasiblePlan && (
        <div
          role="alert"
          style={{
            padding: 16,
            background: '#fff1f2',
            border: '1px solid #fecdd3',
            borderRadius: 'var(--radius)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#be123c', fontWeight: 600, fontSize: 14, marginBottom: 6 }}>
            <AlertTriangle size={18} /> No Feasible Plan Found
          </div>
          <p style={{ margin: 0, fontSize: 13, color: '#9f1239' }}>
            Under your current baseline commitments, no combination of available borrowing options and savings contributions eliminates the reserve floor breach.
          </p>
          {constraints.length > 0 && (
            <div style={{ marginTop: 8, fontSize: 12, color: '#881337' }}>
              <strong>Binding constraints:</strong> {constraints.join(' • ')}
            </div>
          )}
        </div>
      )}

      {alternatives && alternatives.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 12 }}>
          {alternatives.map((alt) => (
            <Card
              key={alt.id}
              style={{
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius)',
                padding: 16,
                background: '#ffffff',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                  <CheckCircle size={16} color="var(--color-primary)" />
                  <strong style={{ fontSize: 14 }}>{alt.title}</strong>
                </div>
                <p style={{ margin: '0 0 10px', fontSize: 13, color: '#334155', lineHeight: 1.4 }}>
                  {alt.description}
                </p>

                <div
                  style={{
                    background: '#f0fdfa',
                    padding: '8px 10px',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: 12,
                    color: '#0f766e',
                    marginBottom: 8,
                  }}
                >
                  <strong>Consequence:</strong> {alt.consequence_summary}
                </div>

                <div style={{ fontSize: 11, color: '#64748b' }}>
                  <strong>Trade-off / Risk:</strong> {alt.risk_assessment}
                </div>
              </div>

              <div
                style={{
                  marginTop: 12,
                  paddingTop: 8,
                  borderTop: '1px dashed var(--color-border)',
                  fontSize: 11,
                  color: '#94a3b8',
                }}
              >
                * Modeled possibility based on rules engine. Not a guaranteed provider offer.
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
