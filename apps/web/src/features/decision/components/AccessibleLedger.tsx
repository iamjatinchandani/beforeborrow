import { Money } from '../../../components/ui/Money'
import { LedgerEvent } from '../types'

interface Props {
  events: LedgerEvent[]
  reserveFloorPaise: number
}

export function AccessibleLedger({ events, reserveFloorPaise }: Props) {
  if (!events || events.length === 0) {
    return <div style={{ padding: 16, color: '#64748b' }}>No transaction events recorded.</div>
  }

  return (
    <div style={{ overflowX: 'auto', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)' }}>
      <table
        role="table"
        aria-label="Chronological cash ledger"
        style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, textAlign: 'left' }}
      >
        <thead>
          <tr style={{ background: 'var(--color-bg-muted)', borderBottom: '1px solid var(--color-border)' }}>
            <th style={{ padding: '10px 12px', fontWeight: 600 }}>Date</th>
            <th style={{ padding: '10px 12px', fontWeight: 600 }}>Event Description</th>
            <th style={{ padding: '10px 12px', fontWeight: 600, textAlign: 'right' }}>Inflow</th>
            <th style={{ padding: '10px 12px', fontWeight: 600, textAlign: 'right' }}>Outflow</th>
            <th style={{ padding: '10px 12px', fontWeight: 600, textAlign: 'right' }}>Balance</th>
            <th style={{ padding: '10px 12px', fontWeight: 600 }}>Source Reference</th>
          </tr>
        </thead>
        <tbody>
          {events.map((ev, i) => {
            const isBreach = ev.balance_paise < reserveFloorPaise && ev.balance_paise >= 0
            const isNegative = ev.balance_paise < 0

            return (
              <tr
                key={`${ev.date}-${i}`}
                style={{
                  borderBottom: '1px solid var(--color-border)',
                  background: isNegative ? '#fef2f2' : isBreach ? '#fffbeb' : i % 2 === 0 ? '#ffffff' : '#fafafa',
                }}
              >
                <td style={{ padding: '8px 12px', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                  {ev.date}
                </td>
                <td style={{ padding: '8px 12px' }}>
                  {ev.description}
                  {isNegative && (
                    <span style={{ marginLeft: 6, fontSize: 10, color: 'var(--color-shortfall)', fontWeight: 700 }}>
                      [NEGATIVE CASH]
                    </span>
                  )}
                  {isBreach && (
                    <span style={{ marginLeft: 6, fontSize: 10, color: 'var(--color-caution)', fontWeight: 700 }}>
                      [BELOW RESERVE]
                    </span>
                  )}
                </td>
                <td style={{ padding: '8px 12px', textAlign: 'right', color: ev.inflow_paise > 0 ? 'var(--color-primary)' : '#64748b' }}>
                  {ev.inflow_paise > 0 ? (
                    <>+<Money paise={ev.inflow_paise} /></>
                  ) : (
                    '—'
                  )}
                </td>
                <td style={{ padding: '8px 12px', textAlign: 'right', color: ev.outflow_paise > 0 ? 'var(--color-shortfall)' : '#64748b' }}>
                  {ev.outflow_paise > 0 ? (
                    <>-<Money paise={ev.outflow_paise} /></>
                  ) : (
                    '—'
                  )}
                </td>
                <td style={{ padding: '8px 12px', textAlign: 'right', fontWeight: 600 }}>
                  <Money paise={ev.balance_paise} shortfall={isNegative} />
                </td>
                <td style={{ padding: '8px 12px', fontSize: 12, color: '#64748b' }}>
                  {ev.source}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
