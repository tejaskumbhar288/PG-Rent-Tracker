import { Pressable, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useHealth } from '@/api/use-health';
import { useMe } from '@/api/use-auth';
import { useAuth } from '@/components/auth-provider';
import { StatusPill } from '@/components/status-pill';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { BottomTabInset, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { describeApiError } from '@/lib/api-errors';
import { confirmAction } from '@/lib/confirm';
import { API_URL } from '@/lib/config';
import { interpretHealth } from '@/lib/health';

export default function SettingsScreen() {
  const theme = useTheme();
  const query = useHealth();
  const state = interpretHealth(query);
  const me = useMe();
  const { signOut } = useAuth();

  const confirmLogout = () => {
    confirmAction({
      title: 'Log out?',
      message: 'You will need your password to log back in.',
      confirmLabel: 'Log out',
      onConfirm: () => void signOut(),
    });
  };

  return (
    <ThemedView style={styles.container}>
      <SafeAreaView style={styles.safeArea}>
        <ThemedText type="subtitle">Settings</ThemedText>

        <ThemedView type="backgroundElement" style={styles.card}>
          <ThemedText type="smallBold" themeColor="textSecondary">
            ACCOUNT
          </ThemedText>

          {me.isLoading ? (
            <ThemedText type="small" themeColor="textSecondary">
              Loading…
            </ThemedText>
          ) : null}

          {me.data === undefined ? null : (
            <>
              <ThemedText>{me.data.name}</ThemedText>
              <ThemedText type="small" themeColor="textSecondary">
                {me.data.phone}
              </ThemedText>
              {me.data.email === null ? null : (
                <ThemedText type="small" themeColor="textSecondary">
                  {me.data.email}
                </ThemedText>
              )}
            </>
          )}

          {me.isError ? (
            <ThemedText type="small" style={{ color: theme.statusError }}>
              {describeApiError(me.error)}
            </ThemedText>
          ) : null}

          <Pressable
            accessibilityRole="button"
            onPress={confirmLogout}
            style={({ pressed }) => [
              styles.action,
              { borderColor: theme.statusError, opacity: pressed ? 0.7 : 1 },
            ]}>
            <ThemedText type="smallBold" style={{ color: theme.statusError }}>
              Log out
            </ThemedText>
          </Pressable>
        </ThemedView>

        <ThemedView type="backgroundElement" style={styles.card}>
          <ThemedText type="smallBold" themeColor="textSecondary">
            BACKEND
          </ThemedText>
          <StatusPill state={state} />
          <ThemedText type="small" themeColor="textSecondary">
            {API_URL}
          </ThemedText>

          <Pressable
            accessibilityRole="button"
            disabled={query.isFetching}
            onPress={() => query.refetch()}
            style={({ pressed }) => [
              styles.retry,
              { backgroundColor: theme.backgroundSelected, opacity: pressed ? 0.7 : 1 },
            ]}>
            <ThemedText type="smallBold">{query.isFetching ? 'Checking…' : 'Retry'}</ThemedText>
          </Pressable>
        </ThemedView>
      </SafeAreaView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  safeArea: {
    flex: 1,
    gap: Spacing.four,
    paddingHorizontal: Spacing.four,
    paddingTop: Spacing.six,
    paddingBottom: BottomTabInset,
  },
  card: {
    gap: Spacing.three,
    padding: Spacing.four,
    borderRadius: Spacing.three,
  },
  action: {
    alignSelf: 'flex-start',
    borderWidth: 1,
    paddingHorizontal: Spacing.four,
    paddingVertical: Spacing.two,
    borderRadius: Spacing.five,
  },
  retry: {
    alignSelf: 'flex-start',
    paddingHorizontal: Spacing.four,
    paddingVertical: Spacing.two,
    borderRadius: Spacing.five,
  },
});
