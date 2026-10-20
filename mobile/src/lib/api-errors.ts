import { ApiError } from '@/api/client';

const UNREACHABLE = "Can't reach server. Check your connection.";
const UNEXPECTED = 'Something went wrong. Please try again.';

/**
 * Turn a failed request into one line the owner can act on.
 *
 * The backend sends lowercase `{"detail": "..."}` messages (CLAUDE.md §8), so
 * they are shown with the first letter capitalised. A request that never got an
 * answer — no network, or the client's timeout — reads as unreachable rather
 * than as a server error.
 */
export function describeApiError(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return UNREACHABLE;
  }
  if (error.detail) {
    return error.detail.charAt(0).toUpperCase() + error.detail.slice(1);
  }
  return UNEXPECTED;
}
