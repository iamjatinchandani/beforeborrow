import { useMutation, useQuery } from '@tanstack/react-query'
import { queryKeys } from '@/lib/queryKeys'
import { modelInspectorApi } from './api'
import { CounterfactualRequest } from './types'

export function useAnalysis(userId: string, id: string) {
  return useQuery({
    queryKey: queryKeys.analysis(userId, id),
    queryFn: ({ signal }) => modelInspectorApi.getAnalysis(id, signal),
    enabled: Boolean(userId && id),
    retry: 1,
  })
}

export function useCounterfactualMutation() {
  return useMutation({
    mutationFn: ({
      scenarioId,
      body,
    }: {
      scenarioId: string
      body: CounterfactualRequest
    }) => modelInspectorApi.getCounterfactuals(scenarioId, body),
  })
}
