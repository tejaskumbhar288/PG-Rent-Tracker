import { ApiError, apiPatch, setAuthToken } from '@/api/client';

const fetchMock = jest.fn();

beforeEach(() => {
  fetchMock.mockReset();
  globalThis.fetch = fetchMock as unknown as typeof fetch;
  setAuthToken(null);
});

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response;
}

describe('apiPatch', () => {
  it('sends PATCH with a JSON body and the bearer header', async () => {
    setAuthToken('abc');
    fetchMock.mockResolvedValue(jsonResponse(200, { name: 'Sri Sai PG' }));

    const result = await apiPatch<{ name: string }>('/pg', { name: 'Sri Sai PG' });

    expect(result).toEqual({ name: 'Sri Sai PG' });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain('/api/v1/pg');
    expect(init.method).toBe('PATCH');
    expect(init.body).toBe(JSON.stringify({ name: 'Sri Sai PG' }));
    expect(init.headers).toMatchObject({
      'Content-Type': 'application/json',
      Authorization: 'Bearer abc',
    });
  });

  it('throws an ApiError carrying the status and the server detail', async () => {
    fetchMock.mockResolvedValue(jsonResponse(404, { detail: 'pg not found' }));

    await expect(apiPatch('/pg', {})).rejects.toMatchObject({
      name: 'ApiError',
      status: 404,
      detail: 'pg not found',
    });
    await expect(apiPatch('/pg', {})).rejects.toBeInstanceOf(ApiError);
  });
});
