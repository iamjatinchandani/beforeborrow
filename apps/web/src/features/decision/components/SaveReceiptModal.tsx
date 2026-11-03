import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Modal } from '../../../components/ui/Modal'
import { Button } from '../../../components/ui/Button'
import { Field } from '../../../components/ui/Field'
import { reportsApi } from '@/features/reports/api'
import { OfferAnalysisResult } from '../types'
import { ShieldCheck, ArrowRight } from 'lucide-react'

interface Props {
  isOpen: boolean
  onClose: () => void
  analysisId: string
  offers: OfferAnalysisResult[]
}

export function SaveReceiptModal({
  isOpen,
  onClose,
  analysisId,
  offers,
}: Props) {
  const navigate = useNavigate()
  const [selectedOffer, setSelectedOffer] = useState(offers[0]?.offer_name || 'Option 1')
  const [tightDate, setTightDate] = useState('')
  const [keyAssumption, setKeyAssumption] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSaving(true)
    setError(null)

    try {
      const res = await reportsApi.createReceipt({
        analysis_id: analysisId,
        chosen_option: selectedOffer,
        reflection_answers: {
          tight_repayment_date: tightDate || 'None specified',
          key_income_assumption: keyAssumption || 'Standard salary credit',
        },
      })
      onClose()
      const receiptId = (res as any).id
      if (receiptId) {
        navigate(`/reports/${receiptId}`)
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to save decision receipt')
      setIsSaving(false)
    }
  }

  return (
    <Modal open={isOpen} onClose={onClose} title="Save Decision Receipt">
      <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#047857', fontSize: 13 }}>
          <ShieldCheck size={18} />
          <span>
            This produces an immutable decision receipt preserving your exact inputs, snapshot hash, and consequence metrics.
          </span>
        </div>

        {error && (
          <div style={{ padding: '8px 12px', background: '#fee2e2', color: 'var(--color-shortfall)', borderRadius: 'var(--radius-sm)', fontSize: 12 }}>
            {error}
          </div>
        )}

        <Field label="Selected Funding Option" htmlFor="receipt-option">
          <select
            id="receipt-option"
            value={selectedOffer}
            onChange={(e) => setSelectedOffer(e.target.value)}
            style={{ width: '100%', padding: '8px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)' }}
          >
            {offers.map((off, idx) => (
              <option key={off.offer_id || idx} value={off.offer_name || `Option ${idx + 1}`}>
                {off.offer_name} ({off.provider})
              </option>
            ))}
          </select>
        </Field>

        <div style={{ borderTop: '1px solid var(--color-border)', paddingTop: 12 }}>
          <h5 style={{ margin: '0 0 4px', fontSize: 13, fontWeight: 600, color: 'var(--color-text)' }}>
            User Reflection (Optional / Skippable)
          </h5>
          <p style={{ margin: '0 0 12px', fontSize: 12, color: '#64748b' }}>
            Recording your thoughts strengthens your financial discipline before signing any agreement.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <Field label="1. Which repayment date feels tightest in your calendar?">
              <input
                id="reflection-date"
                type="text"
                value={tightDate}
                onChange={(e) => setTightDate(e.target.value)}
                placeholder="e.g. 5 Nov rent week, or mid-month school fees"
                style={{ width: '100%', padding: '8px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)' }}
              />
            </Field>

            <Field label="2. Which income assumption matters most to keep this safe?">
              <input
                id="reflection-assumption"
                type="text"
                value={keyAssumption}
                onChange={(e) => setKeyAssumption(e.target.value)}
                placeholder="e.g. On-time salary by 30th, expected quarterly bonus"
                style={{ width: '100%', padding: '8px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)' }}
              />
            </Field>
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
          <Button variant="secondary" type="button" onClick={onClose} disabled={isSaving}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" disabled={isSaving}>
            {isSaving ? 'Preserving...' : 'Save & View Receipt'} <ArrowRight size={14} />
          </Button>
        </div>
      </form>
    </Modal>
  )
}
