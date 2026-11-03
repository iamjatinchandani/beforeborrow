import { CauseItem } from '../types'
import { AlertCircle, Clock, Calendar } from 'lucide-react'

interface Props {
  causes: CauseItem[]
  reasonCodes: string[]
}

const REASON_LABELS: Record<string, string> = {
  reserve_breach: 'Cash falls below reserve floor threshold',
  negative_balance: 'Cash balance falls into negative deficit (insolvency risk)',
  high_financing_cost: 'Financing cost exceeds 20% of borrowed principal',
  tight_pressure_window: 'Tight cash headroom (< ₹5,000) for consecutive days',
}

export function SqueezeCauses({ causes, reasonCodes }: Props) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {reasonCodes.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 4 }}>
          {reasonCodes.map((code) => (
            <span
              key={code}
              style={{
                fontSize: 11,
                fontWeight: 600,
                padding: '4px 8px',
                borderRadius: 4,
                background: code === 'negative_balance' ? '#fee2e2' : '#fef3c7',
                color: code === 'negative_balance' ? '#991b1b' : '#92400e',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
              }}
            >
              <AlertCircle size={12} /> {REASON_LABELS[code] || code}
            </span>
          ))}
        </div>
      )}

      {causes.length === 0 ? (
        <div style={{ padding: '16px 12px', background: '#f0fdf4', borderRadius: 'var(--radius-sm)', color: '#166534', fontSize: 13 }}>
          ✓ No significant cashflow squeezes or reserve breaches detected over this evaluation horizon.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {causes.map((c, i) => (
            <div
              key={i}
              style={{
                padding: '12px 14px',
                background: '#ffffff',
                border: '1px solid var(--color-border)',
                borderLeft: '4px solid var(--color-caution)',
                borderRadius: 'var(--radius-sm)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                <h5 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: 'var(--color-text)' }}>
                  {c.title}
                </h5>
                <span
                  style={{
                    fontSize: 11,
                    color: '#64748b',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 3,
                  }}
                >
                  <Calendar size={12} /> {c.date}
                </span>
              </div>
              <p style={{ margin: '4px 0 6px', fontSize: 13, color: '#334155', lineHeight: 1.4 }}>
                {c.detail}
              </p>
              <div style={{ fontSize: 11, color: '#64748b', display: 'flex', alignItems: 'center', gap: 4 }}>
                <Clock size={11} /> Source: <strong>{c.source_event}</strong>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
