import { useState, useEffect } from 'react'
import { Modal } from '../../../components/ui/Modal'
import { Button } from '../../../components/ui/Button'
import { Field } from '../../../components/ui/Field'
import { rupeesToPaise } from '../../../components/ui/Money'
import { OfferItem } from '../types'
import { Sparkles } from 'lucide-react'

interface Props {
  isOpen: boolean
  onClose: () => void
  onSave: (offer: OfferItem) => void
  initialOffer?: OfferItem | null
}

export function OfferFormModal({
  isOpen,
  onClose,
  onSave,
  initialOffer,
}: Props) {
  const [name, setName] = useState('')
  const [provider, setProvider] = useState('')
  const [type, setType] = useState<'personal_loan' | 'credit_card' | 'bnpl' | 'other'>('personal_loan')
  const [principalRupees, setPrincipalRupees] = useState('20000')
  const [feesRupees, setFeesRupees] = useState('500')
  const [ratePct, setRatePct] = useState('14.00')
  const [termMonths, setTermMonths] = useState('6')
  const [eligibility, setEligibility] = useState('')
  const [isDemo, setIsDemo] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (initialOffer) {
      setName(initialOffer.offer_name || '')
      setProvider(initialOffer.provider || '')
      setType(initialOffer.offer_type)
      setPrincipalRupees(String(initialOffer.principal_paise / 100))
      setFeesRupees(String(initialOffer.fees_paise / 100))
      setRatePct(initialOffer.rate_annual_pct || '0.00')
      setTermMonths(String(initialOffer.term_months || 3))
      setEligibility(initialOffer.eligibility_evidence || '')
      setIsDemo(Boolean(initialOffer.is_demo))
    } else {
      setName('')
      setProvider('')
      setType('personal_loan')
      setPrincipalRupees('20000')
      setFeesRupees('500')
      setRatePct('14.00')
      setTermMonths('6')
      setEligibility('Pre-approved based on income statement')
      setIsDemo(false)
    }
    setError(null)
  }, [initialOffer, isOpen])

  const applyTemplate = (
    tplName: string,
    tplProvider: string,
    tplType: 'personal_loan' | 'credit_card' | 'bnpl' | 'other',
    tplPrincipal: string,
    tplFees: string,
    tplRate: string,
    tplTerm: string
  ) => {
    setName(tplName)
    setProvider(tplProvider)
    setType(tplType)
    setPrincipalRupees(tplPrincipal)
    setFeesRupees(tplFees)
    setRatePct(tplRate)
    setTermMonths(tplTerm)
    setEligibility('Synthetic demo quote from pre-qualification engine')
    setIsDemo(true)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    try {
      const pPaise = rupeesToPaise(principalRupees)
      const fPaise = rupeesToPaise(feesRupees)
      const term = parseInt(termMonths, 10)

      if (pPaise <= 0) {
        setError('Principal borrowed must be greater than ₹0')
        return
      }
      if (fPaise < 0) {
        setError('Fees cannot be negative')
        return
      }
      if (fPaise >= pPaise) {
        setError('Fees cannot exceed or equal the principal borrowed')
        return
      }
      if (isNaN(term) || term <= 0) {
        setError('Tenure must be at least 1 month')
        return
      }

      onSave({
        id: initialOffer?.id,
        scenario_id: initialOffer?.scenario_id,
        offer_name: name || `${type.replace('_', ' ').toUpperCase()} Offer`,
        provider: provider || 'Financing Partner',
        offer_type: type,
        principal_paise: pPaise,
        fees_paise: fPaise,
        rate_annual_pct: parseFloat(ratePct).toFixed(2),
        term_months: term,
        eligibility_evidence: eligibility,
        is_demo: isDemo,
      })
      onClose()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Invalid amount entered')
    }
  }

  return (
    <Modal open={isOpen} onClose={onClose} title={initialOffer ? 'Edit Borrowing Offer' : 'Add Borrowing Offer'}>
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {!initialOffer && (
          <div
            style={{
              padding: 10,
              background: '#f0fdfa',
              border: '1px solid #ccfbf1',
              borderRadius: 'var(--radius-sm)',
            }}
          >
            <span
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: 'var(--color-primary)',
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                marginBottom: 6,
              }}
            >
              <Sparkles size={14} /> Quick Demo Offer Templates (Labelled & Safe)
            </span>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              <button
                type="button"
                onClick={() =>
                  applyTemplate(
                    'Demo 3-Mo BNPL',
                    'PayLater Fin',
                    'bnpl',
                    '20000',
                    '400',
                    '0.00',
                    '3'
                  )
                }
                style={{
                  fontSize: 11,
                  padding: '4px 8px',
                  borderRadius: 4,
                  background: '#ffffff',
                  border: '1px solid #99f6e4',
                  cursor: 'pointer',
                }}
              >
                Demo BNPL (0%, 3 mo)
              </button>
              <button
                type="button"
                onClick={() =>
                  applyTemplate(
                    'Demo Instant Personal Loan',
                    'Axis Express',
                    'personal_loan',
                    '25000',
                    '1200',
                    '14.50',
                    '6'
                  )
                }
                style={{
                  fontSize: 11,
                  padding: '4px 8px',
                  borderRadius: 4,
                  background: '#ffffff',
                  border: '1px solid #99f6e4',
                  cursor: 'pointer',
                }}
              >
                Demo Personal Loan (14.5%, 6 mo)
              </button>
              <button
                type="button"
                onClick={() =>
                  applyTemplate(
                    'Demo Card EMI Option',
                    'HDFC Card EMI',
                    'credit_card',
                    '20000',
                    '800',
                    '16.00',
                    '6'
                  )
                }
                style={{
                  fontSize: 11,
                  padding: '4px 8px',
                  borderRadius: 4,
                  background: '#ffffff',
                  border: '1px solid #99f6e4',
                  cursor: 'pointer',
                }}
              >
                Demo Card EMI (16%, 6 mo)
              </button>
            </div>
          </div>
        )}

        {error && (
          <div
            role="alert"
            style={{
              padding: '8px 12px',
              borderRadius: 'var(--radius-sm)',
              background: '#fee2e2',
              color: 'var(--color-shortfall)',
              fontSize: 12,
            }}
          >
            {error}
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <Field label="Offer Name">
            <input
              id="offer-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Axis Express Personal Loan"
              style={{ width: '100%', padding: '8px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)' }}
            />
          </Field>

          <Field label="Provider / Bank">
            <input
              id="offer-provider"
              type="text"
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              placeholder="e.g. Axis Bank, Tata Neu"
              style={{ width: '100%', padding: '8px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)' }}
            />
          </Field>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <Field label="Offer Type">
            <select
              id="offer-type"
              value={type}
              onChange={(e) => setType(e.target.value as any)}
              style={{ width: '100%', padding: '8px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)' }}
            >
              <option value="personal_loan">Personal Loan</option>
              <option value="credit_card">Credit Card EMI</option>
              <option value="bnpl">Buy Now Pay Later (BNPL)</option>
              <option value="other">Other Financing</option>
            </select>
          </Field>

          <Field label="Gross Amount Borrowed (₹)">
            <input
              id="offer-principal"
              type="number"
              step="100"
              value={principalRupees}
              onChange={(e) => setPrincipalRupees(e.target.value)}
              required
              style={{ width: '100%', padding: '8px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)' }}
            />
          </Field>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
          <Field label="Processing Fees (₹)">
            <input
              id="offer-fees"
              type="number"
              step="50"
              value={feesRupees}
              onChange={(e) => setFeesRupees(e.target.value)}
              style={{ width: '100%', padding: '8px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)' }}
            />
          </Field>

          <Field label="Interest Rate (% p.a.)">
            <input
              id="offer-rate"
              type="number"
              step="0.1"
              value={ratePct}
              onChange={(e) => setRatePct(e.target.value)}
              style={{ width: '100%', padding: '8px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)' }}
            />
          </Field>

          <Field label="Tenure (Months)">
            <input
              id="offer-term"
              type="number"
              min="1"
              max="60"
              value={termMonths}
              onChange={(e) => setTermMonths(e.target.value)}
              required
              style={{ width: '100%', padding: '8px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)' }}
            />
          </Field>
        </div>

        <Field label="Eligibility / Quotation Source Note">
          <input
            id="offer-eligibility"
            type="text"
            value={eligibility}
            onChange={(e) => setEligibility(e.target.value)}
            placeholder="e.g. In-app pre-approved banner, soft quotation"
            style={{ width: '100%', padding: '8px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)' }}
          />
        </Field>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
          <Button variant="ghost" type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" type="submit">
            {initialOffer ? 'Update Offer' : 'Add to Scenario'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
