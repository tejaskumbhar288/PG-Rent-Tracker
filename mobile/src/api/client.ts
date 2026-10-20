import { API_PREFIX, API_URL } from '@/lib/config';

/**
 * Thrown when the backend responds with a non-2xx status. Carries the HTTP
 * status so callers (e.g. health mapping) can distinguish cases like 503, and
 * the server's `detail` message where there was one, so a screen can show what
 * the backend actually said.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly detail?: string;

  constructor(status: number, detail?: string) {
    super(detail ?? `Request failed with status ${status}`);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

const DEFAULT_TIMEOUT_MS = 5000;

let authToken: string | null = null;

/**
 * Set the bearer token sent with every subsequent request; `null` clears it.
 * Owned by the auth provider, which keeps it in step with secure storage.
 */
export function setAuthToken(token: string | null): void {
  authToken = token;
}

function authHeader(): Record<string, string> {
  return authToken === null ? {} : { Authorization: `Bearer ${authToken}` };
}

/** FastAPI reports errors as `{"detail": "..."}` (CLAUDE.md §8). */
async function readDetail(response: Response): Promise<string | undefined> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    // 422 sends an array of field errors instead; those are not owner-readable,
    // so they fall through to a generic message.
    return typeof body.detail === 'string' ? body.detail : undefined;
  } catch {
    return undefined;
  }
}

/**
 * Fetch `${API_URL}${API_PREFIX}${path}` as JSON.
 *
 * Aborts after `timeoutMs` (default 5s) so a dead server surfaces promptly
 * instead of hanging — `fetch` has no default timeout. Non-2xx responses throw
 * `ApiError`; network errors and timeouts propagate as-is.
 */
async function request<T>(path: string, init: RequestInit, timeoutMs?: number): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs ?? DEFAULT_TIMEOUT_MS);

  try {
    const response = await fetch(`${API_URL}${API_PREFIX}${path}`, {
      ...init,
      headers: { Accept: 'application/json', ...authHeader(), ...init.headers },
      signal: controller.signal,
    });
    if (!response.ok) {
      throw new ApiError(response.status, await readDetail(response));
    }
    return (await response.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}

export async function apiGet<T>(path: string, opts?: { timeoutMs?: number }): Promise<T> {
  return request<T>(path, { method: 'GET' }, opts?.timeoutMs);
}

export async function apiPost<T>(
  path: string,
  body: unknown,
  opts?: { timeoutMs?: number },
): Promise<T> {
  return request<T>(
    path,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
    opts?.timeoutMs,
  );
}
