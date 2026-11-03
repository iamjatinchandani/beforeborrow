import { useParams, Link } from 'react-router-dom'
import { useReceipt } from '../hooks'
import { Card } from '../../../components/ui/Card'
import { Button } from '../../../components/ui/Button'
import { Money } from '../../../components/ui/Money'
import {
  Printer,
  ShieldCheck,
  AlertTriangle,
  ArrowLeft,
  Bell,
  Lock,
} from 'lucide-react'

export default function ReportsPage() {
  const { id } = useParams<{ id: string }>()
  const { data: receiptData, isLoading, error } = useReceipt(id)

  const receipt: any = receiptData

  const handlePrint = () => {
    window.print()
  }

  if (isLoading) {
    return (
      <div style={{ padding: 48, textAlign: 'center', color: '#64748b' }}>
        Retrieving verified decision receipt...
      </div>
    )
  }

  if (error || !receipt) {
    return (
      <div style={{ padding: 48, textAlign: 'center' }}>
        <h3 style={{ color: 'var(--color-shortfall)' }}>Receipt Not Found</h3>
        <p style={{ color: '#64748b' }}>The requested decision receipt does not exist or access is unauthorized.</p>
        <Link to="/dashboard">
          <Button variant="primary">Return to Dashboard</Button>
        </Link>
      </div>
    )
  }

  const { context = {}, consequences = {}, uncertainty = {}, reflection_answers = {} } = receipt

  return (
    <>
      {/* Print Stylesheet */}
      <style>{`
        @media print {
          body {
            background: #ffffff !important;
            color: #000000 !important;
          }
          nav, header, button, .no-print {
            display: none !important;
          }
          main {
            padding: 0 !important;
            margin: 0 !important;
            max-width: 100% !important;
          }
          .receipt-paper {
            border: 1px solid #000000 !important;
            box-shadow: none !important;
            padding: 24px !important;
          }
        }
      `}</style>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)', paddingBottom: 'var(--space-6)' }}>
        {/* Top Action Bar (hidden on print) */}
        <div
          className="no-print"
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            background: 'var(--color-bg)',
            padding: '12px 16px',
            borderRadius: 'var(--radius)',
            border: '1px solid var(--color-border)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Link to="/dashboard" style={{ textDecoration: 'none' }}>
              <Button variant="secondary" size="sm">
                <ArrowLeft size={14} /> Dashboard
              </Button>
            </Link>
            <span style={{ fontSize: 13, color: '#64748b' }}>/</span>
            <span style={{ fontSize: 13, fontWeight: 600 }}>Decision Receipt</span>
          </div>

          <div style={{ display: 'flex', gap: 8 }}>
            <Link to="/alerts" style={{ textDecoration: 'none' }}>
              <Button variant="secondary" size="sm" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <Bell size={14} /> View Alerts
              </Button>
            </Link>
            <Button
              variant="primary"
              size="sm"
              onClick={handlePrint}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
            >
              <Printer size={14} /> Print / Save as PDF
            </Button>
          </div>
        </div>

        {/* Stale Status Banner */}
        {receipt.stale && (
          <div
            role="alert"
            style={{
              padding: '12px 16px',
              background: '#fffbeb',
              border: '1px solid #fef3c7',
              borderLeft: '4px solid var(--color-caution)',
              borderRadius: 'var(--radius-sm)',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              fontSize: 13,
              color: '#92400e',
            }}
          >
            <AlertTriangle size={18} />
            <span>
              <strong>Note:</strong> Your financial profile has updated since this receipt was generated.
              This receipt remains an immutable snapshot of conditions on the date of rehearsal.
            </span>
          </div>
        )}

        {/* Printable Decision Receipt Document */}
        <Card
          className="receipt-paper"
          style={{
            background: '#ffffff',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius)',
            padding: '32px',
            boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.05)',
          }}
        >
          {/* Header & Seal */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'flex-start',
              borderBottom: '2px solid var(--color-primary)',
              paddingBottom: 20,
              marginBottom: 24,
            }}
          >
            <div>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  letterSpacing: '0.05em',
                  textTransform: 'uppercase',
                  color: 'var(--color-primary)',
                }}
              >
                Official Rehearsal Record
              </span>
              <h1 style={{ margin: '4px 0 2px', fontSize: 24, fontWeight: 700 }}>
                BeforeBorrow Decision Receipt
              </h1>
              <p style={{ margin: 0, fontSize: 13, color: '#64748b' }}>
                Consequence & Cash-flow Snapshot on Actual Calendar Dates
              </p>
            </div>

            <div style={{ textAlign: 'right' }}>
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  background: '#f0fdfa',
                  color: 'var(--color-primary)',
                  padding: '4px 8px',
                  borderRadius: 4,
                  fontSize: 12,
                  fontWeight: 600,
                }}
              >
                <ShieldCheck size={14} /> Immutable Snapshot
              </div>
              <div style={{ fontSize: 11, color: '#64748b', marginTop: 4 }}>
                Receipt ID: {String(receipt.id).slice(0, 12)}...
              </div>
              <div style={{ fontSize: 11, color: '#64748b' }}>
                Timestamp: {new Date(receipt.created_at).toLocaleString('en-IN')}
              </div>
            </div>
          </div>

          {/* Section 1: Context */}
          <div style={{ marginBottom: 24 }}>
            <h3 style={{ fontSize: 14, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#475569', marginBottom: 12 }}>
              1. Scenario & Funding Context
            </h3>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: 16,
                background: 'var(--color-bg-muted)',
                padding: 16,
                borderRadius: 'var(--radius-sm)',
                fontSize: 13,
              }}
            >
              <div>
                <span style={{ color: '#64748b', fontSize: 11, display: 'block' }}>Emergency Expense</span>
                <strong><Money paise={context.emergency_amount_paise || 0} /></strong>
              </div>
              <div>
                <span style={{ color: '#64748b', fontSize: 11, display: 'block' }}>Required Settlement Date</span>
                <strong>{context.expense_date || 'N/A'}</strong>
              </div>
              <div>
                <span style={{ color: '#64748b', fontSize: 11, display: 'block' }}>Allowed Savings Contribution</span>
                <strong><Money paise={context.allowed_savings_paise || 0} /></strong>
              </div>
              <div>
                <span style={{ color: '#64748b', fontSize: 11, display: 'block' }}>Selected Funding Option</span>
                <strong style={{ color: 'var(--color-primary)' }}>{receipt.chosen_option}</strong>
              </div>
            </div>
          </div>

          {/* Section 2: Consequence Summary */}
          <div style={{ marginBottom: 24 }}>
            <h3 style={{ fontSize: 14, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#475569', marginBottom: 12 }}>
              2. Projected Financial Consequences
            </h3>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, textAlign: 'left' }}>
              <tbody>
                <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td style={{ padding: '8px 0', color: '#64748b' }}>Total Credit Cost (Fees + Interest):</td>
                  <td style={{ padding: '8px 0', textAlign: 'right', fontWeight: 600, color: 'var(--color-shortfall)' }}>
                    <Money paise={consequences.total_credit_cost_paise || 0} />
                  </td>
                </tr>
                <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td style={{ padding: '8px 0', color: '#64748b' }}>Total Scheduled Repayment:</td>
                  <td style={{ padding: '8px 0', textAlign: 'right', fontWeight: 600 }}>
                    <Money paise={consequences.total_repayment_paise || 0} />
                  </td>
                </tr>
                <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td style={{ padding: '8px 0', color: '#64748b' }}>Monthly Installment Amount:</td>
                  <td style={{ padding: '8px 0', textAlign: 'right' }}>
                    <Money paise={consequences.monthly_installment_paise || 0} /> × {consequences.repayment_term_months || 0} months
                  </td>
                </tr>
                <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td style={{ padding: '8px 0', color: '#64748b' }}>Lowest Modeled Cash Trough:</td>
                  <td style={{ padding: '8px 0', textAlign: 'right', fontWeight: 600 }}>
                    <Money paise={consequences.cash_trough_paise || 0} shortfall={consequences.cash_trough_paise < 0} /> on {consequences.cash_trough_date || 'N/A'}
                  </td>
                </tr>
                <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td style={{ padding: '8px 0', color: '#64748b' }}>First Reserve Floor Breach Date:</td>
                  <td style={{ padding: '8px 0', textAlign: 'right', fontWeight: 600, color: consequences.first_reserve_breach ? 'var(--color-caution)' : 'var(--color-primary)' }}>
                    {consequences.first_reserve_breach || 'None (Buffer preserved)'}
                  </td>
                </tr>
                <tr>
                  <td style={{ padding: '8px 0', color: '#64748b' }}>First Negative Cash Date:</td>
                  <td style={{ padding: '8px 0', textAlign: 'right', fontWeight: 600, color: consequences.first_negative_date ? 'var(--color-shortfall)' : 'var(--color-primary)' }}>
                    {consequences.first_negative_date || 'None (Insolvency avoided)'}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* Section 3: Uncertainty & Stress Cases */}
          <div style={{ marginBottom: 24 }}>
            <h3 style={{ fontSize: 14, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#475569', marginBottom: 12 }}>
              3. Uncertainty & Assumptions
            </h3>
            <div style={{ fontSize: 13, color: '#334155', lineHeight: 1.5 }}>
              <ul style={{ margin: '0 0 12px', paddingLeft: 20 }}>
                {(uncertainty.assumptions || []).map((asm: string, i: number) => (
                  <li key={i}>{asm}</li>
                ))}
                <li>{uncertainty.same_day_settlement_rule}</li>
              </ul>

              {uncertainty.stress_outcomes && Object.keys(uncertainty.stress_outcomes).length > 0 && (
                <div style={{ background: '#f8fafc', padding: 12, borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)' }}>
                  <strong style={{ display: 'block', marginBottom: 6, fontSize: 12 }}>Stress Outcomes:</strong>
                  {Object.entries(uncertainty.stress_outcomes).map(([k, v]: [string, any]) => (
                    <div key={k} style={{ fontSize: 12, marginBottom: 4 }}>
                      • <strong>{k.replace(/_/g, ' ')}:</strong> {v}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Section 4: User Reflection */}
          {reflection_answers && (
            <div style={{ marginBottom: 24, borderTop: '1px dashed var(--color-border)', paddingTop: 16 }}>
              <h3 style={{ fontSize: 14, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#475569', marginBottom: 10 }}>
                4. User Reflection
              </h3>
              <div style={{ fontSize: 13, color: '#334155', display: 'flex', flexDirection: 'column', gap: 6 }}>
                <div>
                  <span style={{ color: '#64748b' }}>Tightest repayment date identified: </span>
                  <strong>{reflection_answers.tight_repayment_date || 'None specified'}</strong>
                </div>
                <div>
                  <span style={{ color: '#64748b' }}>Key income assumption: </span>
                  <strong>{reflection_answers.key_income_assumption || 'Standard salary credit'}</strong>
                </div>
              </div>
            </div>
          )}

          {/* Footer & Cryptographic Verification */}
          <div
            style={{
              borderTop: '1px solid var(--color-border)',
              paddingTop: 16,
              marginTop: 24,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              fontSize: 11,
              color: '#94a3b8',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Lock size={12} />
              <span>
                Snapshot Hash: <code style={{ fontFamily: 'var(--font-mono)' }}>{String(context.snapshot_hash || '').slice(0, 24)}...</code>
              </span>
            </div>
            <div>
              Engine: {context.model_version || 'rules-v1'} • Source Version: {context.source_data_version || 1}
            </div>
          </div>
        </Card>
      </div>
    </>
  )
}
