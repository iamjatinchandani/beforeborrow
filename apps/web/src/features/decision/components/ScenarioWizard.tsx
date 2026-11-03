import { useState, useRef } from 'react'
import { Card } from '../../../components/ui/Card'
import { Button } from '../../../components/ui/Button'
import { Field } from '../../../components/ui/Field'
import { Money, rupeesToPaise } from '../../../components/ui/Money'
import { ScenarioData, OfferItem } from '../types'
import { OfferCard } from './OfferCard'
import { OfferFormModal } from './OfferFormModal'
import { AutosaveIndicator, SaveStatus } from './AutosaveIndicator'
import {
  ChevronRight,
  ChevronLeft,
  Plus,
  Play,
  AlertCircle,
} from 'lucide-react'

interface Props {
  initialData?: ScenarioData
  onSaveDraft: (data: ScenarioData) => Promise<ScenarioData | void>
  onRunAnalysis: (data: ScenarioData) => void
  isAnalyzing: boolean
}

const CATEGORIES = [
  'Medical emergency',
  'Education',
  'Household expense',
  'Travel',
  'Vehicle repair',
  'Other urgent expense',
]

export function ScenarioWizard({
  initialData,
  onSaveDraft,
  onRunAnalysis,
  isAnalyzing,
}: Props) {
  const [step, setStep] = useState(1)

  // Form State
  const [category, setCategory] = useState(initialData?.category || 'Medical emergency')
  const [expenseRupees, setExpenseRupees] = useState(
    initialData ? String(initialData.expense_amount_paise / 100) : '20000'
  )
  const [expenseDate, setExpenseDate] = useState(
    initialData?.expense_date || '2026-11-08'
  )
  const [needCash, setNeedCash] = useState(initialData?.need_cash ?? true)
  const [horizonDays, setHorizonDays] = useState(initialData?.horizon_days || 90)

  // Step 2 State
  const [savingsRupees, setSavingsRupees] = useState(
    initialData ? String(initialData.allowed_savings_paise / 100) : '5000'
  )

  // Step 3 State: Offers
  const [offers, setOffers] = useState<OfferItem[]>(
    initialData?.offers || [
      {
        offer_name: 'Demo 3-Mo BNPL',
        provider: 'PayLater Fin',
        offer_type: 'bnpl',
        principal_paise: 1_500_000,
        fees_paise: 40_000,
        rate_annual_pct: '0.00',
        term_months: 3,
        eligibility_evidence: 'Pre-approved in-app',
        is_demo: true,
      },
      {
        offer_name: 'Demo Personal Loan',
        provider: 'Axis Express',
        offer_type: 'personal_loan',
        principal_paise: 2_000_000,
        fees_paise: 100_000,
        rate_annual_pct: '14.00',
        term_months: 6,
        eligibility_evidence: 'Salary account offer',
        is_demo: true,
      },
    ]
  )

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingIndex, setEditingIndex] = useState<number | null>(null)

  // Autosave State
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle')
  const [lastSaved, setLastSaved] = useState<Date | null>(null)
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Compute live data object
  const getCurrentScenarioData = (): ScenarioData => {
    let expPaise = 2_000_000
    let savPaise = 0
    try {
      expPaise = rupeesToPaise(expenseRupees)
    } catch {
      expPaise = 0
    }
    try {
      savPaise = rupeesToPaise(savingsRupees)
    } catch {
      savPaise = 0
    }

    return {
      id: initialData?.id,
      category,
      expense_amount_paise: expPaise,
      expense_date: expenseDate,
      need_cash: needCash,
      allowed_savings_paise: savPaise,
      horizon_days: horizonDays,
      offers,
    }
  }

  // Trigger autosave on field changes
  const triggerAutosave = () => {
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current)
    setSaveStatus('saving')

    debounceTimerRef.current = setTimeout(async () => {
      try {
        const data = getCurrentScenarioData()
        if (data.expense_amount_paise > 0) {
          await onSaveDraft(data)
          setSaveStatus('saved')
          setLastSaved(new Date())
        }
      } catch {
        setSaveStatus('error')
      }
    }, 1200)
  }

  // Offer handlers
  const handleSaveOffer = (offer: OfferItem) => {
    if (editingIndex !== null) {
      const updated = [...offers]
      updated[editingIndex] = offer
      setOffers(updated)
    } else {
      if (offers.length >= 3) return
      setOffers([...offers, offer])
    }
    setEditingIndex(null)
    triggerAutosave()
  }

  const handleDuplicateOffer = (idx: number) => {
    if (offers.length >= 3) return
    const target = offers[idx]
    const dup: OfferItem = {
      ...target,
      id: undefined,
      offer_name: `${target.offer_name || 'Offer'} (Copy)`,
    }
    setOffers([...offers, dup])
    triggerAutosave()
  }

  const handleRemoveOffer = (idx: number) => {
    const updated = offers.filter((_, i) => i !== idx)
    setOffers(updated)
    triggerAutosave()
  }

  const expPaise = Math.max(0, parseFloat(expenseRupees || '0') * 100)
  const savPaise = Math.max(0, parseFloat(savingsRupees || '0') * 100)
  const fundingGapPaise = Math.max(0, expPaise - savPaise)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
      {/* Wizard Header & Progress */}
      <Card
        style={{
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius)',
          padding: '16px 20px',
          background: '#ffffff',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700 }}>
              Emergency Decision Studio
            </h2>
            <p style={{ margin: '2px 0 0', fontSize: 13, color: '#64748b' }}>
              Rehearse borrowing consequences before you commit.
            </p>
          </div>
          <AutosaveIndicator status={saveStatus} lastSavedAt={lastSaved} />
        </div>

        {/* Step Indicator Bar */}
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {[
            { num: 1, label: '1. Expense Details' },
            { num: 2, label: '2. Savings Contribution' },
            { num: 3, label: '3. Funding Offers' },
          ].map((s) => (
            <button
              key={s.num}
              type="button"
              onClick={() => setStep(s.num)}
              style={{
                flex: 1,
                padding: '8px 12px',
                borderRadius: 'var(--radius-sm)',
                border: 'none',
                background: step === s.num ? 'var(--color-primary)' : step > s.num ? '#e0f2fe' : 'var(--color-bg-muted)',
                color: step === s.num ? '#ffffff' : step > s.num ? '#0369a1' : '#64748b',
                fontWeight: 600,
                fontSize: 13,
                cursor: 'pointer',
                textAlign: 'left',
              }}
            >
              {s.label}
            </button>
          ))}
        </div>
      </Card>

      {/* Step 1: Expense Details */}
      {step === 1 && (
        <Card style={{ border: '1px solid var(--color-border)', borderRadius: 'var(--radius)', padding: 'var(--space-3)', background: '#ffffff' }}>
          <h3 style={{ margin: '0 0 16px', fontSize: 16, fontWeight: 600 }}>
            Step 1: Emergency Expense Parameters
          </h3>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 16 }}>
            <Field label="Emergency Purpose / Category">
              <select
                id="scenario-category"
                value={category}
                onChange={(e) => {
                  setCategory(e.target.value)
                  triggerAutosave()
                }}
                style={{ width: '100%', padding: '10px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)', fontSize: 14 }}
              >
                {CATEGORIES.map((cat) => (
                  <option key={cat} value={cat}>{cat}</option>
                ))}
              </select>
            </Field>

            <Field label="Required Expense Amount (₹)">
              <input
                id="scenario-amount"
                type="number"
                step="500"
                value={expenseRupees}
                onChange={(e) => {
                  setExpenseRupees(e.target.value)
                  triggerAutosave()
                }}
                required
                style={{ width: '100%', padding: '10px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)', fontSize: 14, fontWeight: 600 }}
              />
            </Field>

            <Field label="Required Payment Date">
              <input
                id="scenario-date"
                type="date"
                value={expenseDate}
                onChange={(e) => {
                  setExpenseDate(e.target.value)
                  triggerAutosave()
                }}
                required
                style={{ width: '100%', padding: '10px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)', fontSize: 14 }}
              />
            </Field>

            <Field label="Analysis Horizon (Days)">
              <select
                id="scenario-horizon"
                value={horizonDays}
                onChange={(e) => {
                  setHorizonDays(Number(e.target.value))
                  triggerAutosave()
                }}
                style={{ width: '100%', padding: '10px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)', fontSize: 14 }}
              >
                <option value={30}>30 Days (Immediate recovery)</option>
                <option value={90}>90 Days (Quarterly buffer)</option>
                <option value={180}>180 Days (Standard 6-Month)</option>
                <option value={365}>365 Days (Full Year Outlook)</option>
              </select>
            </Field>
          </div>

          <div style={{ marginTop: 16 }}>
            <label style={{ display: 'inline-flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 13, fontWeight: 500 }}>
              <input
                type="checkbox"
                checked={needCash}
                onChange={(e) => {
                  setNeedCash(e.target.checked)
                  triggerAutosave()
                }}
                style={{ width: 16, height: 16, accentColor: 'var(--color-primary)' }}
              />
              Expense requires cash disbursement (excludes merchant-only voucher/card limits)
            </label>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 20 }}>
            <Button variant="primary" onClick={() => setStep(2)}>
              Next: Savings Contribution <ChevronRight size={14} />
            </Button>
          </div>
        </Card>
      )}

      {/* Step 2: Savings Allocation */}
      {step === 2 && (
        <Card style={{ border: '1px solid var(--color-border)', borderRadius: 'var(--radius)', padding: 'var(--space-3)', background: '#ffffff' }}>
          <h3 style={{ margin: '0 0 16px', fontSize: 16, fontWeight: 600 }}>
            Step 2: Self-Funding & Allowed Savings Contribution
          </h3>

          <p style={{ margin: '0 0 16px', fontSize: 13, color: '#475569', lineHeight: 1.5 }}>
            Decide how much of your current cash balance you allow yourself to spend directly towards this expense.
            Preserving a reserve floor protects you against next week's regular commitments.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16 }}>
            <Field label="Maximum Savings Contribution Allowed (₹)">
              <input
                id="scenario-savings"
                type="number"
                step="500"
                value={savingsRupees}
                onChange={(e) => {
                  setSavingsRupees(e.target.value)
                  triggerAutosave()
                }}
                style={{ width: '100%', padding: '10px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border)', fontSize: 14, fontWeight: 600 }}
              />
            </Field>

            {/* Live Gap Summary */}
            <div
              style={{
                background: 'var(--color-bg-muted)',
                padding: '14px 16px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--color-border)',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
                gap: 6,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                <span style={{ color: '#64748b' }}>Total Expense:</span>
                <strong><Money paise={expPaise} /></strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                <span style={{ color: '#64748b' }}>Self-Funded from Savings:</span>
                <span style={{ color: 'var(--color-primary)', fontWeight: 600 }}><Money paise={savPaise} /></span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 14, borderTop: '1px solid #e2e8f0', paddingTop: 6 }}>
                <strong>Borrowing Need (Funding Gap):</strong>
                <strong style={{ color: fundingGapPaise > 0 ? 'var(--color-shortfall)' : 'var(--color-primary)' }}>
                  <Money paise={fundingGapPaise} />
                </strong>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 24 }}>
            <Button variant="secondary" onClick={() => setStep(1)}>
              <ChevronLeft size={14} /> Back
            </Button>
            <Button variant="primary" onClick={() => setStep(3)}>
              Next: Funding Offers <ChevronRight size={14} />
            </Button>
          </div>
        </Card>
      )}

      {/* Step 3: Funding Offers */}
      {step === 3 && (
        <Card style={{ border: '1px solid var(--color-border)', borderRadius: 'var(--radius)', padding: 'var(--space-3)', background: '#ffffff' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <div>
              <h3 style={{ margin: '0 0 2px', fontSize: 16, fontWeight: 600 }}>
                Step 3: Candidate Funding Offers ({offers.length} / 3)
              </h3>
              <p style={{ margin: 0, fontSize: 13, color: '#64748b' }}>
                Enter up to 3 funding arrangements to compare on actual dates.
              </p>
            </div>

            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setEditingIndex(null)
                setIsModalOpen(true)
              }}
              disabled={offers.length >= 3}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
            >
              <Plus size={14} /> Add Offer
            </Button>
          </div>

          {offers.length === 0 ? (
            <div
              style={{
                padding: '32px 16px',
                textAlign: 'center',
                background: 'var(--color-bg-muted)',
                borderRadius: 'var(--radius-sm)',
                border: '1px dashed var(--color-border)',
              }}
            >
              <AlertCircle size={28} color="#94a3b8" style={{ marginBottom: 8 }} />
              <h4 style={{ margin: '0 0 4px', fontSize: 15 }}>No Offers Added Yet</h4>
              <p style={{ margin: '0 0 16px', fontSize: 13, color: '#64748b' }}>
                Add at least one borrowing offer or choose from demo templates to run the consequence simulation.
              </p>
              <Button
                variant="primary"
                size="sm"
                onClick={() => {
                  setEditingIndex(null)
                  setIsModalOpen(true)
                }}
              >
                <Plus size={14} /> Add First Offer
              </Button>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 14 }}>
              {offers.map((off, idx) => (
                <OfferCard
                  key={off.id || idx}
                  offer={off}
                  index={idx}
                  onEdit={() => {
                    setEditingIndex(idx)
                    setIsModalOpen(true)
                  }}
                  onDuplicate={() => handleDuplicateOffer(idx)}
                  onRemove={() => handleRemoveOffer(idx)}
                  canDuplicate={offers.length < 3}
                />
              ))}
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 24, borderTop: '1px solid var(--color-border)', paddingTop: 16 }}>
            <Button variant="secondary" onClick={() => setStep(2)}>
              <ChevronLeft size={14} /> Back
            </Button>

            <Button
              variant="primary"
              onClick={() => onRunAnalysis(getCurrentScenarioData())}
              disabled={offers.length === 0 || isAnalyzing}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '10px 20px', fontSize: 15, fontWeight: 700 }}
            >
              <Play size={16} /> {isAnalyzing ? 'Simulating Cashflows...' : 'Compare Consequences'}
            </Button>
          </div>
        </Card>
      )}

      {/* Offer Form Modal */}
      {isModalOpen && (
        <OfferFormModal
          isOpen={isModalOpen}
          onClose={() => {
            setIsModalOpen(false)
            setEditingIndex(null)
          }}
          onSave={handleSaveOffer}
          initialOffer={editingIndex !== null ? offers[editingIndex] : null}
        />
      )}
    </div>
  )
}
