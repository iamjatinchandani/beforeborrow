import { useQuery } from '@tanstack/react-query'
import { queryKeys } from '@/lib/queryKeys'
import { profileApi } from './api'

export function useProfile(userId: string) {
  return useQuery({
    queryKey: queryKeys.profile(userId),
    queryFn: ({ signal }) => profileApi.get(signal),
  })
}
