import { Money } from '../../../components/ui/Money'
import { Card } from '../../../components/ui/Card'
import { Button } from '../../../components/ui/Button'
import { OfferItem } from '../types'
import { Copy, Trash2, Edit3, Tag } from 'lucide-react'

interface Props {
  offer: OfferItem
  index: number
  onEdit: () => void
  onDuplicate: () => void
  onRemove: () => void
  canDuplicate: boolean
}

export function OfferCard({
  offer,
  index,
  onEdit,
  onDuplicate,
  onRemove,
  canDuplicate,
}: Props) {
  const netDisbursed = Math.max(0, offer.principal_paise - offer.fees_paise)
  const isDemo =
    offer.is_demo ||
    (offer.offer_name && offer.offer_name.toLowerCase().includes('demo')) ||
    (offer.provider && offer.provider.toLowerCase().includes('demo'))

  return (
    <Card
      style={{
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius)',
        padding: 'var(--space-2)',
        position: 'relative',
        background: '#ffffff',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                textTransform: 'uppercase',
                background: '#e0f2fe',
                color: '#0369a1',
                padding: '2px 6px',
                borderRadius: 4,
              }}
            >
              Option {index + 1}
            </span>
            {isDemo && (
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  background: '#fef3c7',
                  color: '#92400e',
                  padding: '2px 6px',
                  borderRadius: 4,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 3,
                }}
              >
                <Tag size={10} /> Demo offer
              </span>
            )}
          </div>
          <h4 style={{ margin: '6px 0 2px', fontSize: 16, fontWeight: 600 }}>
            {offer.offer_name || `${offer.offer_type.replace('_', ' ').toUpperCase()}`}
          </h4>
          <span style={{ fontSize: 12, color: '#64748b' }}>
            Provider: {offer.provider || 'Self-Arranged'}
          </span>
        </div>

        <div style={{ display: 'flex', gap: 4 }}>
          <Button variant="secondary" size="sm" onClick={onEdit} title="Edit Offer">
            <Edit3 size={14} />
          </Button>
          {canDuplicate && (
            <Button variant="secondary" size="sm" onClick={onDuplicate} title="Duplicate Offer">
              <Copy size={14} />
            </Button>
          )}
          <Button variant="danger" size="sm" onClick={onRemove} title="Remove Offer">
            <Trash2 size={14} />
          </Button>
        </div>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(2, 1fr)',
          gap: 10,
          background: 'var(--color-bg-muted)',
          padding: '10px 12px',
          borderRadius: 'var(--radius-sm)',
          fontSize: 13,
        }}
      >
        <div>
          <span style={{ color: '#64748b', fontSize: 11, display: 'block' }}>Borrowed (Gross)</span>
          <strong><Money paise={offer.principal_paise} /></strong>
        </div>
        <div>
          <span style={{ color: '#64748b', fontSize: 11, display: 'block' }}>Net Cash Received</span>
          <strong style={{ color: 'var(--color-primary)' }}><Money paise={netDisbursed} /></strong>
        </div>
        <div>
          <span style={{ color: '#64748b', fontSize: 11, display: 'block' }}>Upfront Fees</span>
          <span><Money paise={offer.fees_paise} /></span>
        </div>
        <div>
          <span style={{ color: '#64748b', fontSize: 11, display: 'block' }}>Interest / Tenure</span>
          <span>{offer.rate_annual_pct}% p.a. • {offer.term_months || 1} mo</span>
        </div>
      </div>
    </Card>
  )
}
