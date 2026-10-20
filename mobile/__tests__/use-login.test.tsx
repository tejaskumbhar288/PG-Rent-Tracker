import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react-native';
import type { ReactNode } from 'react';

jest.mock('@/api/auth', () => ({
  login: jest.fn(),
  signup: jest.fn(),
  fetchMe: jest.fn(),
}));

jest.mock('@/lib/auth-storage', () => ({
  getToken: jest.fn(),
  saveToken: jest.fn(),
  clearToken: jest.fn(),
}));

import { login } from '@/api/auth';
import { useLogin } from '@/api/use-auth';
import { AuthProvider } from '@/components/auth-provider';
import { getToken, saveToken } from '@/lib/auth-storage';
import type { Owner } from '@/types/auth';

const loginMock = login as jest.MockedFunction<typeof login>;
const getTokenMock = getToken as jest.MockedFunction<typeof getToken>;
const saveTokenMock = saveToken as jest.MockedFunction<typeof saveToken>;

const owner: Owner = {
  id: '3f1c7f4e-8e2a-4d3b-9b7a-2c9f0a1b5d61',
  name: 'Suresh Kumar',
  phone: '+919876543210',
  email: null,
  created_at: '2026-10-20T09:15:00+05:30',
};

it('stores the token and seeds the owner cache on a successful login', async () => {
  getTokenMock.mockResolvedValue(null);
  saveTokenMock.mockResolvedValue(true);
  loginMock.mockResolvedValue({ access_token: 'a-token', token_type: 'bearer', owner });

  const queryClient = new QueryClient({
    // gcTime 0 on mutations only: the mutation's default 5-minute
    // garbage-collection timer otherwise outlives the test run. Queries keep
    // their default, since the owner cache is asserted below.
    defaultOptions: { queries: { retry: false }, mutations: { retry: false, gcTime: 0 } },
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  );

  const { result, unmount } = await renderHook(() => useLogin(), { wrapper });

  await act(async () => {
    result.current.mutate({ identifier: '98765 43210', password: 'hunter2hunter2' });
  });

  await waitFor(() => expect(saveTokenMock).toHaveBeenCalledWith('a-token'));
  // The owner rides along in the response, so the dashboard needs no /auth/me
  // round trip to render.
  expect(queryClient.getQueryData(['me'])).toEqual(owner);

  queryClient.removeQueries({ queryKey: ['me'] });
  await unmount();
});
