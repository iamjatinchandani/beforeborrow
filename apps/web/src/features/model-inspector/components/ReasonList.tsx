import { ReasonEvidence } from '../types'
import { Money } from '@/components/ui/Money'
import { DateText } from '@/components/ui/DateText'

export interface ReasonListProps {
  evidence?: ReasonEvidence[]
  className?: string
}

export function ReasonList({ evidence = [], className = '' }: ReasonListProps) {
  if (!evidence || evidence.length === 0) {
    return (
      <div
        className={className}
        style={{
          padding: '16px',
          background: '#f8fafc',
          borderRadius: 'var(--radius, 12px)',
          border: '1px dashed var(--color-border, #e2e8f0)',
          color: 'var(--color-muted, #64748b)',
          fontSize: '14px',
          textAlign: 'center',
        }}
      >
        No reason evidence recorded for this calculation.
      </div>
    )
  }

  return (
    <div
      className={className}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
      }}
    >
      {evidence.map((item, idx) => (
        <div
          key={`${item.code}-${item.date ?? ''}-${idx}`}
          style={{
            background: '#ffffff',
            border: '1px solid var(--color-border, #e2e8f0)',
            borderRadius: 'var(--radius, 12px)',
            padding: '16px',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px',
          }}
        >
          {/* Header: Code and Date */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '8px',
            }}
          >
            <span
              style={{
                fontFamily: 'var(--font-mono, monospace)',
                fontWeight: 700,
                fontSize: '13px',
                background: '#f1f5f9',
                color: 'var(--color-text, #0f172a)',
                padding: '3px 8px',
                borderRadius: '6px',
                border: '1px solid #cbd5e1',
              }}
            >
              {item.code}
            </span>

            {item.date && (
              <span style={{ fontSize: '13px', color: 'var(--color-muted, #64748b)' }}>
                Date: <DateText value={item.date} />
              </span>
            )}
          </div>

          {/* Message Key */}
          {item.message_key && (
            <div style={{ fontSize: '14px', color: 'var(--color-text, #0f172a)' }}>
              <strong>Evidence Key:</strong>{' '}
              <span style={{ fontFamily: 'var(--font-mono, monospace)', fontSize: '13px' }}>
                {item.message_key}
              </span>
            </div>
          )}

          {/* Cash Ledger Changes */}
          {(item.before_paise !== undefined && item.before_paise !== null) ||
          (item.after_paise !== undefined && item.after_paise !== null) ||
          (item.threshold_paise !== undefined && item.threshold_paise !== null) ? (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
                gap: '12px',
                background: '#f8fafc',
                padding: '10px 12px',
                borderRadius: '8px',
                fontSize: '13px',
              }}
            >
              {item.before_paise !== undefined && item.before_paise !== null && (
                <div>
                  <span style={{ color: 'var(--color-muted, #64748b)', display: 'block', fontSize: '11px' }}>
                    Before Cash
                  </span>
                  <strong>
                    <Money paise={item.before_paise} />
                  </strong>
                </div>
              )}

              {item.after_paise !== undefined && item.after_paise !== null && (
                <div>
                  <span style={{ color: 'var(--color-muted, #64748b)', display: 'block', fontSize: '11px' }}>
                    After Cash
                  </span>
                  <strong>
                    <Money paise={item.after_paise} shortfall={item.after_paise < 0} />
                  </strong>
                </div>
              )}

              {item.threshold_paise !== undefined && item.threshold_paise !== null && (
                <div>
                  <span style={{ color: 'var(--color-muted, #64748b)', display: 'block', fontSize: '11px' }}>
                    Reserve Threshold
                  </span>
                  <strong>
                    <Money paise={item.threshold_paise} />
                  </strong>
                </div>
              )}
            </div>
          ) : null}

          {/* Assumptions */}
          {item.assumptions && item.assumptions.length > 0 && (
            <div style={{ fontSize: '12px', color: 'var(--color-muted, #64748b)' }}>
              <span style={{ fontWeight: 600 }}>Stated Assumptions:</span>
              <ul style={{ margin: '4px 0 0 0', paddingLeft: '20px', lineHeight: 1.4 }}>
                {item.assumptions.map((assump, aIdx) => (
                  <li key={aIdx}>{assump}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Event IDs */}
          {item.event_ids && item.event_ids.length > 0 && (
            <div style={{ fontSize: '12px', color: 'var(--color-muted, #64748b)' }}>
              <span style={{ fontWeight: 600 }}>Causing Events:</span>{' '}
              <span style={{ fontFamily: 'var(--font-mono, monospace)', fontSize: '11px' }}>
                {item.event_ids.join(', ')}
              </span>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
