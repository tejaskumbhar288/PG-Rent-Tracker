import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render } from '@testing-library/react-native';
import type { ReactNode } from 'react';

jest.mock('expo-router', () => ({
  Link: ({ children }: { children: ReactNode }) => children,
}));

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
import { ApiError } from '@/api/client';
import LoginScreen from '@/app/(auth)/login';
import { AuthProvider } from '@/components/auth-provider';
import { getToken, saveToken } from '@/lib/auth-storage';

const loginMock = login as jest.MockedFunction<typeof login>;
const getTokenMock = getToken as jest.MockedFunction<typeof getToken>;
const saveTokenMock = saveToken as jest.MockedFunction<typeof saveToken>;

/**
 * One submitting test per file, deliberately.
 *
 * RNTL 14 wraps `fireEvent` in `act()` while react-hook-form validates
 * asynchronously, which leaves an act scope open past the end of the test; a
 * second `render()` in the same file then returns an empty tree. The other
 * behaviours this screen relies on are covered where they live:
 * `auth-schemas.test.ts` (the validation messages), `api-error-detail.test.ts`
 * (how a network failure reads) and `use-login.test.tsx` (storing the token).
 */
describe('Login screen', () => {
  it('shows the server message on a rejected login and stores no token', async () => {
    getTokenMock.mockResolvedValue(null);
    saveTokenMock.mockResolvedValue(true);
    loginMock.mockRejectedValue(new ApiError(401, 'invalid phone/email or password'));

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const screen = await render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <LoginScreen />
        </AuthProvider>
      </QueryClientProvider>,
    );

    fireEvent.changeText(screen.getByLabelText('PHONE OR EMAIL'), '98765 43210');
    fireEvent.changeText(screen.getByLabelText('PASSWORD'), 'wrong-password');
    fireEvent.press(screen.getByRole('button', { name: 'Log in' }));

    // The backend's lowercase detail, shown capitalised.
    expect(await screen.findByText('Invalid phone/email or password')).toBeTruthy();
    expect(saveTokenMock).not.toHaveBeenCalled();

    queryClient.clear();
  });
});
