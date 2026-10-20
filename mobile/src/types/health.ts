/** Response body of `GET /api/v1/health` when the backend is healthy. */
export type HealthResponse = { status: 'ok' };

/**
 * How the Settings screen describes the backend connection.
 * - `checking`     — request in flight
 * - `connected`    — 200 `{"status":"ok"}`
 * - `db_down`      — 503, backend up but database unavailable
 * - `unreachable`  — network error, timeout, or any other non-2xx
 */
export type ConnectionState = 'checking' | 'connected' | 'db_down' | 'unreachable';
