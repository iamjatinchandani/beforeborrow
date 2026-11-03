import { api } from '@/lib/api'
import {
  ScenarioData,
  SetupStatus,
  AnalysisResponse,
  CounterfactualResponse,
} from './types'

export const decisionApi = {
  getSetupStatus: (signal?: AbortSignal) =>
    api.get<SetupStatus>('/scenarios/setup-status', signal),

  getScenarios: (signal?: AbortSignal) =>
    api.get<ScenarioData[]>('/scenarios', signal),

  getScenario: (id: string, signal?: AbortSignal) =>
    api.get<ScenarioData>(`/scenarios/${id}`, signal),

  createScenario: (body: ScenarioData) =>
    api.post<ScenarioData>('/scenarios', body),

  updateScenario: (id: string, body: ScenarioData) =>
    api.put<ScenarioData>(`/scenarios/${id}`, body),

  deleteScenario: (id: string) =>
    api.delete<void>(`/scenarios/${id}`),

  analyze: (
    scenarioId: string,
    body: {
      scenario_version: number
      expected_data_version: number
      stress_cases: string[]
    }
  ) => api.post<AnalysisResponse>(`/scenarios/${scenarioId}/analyze`, body),

  getAnalysis: (analysisId: string, signal?: AbortSignal) =>
    api.get<AnalysisResponse>(`/analyses/${analysisId}`, signal),

  counterfactuals: (
    scenarioId: string,
    body: {
      analysis_id: string
      allowed_changes: string[]
      bounds: Record<string, unknown>
    }
  ) =>
    api.post<CounterfactualResponse>(
      `/scenarios/${scenarioId}/counterfactuals`,
      body
    ),
}
