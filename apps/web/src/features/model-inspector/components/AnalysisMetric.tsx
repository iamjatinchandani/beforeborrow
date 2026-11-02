import { Money } from '@/components/ui/Money'
import { DateText } from '@/components/ui/DateText'
import { StatusBadge } from '@/components/ui/StatusBadge'

export interface AnalysisMetricProps {
  label: string
  value?: number | string | null
  type?: 'paise' | 'date' | 'text'
  shortfall?: boolean
  description?: string
  subtext?: string
  badge?: {
    status: 'ok' | 'caution' | 'shortfall' | 'pending' | 'unknown'
    label: string
  }
  className?: string
}

export function AnalysisMetric({
  label,
  value,
  type = 'paise',
  shortfall = false,
  description,
  subtext,
  badge,
  className = '',
}: AnalysisMetricProps) {
  const isAvailable = value !== null && value !== undefined && value !== ''

  const renderValue = () => {
    if (!isAvailable) {
      return (
        <span
          style={{
            color: 'var(--color-muted, #94a3b8)',
            fontStyle: 'italic',
            fontWeight: 400,
          }}
          aria-label={`${label}: Unavailable`}
        >
          Not available
        </span>
      )
    }

    if (type === 'paise') {
      const numericVal = typeof value === 'number' ? value : Number(value)
      if (!Number.isFinite(numericVal)) {
        return (
          <span style={{ color: 'var(--color-muted, #94a3b8)', fontStyle: 'italic' }}>
            Not available
          </span>
        )
      }
      return <Money paise={numericVal} shortfall={shortfall} />
    }

    if (type === 'date') {
      const dateStr = String(value)
      // Check if it's a valid date representation
      if (!/^\d{4}-\d{2}-\d{2}/.test(dateStr)) {
        return <span>{dateStr}</span>
      }
      return <DateText value={dateStr} />
    }

    return <span>{String(value)}</span>
  }

  return (
    <div
      className={className}
      style={{
        background: '#ffffff',
        border: '1px solid var(--color-border, #e2e8f0)',
        borderRadius: 'var(--radius, 12px)',
        padding: '16px',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        gap: '8px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
        <span
          style={{
            fontSize: '13px',
            fontWeight: 500,
            color: 'var(--color-muted, #64748b)',
            letterSpacing: '0.01em',
          }}
        >
          {label}
        </span>
        {badge && <StatusBadge status={badge.status} label={badge.label} />}
      </div>

      <div
        style={{
          fontSize: '22px',
          fontWeight: 700,
          color: 'var(--color-text, #0f172a)',
          lineHeight: 1.2,
        }}
      >
        {renderValue()}
      </div>

      {(subtext || description) && (
        <div style={{ fontSize: '12px', color: 'var(--color-muted, #64748b)', marginTop: '2px' }}>
          {subtext && <p style={{ margin: 0, fontWeight: 500 }}>{subtext}</p>}
          {description && <p style={{ margin: '2px 0 0 0', lineHeight: 1.4 }}>{description}</p>}
        </div>
      )}
    </div>
  )
}
