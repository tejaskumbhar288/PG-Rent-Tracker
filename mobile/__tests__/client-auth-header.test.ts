import { apiGet, apiPost, setAuthToken } from '@/api/client';

const fetchMock = jest.fn();

function okResponse() {
  return { ok: true, status: 200, json: async () => ({}) };
}

function lastInit(): RequestInit & { headers: Record<string, string> } {
  return fetchMock.mock.calls[0][1];
}

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockResolvedValue(okResponse());
  globalThis.fetch = fetchMock as unknown as typeof fetch;
});

afterEach(() => {
  setAuthToken(null);
});

describe('bearer token', () => {
  it('is sent once a token is set', async () => {
    setAuthToken('abc');

    await apiGet('/auth/me');

    expect(lastInit().headers.Authorization).toBe('Bearer abc');
  });

  it('is absent before any token is set', async () => {
    await apiGet('/health');

    expect(lastInit().headers.Authorization).toBeUndefined();
  });

  it('is absent again once the token is cleared', async () => {
    setAuthToken('abc');
    setAuthToken(null);

    await apiGet('/auth/me');

    expect(lastInit().headers.Authorization).toBeUndefined();
  });

  it('is sent on writes too', async () => {
    setAuthToken('abc');

    await apiPost('/auth/me', { any: 'body' });

    const init = lastInit();
    expect(init.method).toBe('POST');
    expect(init.headers.Authorization).toBe('Bearer abc');
    expect(init.headers['Content-Type']).toBe('application/json');
    expect(init.body).toBe(JSON.stringify({ any: 'body' }));
  });
});
