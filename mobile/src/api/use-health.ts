import { useQuery } from '@tanstack/react-query';

import { apiGet } from '@/api/client';
import type { HealthResponse } from '@/types/health';

/** Query the backend health endpoint. `retry: false` so a down server fails fast. */
export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => apiGet<HealthResponse>('/health'),
    retry: false,
    staleTime: 0,
  });
}
