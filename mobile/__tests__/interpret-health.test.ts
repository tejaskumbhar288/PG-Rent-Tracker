import { ApiError } from '@/api/client';
import { interpretHealth } from '@/lib/health';

describe('interpretHealth', () => {
  it('returns "checking" while the request is in flight', () => {
    expect(interpretHealth({ isPending: true, isError: false })).toBe('checking');
  });

  it('returns "connected" on 200 {status:"ok"}', () => {
    expect(
      interpretHealth({ isPending: false, isError: false, data: { status: 'ok' } }),
    ).toBe('connected');
  });

  it('returns "db_down" on a 503 ApiError', () => {
    expect(
      interpretHealth({ isPending: false, isError: true, error: new ApiError(503) }),
    ).toBe('db_down');
  });

  it('returns "unreachable" on a network error', () => {
    expect(
      interpretHealth({ isPending: false, isError: true, error: new Error('Network request failed') }),
    ).toBe('unreachable');
  });

  it('returns "unreachable" on a non-503 ApiError', () => {
    expect(
      interpretHealth({ isPending: false, isError: true, error: new ApiError(500) }),
    ).toBe('unreachable');
  });
});
