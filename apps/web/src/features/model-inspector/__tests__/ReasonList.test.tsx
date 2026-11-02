import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ReasonList } from '../components/ReasonList'
import { ReasonEvidence } from '../types'

describe('ReasonList', () => {
  it('renders fallback when evidence list is empty', () => {
    render(<ReasonList evidence={[]} />)
    expect(screen.getByText('No reason evidence recorded for this calculation.')).toBeInTheDocument()
  })

  it('renders detailed reason evidence fields accurately', () => {
    const mockEvidence: ReasonEvidence[] = [
      {
        code: 'RESERVE_BREACH',
        date: '2026-11-03',
        message_key: 'breach_after_rent',
        before_paise: 1200000,
        after_paise: 400000,
        threshold_paise: 500000,
        assumptions: ['Rent debited before salary credit', 'Standard same-day order'],
        event_ids: ['rent-nov', 'first-installment'],
      },
    ]

    render(<ReasonList evidence={mockEvidence} />)

    expect(screen.getByText('RESERVE_BREACH')).toBeInTheDocument()
    expect(screen.getByText('breach_after_rent')).toBeInTheDocument()
    expect(screen.getByText('3 Nov 2026')).toBeInTheDocument()
    expect(screen.getByText('₹12,000')).toBeInTheDocument()
    expect(screen.getByText('₹4,000')).toBeInTheDocument()
    expect(screen.getByText('₹5,000')).toBeInTheDocument()
    expect(screen.getByText('Rent debited before salary credit')).toBeInTheDocument()
    expect(screen.getByText('rent-nov, first-installment')).toBeInTheDocument()
  })
})
