import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { alertsApi } from './api'

export function useAlerts() {
  return useQuery({
    queryKey: ['alerts'],
    queryFn: ({ signal }) => alertsApi.list(signal),
  })
}

export function useDismissAlert() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => alertsApi.dismiss(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alerts'] })
    },
  })
}
