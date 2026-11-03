import { api } from '@/lib/api'

export interface AlertItem {
  id: string
  alert_type: string
  due_date: string | null
  source_event_id: string | null
  message: string
  dismissed_at: string | null
  created_at: string
}

export const alertsApi = {
  list: (signal?: AbortSignal) => api.get<AlertItem[]>('/alerts', signal),
  dismiss: (id: string) => api.patch<AlertItem>(`/alerts/${id}`, {}),
}
