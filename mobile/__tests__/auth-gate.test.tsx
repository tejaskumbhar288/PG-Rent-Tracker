import { Text } from 'react-native';

jest.mock('@/components/animated-icon', () => ({
  // The splash overlay is irrelevant here and drags in Reanimated.
  AnimatedSplashOverlay: () => null,
}));

jest.mock('@/lib/auth-storage', () => ({
  getToken: jest.fn(),
  saveToken: jest.fn(async () => true),
  clearToken: jest.fn(async () => true),
}));

jest.mock('@/api/auth', () => ({
  login: jest.fn(),
  signup: jest.fn(),
  fetchMe: jest.fn(async () => ({
    id: '3f1c7f4e-8e2a-4d3b-9b7a-2c9f0a1b5d61',
    name: 'Suresh Kumar',
    phone: '+919876543210',
    email: null,
    created_at: '2026-10-20T09:15:00+05:30',
  })),
}));

import { renderRouter, screen } from 'expo-router/testing-library';

import RootLayout from '@/app/_layout';
import { getToken } from '@/lib/auth-storage';

const getTokenMock = getToken as jest.MockedFunction<typeof getToken>;

function renderApp() {
  return renderRouter(
    {
      _layout: RootLayout,
      '(auth)/login': () => <Text>Login screen</Text>,
      '(auth)/signup': () => <Text>Signup screen</Text>,
      '(tabs)/index': () => <Text>Dashboard screen</Text>,
    },
    { initialUrl: '/' },
  );
}

beforeEach(() => {
  jest.clearAllMocks();
});

describe('auth gate', () => {
  it('sends an owner with no stored token to the login screen', async () => {
    getTokenMock.mockResolvedValue(null);

    await renderApp();

    expect(await screen.findByText('Login screen')).toBeTruthy();
    expect(screen.queryByText('Dashboard screen')).toBeNull();
  });

  it('keeps an owner with a stored token on the dashboard', async () => {
    getTokenMock.mockResolvedValue('a-stored-token');

    await renderApp();

    expect(await screen.findByText('Dashboard screen')).toBeTruthy();
    expect(screen.queryByText('Login screen')).toBeNull();
  });
});
