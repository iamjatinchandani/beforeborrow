import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AnalysisMetric } from '../components/AnalysisMetric'

describe('AnalysisMetric', () => {
  it('renders metric label and formatted integer paise value correctly', () => {
    render(
      <AnalysisMetric
        label="Total Repayment"
        value={2400000}
        type="paise"
        description="Full scheduled outflow"
      />
    )

    expect(screen.getByText('Total Repayment')).toBeInTheDocument()
    expect(screen.getByText('₹24,000')).toBeInTheDocument()
    expect(screen.getByText('Full scheduled outflow')).toBeInTheDocument()
  })

  it('renders date values properly when type is date', () => {
    render(
      <AnalysisMetric
        label="First Reserve Breach"
        value="2026-11-03"
        type="date"
      />
    )

    expect(screen.getByText('First Reserve Breach')).toBeInTheDocument()
    expect(screen.getByText('3 Nov 2026')).toBeInTheDocument()
  })

  it('handles missing/null/undefined values honestly without converting to zero', () => {
    render(
      <AnalysisMetric
        label="Discretionary Savings"
        value={null}
        type="paise"
      />
    )

    expect(screen.getByText('Discretionary Savings')).toBeInTheDocument()
    expect(screen.getByText('Not available')).toBeInTheDocument()
    expect(screen.queryByText('₹0')).not.toBeInTheDocument()
  })

  it('renders optional status badge and subtext', () => {
    render(
      <AnalysisMetric
        label="Trough Cash"
        value={-500000}
        type="paise"
        shortfall={true}
        subtext="Trough on 12 Nov 2026"
        badge={{ status: 'shortfall', label: 'DEFICIT' }}
      />
    )

    expect(screen.getByText('Trough Cash')).toBeInTheDocument()
    expect(screen.getByText('-₹5,000')).toBeInTheDocument()
    expect(screen.getByText('Trough on 12 Nov 2026')).toBeInTheDocument()
    expect(screen.getByText('DEFICIT')).toBeInTheDocument()
  })
})
