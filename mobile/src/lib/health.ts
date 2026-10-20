import { ApiError } from '@/api/client';
import type { ConnectionState, HealthResponse } from '@/types/health';

/**
 * Map a TanStack Query result for the health endpoint to a display state.
 * Pure (no hooks) so it can be unit-tested without a device.
 */
export function interpretHealth(q: {
  isPending: boolean;
  isError: boolean;
  error?: unknown;
  data?: HealthResponse;
}): ConnectionState {
  if (q.isPending) return 'checking';
  if (q.data?.status === 'ok') return 'connected';
  if (q.error instanceof ApiError && q.error.status === 503) return 'db_down';
  return 'unreachable';
}
