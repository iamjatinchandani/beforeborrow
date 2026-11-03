import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AutosaveIndicator } from '../components/AutosaveIndicator'
import { OfferCard } from '../components/OfferCard'
import { MissingSetupBanner } from '../components/MissingSetupBanner'
import { SqueezeCauses } from '../components/SqueezeCauses'
import { AccessibleLedger } from '../components/AccessibleLedger'
import { OfferItem } from '../types'

describe('Person D - Emergency Decision Studio Components', () => {
  it('renders AutosaveIndicator in saving, saved, and error states', () => {
    const { rerender } = render(<AutosaveIndicator status="saving" />)
    expect(screen.getByText(/Autosaving draft/i)).toBeInTheDocument()

    rerender(<AutosaveIndicator status="saved" lastSavedAt={new Date('2026-11-03T16:00:00')} />)
    expect(screen.getByText(/Draft saved/i)).toBeInTheDocument()

    rerender(<AutosaveIndicator status="error" />)
    expect(screen.getByText(/Failed to autosave/i)).toBeInTheDocument()
  })

  it('renders OfferCard with Demo offer badge and consequence figures', () => {
    const mockOffer: OfferItem = {
      offer_name: 'Demo 3-Mo BNPL',
      provider: 'PayLater Fin',
      offer_type: 'bnpl',
      principal_paise: 2_000_000,
      fees_paise: 40_000,
      rate_annual_pct: '0.00',
      term_months: 3,
      is_demo: true,
    }

    const onEdit = vi.fn()
    const onDuplicate = vi.fn()
    const onRemove = vi.fn()

    render(
      <OfferCard
        offer={mockOffer}
        index={0}
        onEdit={onEdit}
        onDuplicate={onDuplicate}
        onRemove={onRemove}
        canDuplicate={true}
      />
    )

    expect(screen.getByText('Option 1')).toBeInTheDocument()
    expect(screen.getByText('Demo offer')).toBeInTheDocument()
    expect(screen.getByText('Demo 3-Mo BNPL')).toBeInTheDocument()
    expect(screen.getByText('Provider: PayLater Fin')).toBeInTheDocument()
    expect(screen.getByText(/0.00% p.a. • 3 mo/i)).toBeInTheDocument()

    // Test actions
    fireEvent.click(screen.getByTitle('Edit Offer'))
    expect(onEdit).toHaveBeenCalledOnce()

    fireEvent.click(screen.getByTitle('Duplicate Offer'))
    expect(onDuplicate).toHaveBeenCalledOnce()

    fireEvent.click(screen.getByTitle('Remove Offer'))
    expect(onRemove).toHaveBeenCalledOnce()
  })

  it('renders MissingSetupBanner when financial setup is incomplete', () => {
    const setupStatus = {
      is_complete: false,
      missing_fields: ['opening_cash', 'reserve_floor'],
      has_profile: false,
      profile_data_version: 0,
      obligations_count: 0,
    }

    render(
      <MemoryRouter>
        <MissingSetupBanner status={setupStatus} />
      </MemoryRouter>
    )

    expect(screen.getByText('Incomplete Financial Setup')).toBeInTheDocument()
    expect(screen.getByText(/opening cash, reserve floor/i)).toBeInTheDocument()
    expect(screen.getByText(/Configure Profile/i)).toBeInTheDocument()
  })

  it('renders SqueezeCauses with reason code badges and source events', () => {
    const causes = [
      {
        date: '2026-11-03',
        title: 'Reserve floor breach on 3 Nov',
        detail: 'Cash drops to ₹4,000, below your ₹5,000 reserve floor.',
        source_event: 'Rent & Upfront Fee',
      },
    ]
    const reasonCodes = ['reserve_breach', 'negative_balance']

    render(<SqueezeCauses causes={causes} reasonCodes={reasonCodes} />)

    expect(screen.getByText(/Reserve floor breach on 3 Nov/i)).toBeInTheDocument()
    expect(screen.getByText(/Rent & Upfront Fee/i)).toBeInTheDocument()
    expect(screen.getByText(/Cash falls below reserve floor threshold/i)).toBeInTheDocument()
    expect(screen.getByText(/Cash balance falls into negative deficit/i)).toBeInTheDocument()
  })

  it('renders AccessibleLedger table with chronological financial events', () => {
    const events = [
      {
        date: '2026-11-01',
        description: 'Opening cash balance',
        inflow_paise: 800_000,
        outflow_paise: 0,
        balance_paise: 800_000,
        source: 'Profile',
      },
      {
        date: '2026-11-05',
        description: 'Rent & Existing Loan EMI',
        inflow_paise: 0,
        outflow_paise: 2_700_000,
        balance_paise: -1_900_000,
        source: 'Obligations',
      },
    ]

    render(<AccessibleLedger events={events} reserveFloorPaise={500_000} />)

    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(screen.getByText('Opening cash balance')).toBeInTheDocument()
    expect(screen.getByText('Rent & Existing Loan EMI')).toBeInTheDocument()
    expect(screen.getByText('[NEGATIVE CASH]')).toBeInTheDocument()
  })
})
