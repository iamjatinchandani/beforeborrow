import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import ModelInspectorPage from '../pages/ModelInspectorPage'
import * as authHooks from '@/features/auth/hooks'
import * as inspectorHooks from '../hooks'
import { AnalysisOut, AnalysisResult, CounterfactualOut } from '../types'

// Mock Recharts ResponsiveContainer to avoid SVG measurement issues in jsdom
vi.mock('recharts', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('recharts')
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: ReactNode }) => (
      <div data-testid="responsive-container" style={{ width: '100%', height: 300 }}>
        {children}
      </div>
    ),
  }
})

describe('ModelInspectorPage', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    vi.clearAllMocks()

    vi.spyOn(authHooks, 'useMe').mockReturnValue({
      data: {
        id: 'user-123',
        email_normalized: 'test@example.com',
        created_at: '2026-11-01T00:00:00Z',
        csrf_token: 'csrf-123',
      },
      isLoading: false,
    } as any)
  })

  it('renders initial search form when no analysis ID is provided in URL', () => {
    vi.spyOn(inspectorHooks, 'useAnalysis').mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/model-inspector']}>
          <Routes>
            <Route path="/model-inspector" element={<ModelInspectorPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    )

    expect(screen.getByText('Model Inspector')).toBeInTheDocument()
    expect(screen.getByText('No Analysis Selected')).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/e\.g\. 550e8400/i)).toBeInTheDocument()
  })

  it('renders loading state while analysis query is pending', () => {
    vi.spyOn(inspectorHooks, 'useAnalysis').mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/model-inspector?analysis_id=an-1']}>
          <Routes>
            <Route path="/model-inspector" element={<ModelInspectorPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    )

    expect(screen.getByText('Loading Analysis Record...')).toBeInTheDocument()
  })

  it('renders error panel with retry when analysis query fails', () => {
    const mockRefetch = vi.fn()
    vi.spyOn(inspectorHooks, 'useAnalysis').mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error('Analysis record not found'),
      refetch: mockRefetch,
    } as any)

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/model-inspector?analysis_id=an-not-found']}>
          <Routes>
            <Route path="/model-inspector" element={<ModelInspectorPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    )

    expect(screen.getByText(/Unable to load analysis: Analysis record not found/i)).toBeInTheDocument()
    const retryBtn = screen.getByRole('button', { name: /retry/i })
    fireEvent.click(retryBtn)
    expect(mockRefetch).toHaveBeenCalled()
  })

  it('renders full analysis results, metrics, stress cases, and stale banner', () => {
    const mockResultJson: AnalysisResult = {
      model_version: 'rules-v1',
      baseline: {
        dates: ['2026-11-01', '2026-11-03', '2026-11-07'],
        balances_paise: [2400000, 1600000, 4600000],
        headrooms_paise: [1900000, 1100000, 4100000],
        first_reserve_breach: null,
        first_negative: null,
        trough_paise: 1600000,
        trough_date: '2026-11-03',
      },
      offers: [
        {
          offer_id: 'bnpl-01',
          funding_gap_paise: 0,
          cash_required_now_paise: 600000,
          total_repayment_paise: 2400000,
          financing_cost_paise: 0,
          remaining_balance_paise: 0,
          shortfall_paise: 0,
          cash_path: {
            dates: ['2026-11-01', '2026-11-03', '2026-11-07'],
            balances_paise: [1800000, 400000, 3400000],
            headrooms_paise: [1300000, -100000, 2900000],
            first_reserve_breach: '2026-11-03',
            first_negative: null,
            trough_paise: 400000,
            trough_date: '2026-11-03',
          },
          pressure_windows: [['2026-11-03', '2026-11-07']],
          reason_codes: ['reserve_breach'],
          excluded_obligations: [],
          status: 'buffer_breach',
          band: 'buffer_breach',
          first_reserve_breach: '2026-11-03',
          trough_paise: 400000,
          trough_date: '2026-11-03',
          evidence: [
            {
              code: 'RESERVE_BREACH',
              date: '2026-11-03',
              message_key: 'rent_creates_squeeze',
              before_paise: 1200000,
              after_paise: 400000,
              threshold_paise: 500000,
              assumptions: ['Standard debit-before-credit'],
              event_ids: ['rent-event'],
            },
          ],
        },
      ],
      stress_results: {
        income_delay_7d: [
          {
            offer_id: 'bnpl-01',
            status: 'shortfall',
            band: 'shortfall',
            trough_paise: -700000,
            funding_gap_paise: 0,
            cash_required_now_paise: 600000,
            total_repayment_paise: 2400000,
            financing_cost_paise: 0,
            remaining_balance_paise: 0,
            shortfall_paise: 700000,
            cash_path: { dates: [], balances_paise: [], headrooms_paise: [] },
            pressure_windows: [],
            reason_codes: ['income_delay_shortfall'],
            excluded_obligations: [],
          },
        ],
      },
    }

    const mockAnalysisOut: AnalysisOut = {
      id: 'an-123',
      scenario_id: 'scen-456',
      result_json: JSON.stringify(mockResultJson),
      model_version: 'rules-v1',
      source_data_version: 1,
      calculated_at: '2026-11-01T10:00:00Z',
      stale: true,
      snapshot_hash: 'a1b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef',
    }

    vi.spyOn(inspectorHooks, 'useAnalysis').mockReturnValue({
      data: mockAnalysisOut,
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/model-inspector?analysis_id=an-123']}>
          <Routes>
            <Route path="/model-inspector" element={<ModelInspectorPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    )

    // Stale banner
    expect(screen.getByText(/Stale Analysis:/i)).toBeInTheDocument()

    // Outcome Verdict
    expect(screen.getByText('Buffer Breach')).toBeInTheDocument()

    // Financial Metrics
    expect(screen.getByText('Total Repayment')).toBeInTheDocument()
    expect(screen.getByText('₹24,000')).toBeInTheDocument()
    expect(screen.getByText('Upfront Cash Required')).toBeInTheDocument()
    expect(screen.getByText('₹6,000')).toBeInTheDocument()
    expect(screen.getByText('Minimum Cash (Trough)')).toBeInTheDocument()
    expect(screen.getAllByText('₹4,000').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('First Reserve Breach')).toBeInTheDocument()
    expect(screen.getAllByText('3 Nov 2026').length).toBeGreaterThanOrEqual(1)

    // Stress Cases
    expect(screen.getByText('Salary Delayed by 7 Days')).toBeInTheDocument()
    expect(screen.getByText('-₹7,000')).toBeInTheDocument()

    // Reason Evidence
    expect(screen.getByText('RESERVE_BREACH')).toBeInTheDocument()
    expect(screen.getByText('rent_creates_squeeze')).toBeInTheDocument()

    // Snapshot Hash
    expect(screen.getByText('a1b2c3d4e5f67890...90abcdef')).toBeInTheDocument()
    const hashSpan = screen.getByText('a1b2c3d4e5f67890...90abcdef')
    expect(hashSpan).toHaveAttribute(
      'title',
      'a1b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef'
    )

    // Table toggle
    const toggleBtn = screen.getByRole('button', { name: /show data table/i })
    fireEvent.click(toggleBtn)
    expect(screen.getByRole('table', { name: /simulation cash path table/i })).toBeInTheDocument()
  })

  it('renders counterfactual alternatives and no_feasible_plan when triggered', async () => {
    const mockResultJson: AnalysisResult = {
      model_version: 'rules-v1',
      baseline: { dates: ['2026-11-01'], balances_paise: [100000], headrooms_paise: [50000] },
      offers: [
        {
          offer_id: 'offer-1',
          band: 'shortfall',
          status: 'shortfall',
          funding_gap_paise: 0,
          cash_required_now_paise: 0,
          total_repayment_paise: 100000,
          financing_cost_paise: 0,
          remaining_balance_paise: 0,
          shortfall_paise: 50000,
          cash_path: { dates: ['2026-11-01'], balances_paise: [-50000], headrooms_paise: [-100000] },
          pressure_windows: [],
          reason_codes: [],
          excluded_obligations: [],
        },
      ],
    }

    const mockAnalysisOut: AnalysisOut = {
      id: 'an-123',
      scenario_id: 'scen-456',
      result_json: JSON.stringify(mockResultJson),
      model_version: 'rules-v1',
      source_data_version: 1,
      calculated_at: '2026-11-01T10:00:00Z',
      stale: false,
    }

    vi.spyOn(inspectorHooks, 'useAnalysis').mockReturnValue({
      data: mockAnalysisOut,
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)

    const mockMutateAsync = vi.fn().mockResolvedValue({
      feasible: [
        {
          description: 'Increase savings contribution to ₹5,000',
          changes: { allowed_savings_paise: 500000 },
          assumptions: ['Immediate down payment from reserve buffer'],
          financing_cost_diff_paise: 0,
          min_cash_diff_paise: 200000,
          tradeoffs: ['Lower reserve headroom in month 1'],
          approval_dependencies: [],
          goal_impacts: [],
          user_changes_count: 1,
          full_financing_cost_paise: 0,
          min_cash_paise: 100000,
        },
      ],
      no_feasible_plan: false,
      binding_causes: [],
      tested_count: 24,
      bounds: {},
      truncated: false,
      insufficient_data: false,
      missing_fields: [],
      evidence: [],
    } as CounterfactualOut)

    vi.spyOn(inspectorHooks, 'useCounterfactualMutation').mockReturnValue({
      mutateAsync: mockMutateAsync,
      isPending: false,
      isError: false,
    } as any)

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/model-inspector?analysis_id=an-123&scenario_id=scen-456']}>
          <Routes>
            <Route path="/model-inspector" element={<ModelInspectorPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    )

    const runBtn = screen.getByRole('button', { name: /run counterfactual search/i })
    fireEvent.click(runBtn)

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith({
        scenarioId: 'scen-456',
        body: expect.objectContaining({
          analysis_id: 'an-123',
          allowed_changes: ['savings', 'discretionary_expenses', 'loan_tenure'],
        }),
      })
    })

    expect(await screen.findByText(/Alternative #1: Increase savings contribution to ₹5,000/i)).toBeInTheDocument()
    expect(screen.getByText('FEASIBLE')).toBeInTheDocument()
    expect(screen.getByText('1 change(s)')).toBeInTheDocument()
  })

  it('renders no_feasible_plan banner and binding causes when all candidates fail', async () => {
    const mockResultJson: AnalysisResult = {
      model_version: 'rules-v1',
      baseline: { dates: ['2026-11-01'], balances_paise: [100000], headrooms_paise: [50000] },
      offers: [
        {
          offer_id: 'offer-fail',
          band: 'shortfall',
          status: 'shortfall',
          funding_gap_paise: 0,
          cash_required_now_paise: 0,
          total_repayment_paise: 100000,
          financing_cost_paise: 0,
          remaining_balance_paise: 0,
          shortfall_paise: 50000,
          cash_path: { dates: ['2026-11-01'], balances_paise: [-50000], headrooms_paise: [-100000] },
          pressure_windows: [],
          reason_codes: [],
          excluded_obligations: [],
        },
      ],
    }

    const mockAnalysisOut: AnalysisOut = {
      id: 'an-fail',
      scenario_id: 'scen-fail',
      result_json: JSON.stringify(mockResultJson),
      model_version: 'rules-v1',
      source_data_version: 1,
      calculated_at: '2026-11-01T10:00:00Z',
      stale: false,
    }

    vi.spyOn(inspectorHooks, 'useAnalysis').mockReturnValue({
      data: mockAnalysisOut,
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)

    const mockMutateAsync = vi.fn().mockResolvedValue({
      feasible: [],
      no_feasible_plan: true,
      binding_causes: ['reserve_breach_in_all_candidates', 'unsupported_borrowing_limit'],
      tested_count: 500,
      bounds: {},
      truncated: true,
      insufficient_data: false,
      missing_fields: [],
      evidence: [],
    } as CounterfactualOut)

    vi.spyOn(inspectorHooks, 'useCounterfactualMutation').mockReturnValue({
      mutateAsync: mockMutateAsync,
      isPending: false,
      isError: false,
    } as any)

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/model-inspector?analysis_id=an-fail&scenario_id=scen-fail']}>
          <Routes>
            <Route path="/model-inspector" element={<ModelInspectorPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    )

    const runBtn = screen.getByRole('button', { name: /run counterfactual search/i })
    fireEvent.click(runBtn)

    expect(
      await screen.findByText(/No Feasible Plan Found Within Searched Bounds/i)
    ).toBeInTheDocument()
    expect(screen.getByText(/Tested 500 candidate combinations/i)).toBeInTheDocument()
    expect(screen.getByText('reserve_breach_in_all_candidates')).toBeInTheDocument()
    expect(screen.getByText('unsupported_borrowing_limit')).toBeInTheDocument()
  })

  it('displays "Not available" and never "Canonical Verified" when snapshot_hash is missing or null', () => {
    const mockResultJson: AnalysisResult = {
      model_version: 'rules-v1',
      baseline: { dates: ['2026-11-01'], balances_paise: [100000], headrooms_paise: [50000] },
      offers: [
        {
          offer_id: 'off-1',
          band: 'safe',
          status: 'viable',
          funding_gap_paise: 0,
          cash_required_now_paise: 0,
          total_repayment_paise: 0,
          financing_cost_paise: 0,
          remaining_balance_paise: 0,
          shortfall_paise: 0,
          cash_path: { dates: [], balances_paise: [], headrooms_paise: [] },
          pressure_windows: [],
          reason_codes: [],
          excluded_obligations: [],
        },
      ],
    }

    const mockAnalysisWithoutHash: AnalysisOut = {
      id: 'an-nohash',
      scenario_id: 'scen-nohash',
      result_json: JSON.stringify(mockResultJson),
      model_version: 'rules-v1',
      source_data_version: 1,
      calculated_at: '2026-11-01T10:00:00Z',
      stale: false,
      snapshot_hash: null,
    }

    vi.spyOn(inspectorHooks, 'useAnalysis').mockReturnValue({
      data: mockAnalysisWithoutHash,
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/model-inspector?analysis_id=an-nohash']}>
          <Routes>
            <Route path="/model-inspector" element={<ModelInspectorPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    )

    // Snapshot Hash header is present
    expect(screen.getByText('Snapshot Hash (SHA-256)')).toBeInTheDocument()

    // Must display "Not available" with fallback title
    const notAvailableSpan = screen.getByTitle('Snapshot hash not available')
    expect(notAvailableSpan).toBeInTheDocument()
    expect(notAvailableSpan).toHaveTextContent('Not available')

    // Misleading "Canonical Verified" label must NEVER be displayed
    expect(screen.queryByText(/Canonical Verified/i)).not.toBeInTheDocument()
  })
})
