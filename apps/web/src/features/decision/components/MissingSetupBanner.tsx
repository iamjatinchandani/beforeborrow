import { Link } from 'react-router-dom'
import { AlertTriangle, ArrowRight } from 'lucide-react'
import { SetupStatus } from '../types'

interface Props {
  status?: SetupStatus | null
}

export function MissingSetupBanner({ status }: Props) {
  if (!status || status.is_complete) return null

  return (
    <div
      role="alert"
      style={{
        background: '#fffbeb',
        border: '1px solid #fef3c7',
        borderLeft: '4px solid var(--color-caution)',
        borderRadius: 'var(--radius-sm)',
        padding: '12px 16px',
        marginBottom: 'var(--space-3)',
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        gap: 12,
      }}
    >
      <div style={{ display: 'flex', gap: 12 }}>
        <AlertTriangle size={20} color="var(--color-caution)" style={{ flexShrink: 0, marginTop: 2 }} />
        <div>
          <h4 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: '#92400e' }}>
            Incomplete Financial Setup
          </h4>
          <p style={{ margin: '4px 0 0', fontSize: 13, color: '#b45309' }}>
            Accurate consequence modeling requires your current cash balance and reserve floor.
            Missing:{' '}
            <strong>
              {status.missing_fields.map((f) => f.replace('_', ' ')).join(', ')}
            </strong>
          </p>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
        {!status.has_profile && (
          <Link
            to="/profile"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              fontSize: 12,
              fontWeight: 600,
              padding: '6px 10px',
              borderRadius: 'var(--radius-sm)',
              background: '#fef3c7',
              color: '#92400e',
              textDecoration: 'none',
            }}
          >
            Configure Profile <ArrowRight size={12} />
          </Link>
        )}
        <Link
          to="/obligations"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
            fontSize: 12,
            fontWeight: 600,
            padding: '6px 10px',
            borderRadius: 'var(--radius-sm)',
            background: '#ffffff',
            border: '1px solid #fde68a',
            color: '#92400e',
            textDecoration: 'none',
          }}
        >
          Check Obligations <ArrowRight size={12} />
        </Link>
      </div>
    </div>
  )
}
