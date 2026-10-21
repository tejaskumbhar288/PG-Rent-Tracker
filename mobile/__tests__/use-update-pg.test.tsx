import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react-native';
import type { ReactNode } from 'react';

jest.mock('@/lib/auth-storage', () => ({
  getToken: jest.fn(),
  saveToken: jest.fn(),
  clearToken: jest.fn(),
}));

import { useUpdatePg } from '@/api/use-pg';
import { AuthProvider } from '@/components/auth-provider';
import { getToken } from '@/lib/auth-storage';
import type { Pg } from '@/types/pg';

const getTokenMock = getToken as jest.MockedFunction<typeof getToken>;
const fetchMock = jest.fn();

const saved: Pg = {
  id: '9b1f0c2a-4e77-4a51-9f3d-0b6a1c8e2d44',
  name: 'Sri Sai PG',
  address: null,
  default_rent_due_day: 10,
  created_at: '2026-10-20T09:15:00+05:30',
};

it('sends the mapped body and puts the saved PG straight into the cache', async () => {
  getTokenMock.mockResolvedValue(null);
  fetchMock.mockResolvedValue({ ok: true, status: 200, json: async () => saved } as Response);
  globalThis.fetch = fetchMock as unknown as typeof fetch;

  const queryClient = new QueryClient({
    // gcTime 0 on mutations only: the default 5-minute timer would outlive the
    // run. Queries keep theirs, since the ['pg'] cache is asserted below.
    defaultOptions: { queries: { retry: false }, mutations: { retry: false, gcTime: 0 } },
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  );

  const { result, unmount } = await renderHook(() => useUpdatePg(), { wrapper });

  await act(async () => {
    result.current.mutate({ name: 'Sri Sai PG', address: null, default_rent_due_day: 10 });
  });

  await waitFor(() => expect(fetchMock).toHaveBeenCalled());
  const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(init.method).toBe('PATCH');
  // A cleared address travels as null, and the due day as a number.
  expect(init.body).toBe(
    JSON.stringify({ name: 'Sri Sai PG', address: null, default_rent_due_day: 10 }),
  );

  // No refetch needed: the PATCH response is the whole PG.
  await waitFor(() => expect(queryClient.getQueryData(['pg'])).toEqual(saved));

  queryClient.removeQueries({ queryKey: ['pg'] });
  await unmount();
});
