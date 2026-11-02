import { api } from '@/lib/api'
import { AnalysisOut, CounterfactualOut, CounterfactualRequest } from './types'

export const modelInspectorApi = {
  getAnalysis: (id: string, signal?: AbortSignal): Promise<AnalysisOut> =>
    api.get<AnalysisOut>(`/analyses/${id}`, signal),

  getCounterfactuals: (
    scenarioId: string,
    body: CounterfactualRequest,
    signal?: AbortSignal,
  ): Promise<CounterfactualOut> =>
    api.post<CounterfactualOut>(`/scenarios/${scenarioId}/counterfactuals`, body, signal),
}
