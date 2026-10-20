import { API_PREFIX, API_URL } from '@/lib/config';

/**
 * Thrown when the backend responds with a non-2xx status. Carries the HTTP
 * status so callers (e.g. health mapping) can distinguish cases like 503.
 */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message?: string) {
    super(message ?? `Request failed with status ${status}`);
    this.name = 'ApiError';
    this.status = status;
  }
}

const DEFAULT_TIMEOUT_MS = 5000;

/**
 * GET `${API_URL}${API_PREFIX}${path}` as JSON.
 *
 * Aborts after `timeoutMs` (default 5s) so a dead server surfaces as an error
 * promptly instead of hanging — `fetch` has no default timeout. Non-2xx
 * responses throw `ApiError`; network errors / timeouts propagate as-is. No
 * auth header yet (added in F1).
 */
export async function apiGet<T>(path: string, opts?: { timeoutMs?: number }): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), opts?.timeoutMs ?? DEFAULT_TIMEOUT_MS);

  try {
    const res = await fetch(`${API_URL}${API_PREFIX}${path}`, {
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    });
    if (!res.ok) {
      throw new ApiError(res.status);
    }
    return (await res.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}
