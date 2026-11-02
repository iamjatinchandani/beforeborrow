import { describe, it, expect, vi, beforeEach } from 'vitest'
import { modelInspectorApi } from '../api'
import { api } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'

vi.mock('@/lib/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

describe('modelInspectorApi', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('getAnalysis queries GET /analyses/{id} via shared api client', async () => {
    const mockAnalysis = { id: 'test-id', scenario_id: 'scen-1', result_json: '{}' }
    vi.mocked(api.get).mockResolvedValueOnce(mockAnalysis)

    const result = await modelInspectorApi.getAnalysis('test-id')

    expect(api.get).toHaveBeenCalledWith('/analyses/test-id', undefined)
    expect(result).toEqual(mockAnalysis)
  })

  it('getCounterfactuals queries POST /scenarios/{id}/counterfactuals via shared api client', async () => {
    const mockResponse = { feasible: [], no_feasible_plan: true, tested_count: 50 }
    vi.mocked(api.post).mockResolvedValueOnce(mockResponse)

    const payload = {
      analysis_id: 'analysis-123',
      allowed_changes: ['savings'],
      bounds: { max_savings_paise: 500000 },
    }
    const result = await modelInspectorApi.getCounterfactuals('scen-456', payload)

    expect(api.post).toHaveBeenCalledWith('/scenarios/scen-456/counterfactuals', payload, undefined)
    expect(result).toEqual(mockResponse)
  })

  it('queryKeys prefix analysis with current userId for multi-user isolation', () => {
    const key = queryKeys.analysis('user-abc', 'analysis-xyz')
    expect(key).toEqual(['user-abc', 'analyses', 'analysis-xyz'])
  })
})
