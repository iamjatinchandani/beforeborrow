import { Link, useNavigate } from 'react-router-dom'
import { useScenarios, useCreateScenario } from '@/features/decision/hooks'
import { useAlerts } from '@/features/alerts/hooks'
import { Card } from '../../../components/ui/Card'
import { Button } from '../../../components/ui/Button'
import { Money } from '../../../components/ui/Money'
import {
  Compass,
  Sparkles,
  ArrowRight,
  Clock,
  Layers,
} from 'lucide-react'

export default function DashboardPage() {
  const navigate = useNavigate()
  const { data: scenarios = [], isLoading: isScenariosLoading } = useScenarios()
  const { data: alerts = [] } = useAlerts()
  const createScenarioMutation = useCreateScenario()

  const activeAlerts = alerts.filter((a) => a.dismissed_at === null).slice(0, 3)

  const handleLaunchTimingDemo = async () => {
    try {
      const demoScenario = await createScenarioMutation.mutateAsync({
        category: 'Medical emergency',
        expense_amount_paise: 2_000_000,
        expense_date: '2026-11-08',
        need_cash: true,
        allowed_savings_paise: 0,
        horizon_days: 90,
        offers: [
          {
            offer_name: 'Demo 3-Mo BNPL',
            provider: 'PayLater Fin',
            offer_type: 'bnpl',
            principal_paise: 2_000_000,
            fees_paise: 40_000,
            rate_annual_pct: '0.00',
            term_months: 3,
            eligibility_evidence: 'Pre-approved in-app',
            is_demo: true,
          },
          {
            offer_name: 'Demo Personal Loan',
            provider: 'Axis Express',
            offer_type: 'personal_loan',
            principal_paise: 2_000_000,
            fees_paise: 100_000,
            rate_annual_pct: '14.00',
            term_months: 6,
            eligibility_evidence: 'Salary account offer',
            is_demo: true,
          },
        ],
      })
      if (demoScenario?.id) {
        navigate(`/decision/${demoScenario.id}`)
      }
    } catch (err) {
      console.error('Failed to launch demo:', err)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
      {/* Hero Header */}
      <Card
        style={{
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius)',
          padding: '28px 32px',
          background: 'linear-gradient(135deg, #ffffff 0%, #f0fdfa 100%)',
        }}
      >
        <div style={{ maxWidth: 700 }}>
          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              color: 'var(--color-primary)',
              background: '#ccfbf1',
              padding: '2px 8px',
              borderRadius: 4,
            }}
          >
            IDEATHON 2026 • Emergency Decision Studio
          </span>
          <h1 style={{ margin: '8px 0 6px', fontSize: 24, fontWeight: 700, color: 'var(--color-text)' }}>
            BeforeBorrow Financial Studio
          </h1>
          <p style={{ margin: '0 0 20px', fontSize: 15, color: '#334155', lineHeight: 1.5 }}>
            "A credit limit tells you what is available. We show what each choice does to your cash,
            commitments and goals — on actual dates."
          </p>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
            <Link to="/decision/new" style={{ textDecoration: 'none' }}>
              <Button variant="primary" style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                <Compass size={16} /> New Emergency Decision Studio
              </Button>
            </Link>

            <Button
              variant="secondary"
              onClick={handleLaunchTimingDemo}
              disabled={createScenarioMutation.isPending}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
            >
              <Sparkles size={16} color="var(--color-primary)" />
              {createScenarioMutation.isPending ? 'Launching Demo...' : 'Load Timing Trap Demo Scenario'}
            </Button>
          </div>
        </div>
      </Card>

      {/* Grid: Active Alerts & Recent Scenarios */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 'var(--space-3)' }}>
        {/* Active Alerts Preview */}
        <Card
          style={{
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius)',
            padding: '20px',
            background: '#ffffff',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
              <Clock size={16} color="var(--color-caution)" /> Active Financial Alerts
            </h3>
            <Link to="/alerts" style={{ fontSize: 12, color: 'var(--color-primary)', textDecoration: 'none', fontWeight: 600 }}>
              View all ({alerts.length}) →
            </Link>
          </div>

          {activeAlerts.length === 0 ? (
            <div style={{ padding: '24px 0', textAlign: 'center', color: '#64748b', fontSize: 13 }}>
              No active alerts. All upcoming dues and reserves are within safety thresholds.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {activeAlerts.map((a) => (
                <div
                  key={a.id}
                  style={{
                    padding: '10px 12px',
                    borderRadius: 'var(--radius-sm)',
                    background: 'var(--color-bg-muted)',
                    border: '1px solid var(--color-border)',
                    fontSize: 13,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                    <strong style={{ fontSize: 11, textTransform: 'uppercase', color: '#64748b' }}>
                      {a.alert_type.replace(/_/g, ' ')}
                    </strong>
                    {a.due_date && <span style={{ fontSize: 11, color: '#94a3b8' }}>{a.due_date}</span>}
                  </div>
                  <p style={{ margin: 0, color: '#1e293b', lineHeight: 1.3 }}>{a.message}</p>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Recent Scenarios */}
        <Card
          style={{
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius)',
            padding: '20px',
            background: '#ffffff',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
              <Layers size={16} color="var(--color-primary)" /> Emergency Scenarios
            </h3>
            <Link to="/decision/new" style={{ fontSize: 12, color: 'var(--color-primary)', textDecoration: 'none', fontWeight: 600 }}>
              + Create new
            </Link>
          </div>

          {isScenariosLoading ? (
            <div style={{ padding: 24, textAlign: 'center', color: '#64748b' }}>Loading scenarios...</div>
          ) : scenarios.length === 0 ? (
            <div style={{ padding: '24px 0', textAlign: 'center', color: '#64748b', fontSize: 13 }}>
              No emergency scenarios created yet. Click "New Emergency Decision Studio" above to rehearse your first expense.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {scenarios.slice(0, 4).map((scen) => (
                <div
                  key={scen.id}
                  style={{
                    padding: '10px 12px',
                    borderRadius: 'var(--radius-sm)',
                    background: '#ffffff',
                    border: '1px solid var(--color-border)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                >
                  <div>
                    <strong style={{ fontSize: 14, display: 'block' }}>
                      {scen.category || 'Urgent Expense'}
                    </strong>
                    <span style={{ fontSize: 12, color: '#64748b' }}>
                      <Money paise={scen.expense_amount_paise} /> • Due on {scen.expense_date}
                    </span>
                  </div>

                  <Link to={`/decision/${scen.id}`} style={{ textDecoration: 'none' }}>
                    <Button variant="secondary" size="sm" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                      Resume <ArrowRight size={12} />
                    </Button>
                  </Link>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
