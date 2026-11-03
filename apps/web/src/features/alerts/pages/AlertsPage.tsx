import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAlerts, useDismissAlert } from '../hooks'
import { Card } from '../../../components/ui/Card'
import { Button } from '../../../components/ui/Button'
import {
  Bell,
  Clock,
  AlertTriangle,
  Calendar,
  CheckCircle2,
  Check,
  ArrowRight,
} from 'lucide-react'

export default function AlertsPage() {
  const { data: alerts = [], isLoading } = useAlerts()
  const dismissMutation = useDismissAlert()
  const [filter, setFilter] = useState<'all' | 'active' | 'dismissed'>('active')

  const filteredAlerts = alerts.filter((a) => {
    if (filter === 'active') return a.dismissed_at === null
    if (filter === 'dismissed') return a.dismissed_at !== null
    return true
  })

  const getAlertIcon = (type: string) => {
    if (type.includes('due')) return <Calendar size={18} color="var(--color-caution)" />
    if (type.includes('pressure')) return <Clock size={18} color="var(--color-shortfall)" />
    if (type.includes('stale')) return <AlertTriangle size={18} color="#d97706" />
    return <Bell size={18} color="var(--color-primary)" />
  }

  const getAlertAction = (a: any) => {
    if (a.alert_type.includes('due') || a.alert_type.includes('incomplete')) {
      return (
        <Link to="/obligations" style={{ textDecoration: 'none' }}>
          <Button variant="secondary" size="sm" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            View Obligations <ArrowRight size={12} />
          </Button>
        </Link>
      )
    }
    if (a.alert_type.includes('stale')) {
      return (
        <Link to="/profile" style={{ textDecoration: 'none' }}>
          <Button variant="secondary" size="sm" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            Update Profile <ArrowRight size={12} />
          </Button>
        </Link>
      )
    }
    if (a.alert_type.includes('pressure')) {
      return (
        <Link to="/decision/new" style={{ textDecoration: 'none' }}>
          <Button variant="secondary" size="sm" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            Review Decision <ArrowRight size={12} />
          </Button>
        </Link>
      )
    }
    return null
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
      {/* Page Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ margin: '0 0 4px', fontSize: 20, fontWeight: 700 }}>
            In-App Alerts & Due Reminders
          </h2>
          <p style={{ margin: 0, fontSize: 13, color: '#64748b' }}>
            Automated alerts derived directly from scheduled obligations, timing pressure, and profile staleness.
          </p>
        </div>

        {/* Filter Tabs */}
        <div
          style={{
            display: 'flex',
            background: 'var(--color-bg-muted)',
            padding: 4,
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--color-border)',
            gap: 4,
          }}
        >
          {(['active', 'all', 'dismissed'] as const).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setFilter(t)}
              style={{
                border: 'none',
                background: filter === t ? '#ffffff' : 'transparent',
                color: filter === t ? 'var(--color-text)' : '#64748b',
                padding: '6px 12px',
                borderRadius: 4,
                fontSize: 12,
                fontWeight: filter === t ? 600 : 400,
                cursor: 'pointer',
                boxShadow: filter === t ? '0 1px 2px rgb(0 0 0 / 0.05)' : 'none',
              }}
            >
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div style={{ padding: 32, textAlign: 'center', color: '#64748b' }}>Loading alerts...</div>
      ) : filteredAlerts.length === 0 ? (
        <Card style={{ padding: 48, textAlign: 'center', background: '#ffffff', borderRadius: 'var(--radius)' }}>
          <CheckCircle2 size={32} color="var(--color-primary)" style={{ marginBottom: 8 }} />
          <h4 style={{ margin: '0 0 4px', fontSize: 16 }}>No {filter} alerts</h4>
          <p style={{ margin: 0, fontSize: 13, color: '#64748b' }}>
            {filter === 'active'
              ? 'You have no pending due reminders or pressure date alerts.'
              : 'No alerts match this filter.'}
          </p>
        </Card>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {filteredAlerts.map((a) => {
            const isDismissed = Boolean(a.dismissed_at)

            return (
              <Card
                key={a.id}
                style={{
                  padding: 16,
                  background: isDismissed ? '#fafafa' : '#ffffff',
                  border: '1px solid var(--color-border)',
                  borderRadius: 'var(--radius-sm)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: 16,
                  opacity: isDismissed ? 0.7 : 1,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
                  <div
                    style={{
                      width: 36,
                      height: 36,
                      borderRadius: '50%',
                      background: 'var(--color-bg-muted)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                    }}
                  >
                    {getAlertIcon(a.alert_type)}
                  </div>

                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
                      <span
                        style={{
                          fontSize: 11,
                          fontWeight: 700,
                          textTransform: 'uppercase',
                          color: '#64748b',
                        }}
                      >
                        {a.alert_type.replace(/_/g, ' ')}
                      </span>
                      {a.due_date && (
                        <span style={{ fontSize: 11, color: '#94a3b8' }}>
                          Target: {a.due_date}
                        </span>
                      )}
                      {isDismissed && (
                        <span style={{ fontSize: 10, background: '#e2e8f0', padding: '1px 5px', borderRadius: 3 }}>
                          Dismissed
                        </span>
                      )}
                    </div>
                    <p style={{ margin: 0, fontSize: 13, color: '#1e293b', lineHeight: 1.4 }}>
                      {a.message}
                    </p>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                  {getAlertAction(a)}

                  {!isDismissed && (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => dismissMutation.mutate(a.id)}
                      disabled={dismissMutation.isPending}
                      title="Dismiss alert"
                      style={{ color: '#64748b' }}
                    >
                      <Check size={14} /> Dismiss
                    </Button>
                  )}
                </div>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
