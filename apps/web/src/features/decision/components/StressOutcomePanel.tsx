import { Card } from '../../../components/ui/Card'
import { ShieldAlert, Info } from 'lucide-react'

interface Props {
  stressResults: Record<string, string>
}

export function StressOutcomePanel({ stressResults }: Props) {
  const entries = Object.entries(stressResults)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ fontSize: 13, color: '#475569', display: 'flex', alignItems: 'center', gap: 6 }}>
        <Info size={14} /> Stress tests simulate adverse external shocks to verify financial durability.
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 12 }}>
        {entries.map(([caseName, description]) => {
          const isDelay = caseName.includes('delay')
          const isSpike = caseName.includes('spike')

          return (
            <Card
              key={caseName}
              style={{
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-sm)',
                padding: '14px',
                background: '#fafafa',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                <ShieldAlert size={16} color="var(--color-caution)" />
                <strong style={{ fontSize: 13, textTransform: 'capitalize' }}>
                  {caseName.replace(/_/g, ' ')}
                </strong>
              </div>
              <p style={{ margin: 0, fontSize: 13, color: '#334155', lineHeight: 1.4 }}>
                {description}
              </p>
              <div style={{ marginTop: 8, fontSize: 11, color: '#64748b' }}>
                Impact: {isDelay ? 'Extends duration of cash trough' : isSpike ? 'Deploys additional cash reserve' : 'Reduces monthly recovery rate'}
              </div>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
