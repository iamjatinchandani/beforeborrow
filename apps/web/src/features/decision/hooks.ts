import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { decisionApi } from './api'
import { ScenarioData } from './types'

export function useSetupStatus() {
  return useQuery({
    queryKey: ['scenarios', 'setup-status'],
    queryFn: ({ signal }) => decisionApi.getSetupStatus(signal),
  })
}

export function useScenarios() {
  return useQuery({
    queryKey: ['scenarios'],
    queryFn: ({ signal }) => decisionApi.getScenarios(signal),
  })
}

export function useScenario(id?: string) {
  return useQuery({
    queryKey: ['scenarios', id],
    queryFn: ({ signal }) => (id ? decisionApi.getScenario(id, signal) : null),
    enabled: Boolean(id),
  })
}

export function useCreateScenario() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: ScenarioData) => decisionApi.createScenario(body),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['scenarios'] })
      if (data.id) {
        qc.setQueryData(['scenarios', data.id], data)
      }
    },
  })
}

export function useUpdateScenario(_scenarioId?: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ScenarioData }) =>
      decisionApi.updateScenario(id, data),
    onSuccess: (updated) => {
      qc.invalidateQueries({ queryKey: ['scenarios'] })
      if (updated.id) {
        qc.setQueryData(['scenarios', updated.id], updated)
      }
    },
  })
}

export function useDeleteScenario() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => decisionApi.deleteScenario(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['scenarios'] })
    },
  })
}

export function useAnalyzeScenario(scenarioId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      scenario_version: number
      expected_data_version: number
      stress_cases: string[]
    }) => decisionApi.analyze(scenarioId, body),
    onSuccess: (res) => {
      qc.setQueryData(['analyses', res.id], res)
    },
  })
}

export function useAnalysis(analysisId?: string) {
  return useQuery({
    queryKey: ['analyses', analysisId],
    queryFn: ({ signal }) =>
      analysisId ? decisionApi.getAnalysis(analysisId, signal) : null,
    enabled: Boolean(analysisId),
  })
}

export function useCounterfactuals(scenarioId?: string) {
  return useMutation({
    mutationFn: (body: {
      analysis_id: string
      allowed_changes: string[]
      bounds: Record<string, unknown>
    }) =>
      scenarioId
        ? decisionApi.counterfactuals(scenarioId, body)
        : Promise.reject(new Error('Missing scenario ID')),
  })
}
