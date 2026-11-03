import { useQuery } from '@tanstack/react-query'
import { reportsApi } from './api'

export function useReceipt(id?: string) {
  return useQuery({
    queryKey: ['receipts', id],
    queryFn: ({ signal }) => (id ? reportsApi.getReceipt(id, signal) : null),
    enabled: Boolean(id),
  })
}

export function useExportReceipt(id?: string) {
  return useQuery({
    queryKey: ['receipts', id, 'export'],
    queryFn: ({ signal }) => (id ? reportsApi.exportReceipt(id, signal) : null),
    enabled: false, // On-demand trigger
  })
}
