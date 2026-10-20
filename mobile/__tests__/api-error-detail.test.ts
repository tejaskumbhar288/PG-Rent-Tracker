import { ApiError, apiGet } from '@/api/client';
import { describeApiError } from '@/lib/api-errors';

const fetchMock = jest.fn();

beforeEach(() => {
  fetchMock.mockReset();
  globalThis.fetch = fetchMock as unknown as typeof fetch;
});

describe('ApiError', () => {
  it("carries the server's detail message", async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'invalid phone/email or password' }),
    });

    await expect(apiGet('/auth/me')).rejects.toMatchObject({
      status: 401,
      detail: 'invalid phone/email or password',
    });
  });

  it('leaves detail unset when 422 sends a list of field errors', async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({ detail: [{ loc: ['body', 'phone'], msg: 'bad' }] }),
    });

    await expect(apiGet('/auth/signup')).rejects.toMatchObject({
      status: 422,
      detail: undefined,
    });
  });
});

describe('describeApiError', () => {
  it('capitalises the server detail for display', () => {
    expect(describeApiError(new ApiError(401, 'invalid phone/email or password'))).toBe(
      'Invalid phone/email or password',
    );
    expect(describeApiError(new ApiError(409, 'an account with this phone already exists'))).toBe(
      'An account with this phone already exists',
    );
  });

  it('reads a request that never got an answer as unreachable', () => {
    expect(describeApiError(new TypeError('Network request failed'))).toBe(
      "Can't reach server. Check your connection.",
    );
  });

  it('falls back to a generic message when there is no usable detail', () => {
    expect(describeApiError(new ApiError(500))).toBe('Something went wrong. Please try again.');
  });
});
