import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { DarkTheme, DefaultTheme, Stack, ThemeProvider } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { useColorScheme } from 'react-native';

import { AnimatedSplashOverlay } from '@/components/animated-icon';
import { AuthProvider, useAuth } from '@/components/auth-provider';

SplashScreen.preventAutoHideAsync();

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

export default function RootLayout() {
  const colorScheme = useColorScheme();
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ThemeProvider value={colorScheme === 'dark' ? DarkTheme : DefaultTheme}>
          <AnimatedSplashOverlay />
          <RootNavigator />
        </ThemeProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}

function RootNavigator() {
  const { token, isHydrating } = useAuth();

  // Render no navigator until the stored token has been read back. The splash
  // overlay covers this, and it means the guards below never flip after mount —
  // which is what would make the login screen flash before the dashboard.
  if (isHydrating) return null;

  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Protected guard={token !== null} redirectTo="/login">
        <Stack.Screen name="(tabs)" />
      </Stack.Protected>
      <Stack.Protected guard={token === null} redirectTo="/">
        <Stack.Screen name="(auth)" />
      </Stack.Protected>
    </Stack>
  );
}
