import { StyleSheet, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Spacing, type ThemeColor } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import type { ConnectionState } from '@/types/health';

const STATE_META: Record<ConnectionState, { label: string; color: ThemeColor }> = {
  checking: { label: 'Checking…', color: 'statusMuted' },
  connected: { label: 'Connected', color: 'statusConnected' },
  db_down: { label: 'Server up, database down', color: 'statusWarning' },
  unreachable: { label: "Can't reach server", color: 'statusError' },
};

/** Coloured dot + label describing the backend connection state. */
export function StatusPill({ state }: { state: ConnectionState }) {
  const theme = useTheme();
  const { label, color } = STATE_META[state];

  return (
    <View style={styles.pill}>
      <View style={[styles.dot, { backgroundColor: theme[color] }]} />
      <ThemedText type="smallBold" style={{ color: theme[color] }}>
        {label}
      </ThemedText>
    </View>
  );
}

const styles = StyleSheet.create({
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
});
