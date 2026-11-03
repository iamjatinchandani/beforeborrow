import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  CartesianGrid,
} from 'recharts'
import { ChartPoint } from '../types'

interface Props {
  points: ChartPoint[]
  reserveFloorPaise: number
}

const formatRupees = (paise: number) => {
  return `₹${(paise / 100).toLocaleString('en-IN')}`
}

export function CashflowChart({ points, reserveFloorPaise }: Props) {
  if (!points || points.length === 0) {
    return <div style={{ padding: 24, textAlign: 'center', color: '#64748b' }}>No timeline points available</div>
  }

  // Find min and max for chart scale
  const balances = points.map((p) => p.balance_paise)
  const minBal = Math.min(...balances, 0)
  const maxBal = Math.max(...balances, reserveFloorPaise * 1.5)

  return (
    <div
      role="region"
      aria-label="Cashflow balance timeline chart"
      style={{
        width: '100%',
        height: 280,
        background: '#ffffff',
        padding: '16px 8px 8px',
        borderRadius: 'var(--radius)',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, padding: '0 8px' }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text)' }}>
          Modeled Cash Balance vs. Safety Reserve
        </div>
        <div style={{ display: 'flex', gap: 16, fontSize: 12 }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 10, height: 10, background: 'var(--color-primary)', borderRadius: 2 }} />
            Balance
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 12, height: 2, background: 'var(--color-caution)', borderTop: '2px dashed var(--color-caution)' }} />
            Reserve Floor ({formatRupees(reserveFloorPaise)})
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 12, height: 2, background: 'var(--color-shortfall)' }} />
            Zero Cash
          </span>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={230}>
        <AreaChart data={points} margin={{ top: 10, right: 20, left: 20, bottom: 0 }}>
          <defs>
            <linearGradient id="balanceGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="var(--color-primary)" stopOpacity={0.35} />
              <stop offset="95%" stopColor="var(--color-primary)" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--color-border)" />
          <XAxis
            dataKey="date"
            tickFormatter={(str) => {
              const d = new Date(str)
              return `${d.getDate()} ${d.toLocaleString('en-US', { month: 'short' })}`
            }}
            tick={{ fontSize: 11, fill: '#64748b' }}
            stroke="var(--color-border)"
          />
          <YAxis
            domain={[Math.floor(minBal * 1.1), Math.ceil(maxBal * 1.1)]}
            tickFormatter={formatRupees}
            tick={{ fontSize: 11, fill: '#64748b' }}
            stroke="var(--color-border)"
            width={75}
          />
          <Tooltip
            formatter={(val: number) => [formatRupees(val), 'Modeled Cash Balance']}
            labelFormatter={(label) => `Date: ${label}`}
            contentStyle={{
              background: '#ffffff',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-sm)',
              fontSize: 12,
              boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
            }}
          />
          <ReferenceLine
            y={reserveFloorPaise}
            stroke="var(--color-caution)"
            strokeDasharray="4 4"
            label={{ value: 'Reserve Floor', position: 'top', fill: '#d97706', fontSize: 10 }}
          />
          <ReferenceLine
            y={0}
            stroke="var(--color-shortfall)"
            strokeWidth={1.5}
            label={{ value: 'Insolvency (₹0)', position: 'insideBottomLeft', fill: '#dc2626', fontSize: 10 }}
          />
          <Area
            type="monotone"
            dataKey="balance_paise"
            stroke="var(--color-primary)"
            strokeWidth={2}
            fillOpacity={1}
            fill="url(#balanceGradient)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
